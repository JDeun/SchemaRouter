from __future__ import annotations

import base64
import datetime as dt
import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from uuid import UUID

from ..authorization import _current_data_scope
from ..errors import PolicyViolationError, RegistrationError
from ..models import (
    EndpointSpec,
    FieldSpec,
    ParameterSpec,
    ServerProjectionSpec,
    ToolCall,
    ToolSpec,
)

_SELECT_ENDPOINT = "select"
_MAX_LIMIT = 1000


def _require_sqlalchemy() -> tuple[Any, Any, Any, Any]:
    try:
        from sqlalchemy import MetaData, Table, inspect, select
    except ImportError as exc:
        raise RegistrationError(
            "SQLAlchemy database onboarding requires the optional 'database' extra; "
            "install schemarouter[database]"
        ) from exc
    return MetaData, Table, inspect, select


def _slug(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9_]+", "_", value.strip()).strip("_").lower()
    return normalized or "database"


def _json_schema_from_python_type(value: Any, *, nullable: bool) -> dict[str, Any]:
    mapping: dict[Any, dict[str, Any]] = {
        bool: {"type": "boolean"},
        int: {"type": "integer"},
        float: {"type": "number"},
        Decimal: {"type": "number"},
        str: {"type": "string"},
        bytes: {"type": "string", "contentEncoding": "base64"},
        dt.date: {"type": "string", "format": "date"},
        dt.datetime: {"type": "string", "format": "date-time"},
        dt.time: {"type": "string", "format": "time"},
        UUID: {"type": "string", "format": "uuid"},
    }
    schema = dict(mapping.get(value, {}))
    if nullable and isinstance(schema.get("type"), str):
        schema["type"] = [schema["type"], "null"]
    return schema


def _column_schema(column_type: Any, *, nullable: bool) -> dict[str, Any]:
    try:
        python_type = column_type.python_type
    except (AttributeError, NotImplementedError):
        return {}
    return _json_schema_from_python_type(python_type, nullable=nullable)


def _json_safe_value(value: Any) -> Any:
    if isinstance(value, bytes):
        return base64.b64encode(value).decode("ascii")
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, (dt.datetime, dt.date, dt.time)):
        return value.isoformat()
    return value


@dataclass(frozen=True)
class SQLAlchemyTableBinding:
    """One introspected SQLAlchemy relation and its trusted read-only invoker."""

    tool: ToolSpec
    invoker: SQLAlchemyTableInvoker


class SQLAlchemyTableInvoker:
    """Read-only call-aware invoker using SQLAlchemy Core parameter binding."""

    projects_fields = True

    def __init__(
        self,
        engine: Any,
        *,
        table: Any,
        columns: tuple[str, ...],
        filter_columns: tuple[str, ...],
        default_limit: int,
    ) -> None:
        self._engine = engine
        self._table = table
        self._columns = columns
        self._filter_columns = filter_columns
        self._default_limit = default_limit

    def invoke_call(self, call: ToolCall) -> list[dict[str, Any]]:
        if call.endpoint != _SELECT_ENDPOINT:
            raise RuntimeError(f"unknown SQLAlchemy endpoint: {call.endpoint!r}")

        selected = tuple(call.fields) or self._columns
        unknown = sorted(set(selected) - set(self._columns))
        if unknown:
            raise RuntimeError(
                "database selection requested unknown fields: " + ", ".join(unknown)
            )

        _, _, _, select = _require_sqlalchemy()
        statement = select(*(self._table.c[name] for name in selected))
        for column in self._filter_columns:
            if column in call.arguments:
                statement = statement.where(
                    self._table.c[column] == call.arguments[column]
                )

        scope = _current_data_scope()
        if scope is not None:
            for column, value in scope.trusted_filters:
                if column not in self._columns:
                    raise PolicyViolationError(
                        "authorization denied for requested data scope"
                    )
                if isinstance(value, tuple):
                    if not value:
                        statement = statement.where(False)
                    else:
                        statement = statement.where(
                            self._table.c[column].in_(value)
                        )
                else:
                    statement = statement.where(self._table.c[column] == value)

        limit = int(call.arguments.get("limit", self._default_limit))
        offset = int(call.arguments.get("offset", 0))
        if limit < 1 or limit > _MAX_LIMIT:
            raise RuntimeError(f"database limit must be between 1 and {_MAX_LIMIT}")
        if offset < 0:
            raise RuntimeError("database offset must be non-negative")
        statement = statement.limit(limit).offset(offset)

        with self._engine.connect() as connection:
            rows = connection.execute(statement).mappings().all()
        return [
            {
                column: _json_safe_value(row[column])
                for column in selected
            }
            for row in rows
        ]


def introspect_sqlalchemy_engine(
    engine: Any,
    *,
    database_name: str,
    namespace: str | None = None,
    schemas: tuple[str | None, ...] | list[str | None] | None = None,
    tables: set[str] | tuple[str, ...] | list[str] | None = None,
    include_views: bool = True,
    max_default_rows: int = 100,
    remote: bool = True,
) -> tuple[SQLAlchemyTableBinding, ...]:
    """Compile a caller-owned SQLAlchemy Engine into typed read-only capabilities.

    The Engine, URL, credentials, pools, and driver objects remain trusted process-local state.
    Only inspected relation/column metadata is copied into model-visible ToolSpec contracts.
    """

    if not database_name.strip():
        raise ValueError("database_name must be non-empty")
    if max_default_rows < 1 or max_default_rows > _MAX_LIMIT:
        raise ValueError(f"max_default_rows must be between 1 and {_MAX_LIMIT}")

    MetaData, Table, inspect, _ = _require_sqlalchemy()
    inspector = inspect(engine)

    selected_schemas = tuple(schemas) if schemas is not None else (None,)
    requested_tables = None if tables is None else {str(value) for value in tables}
    discovered_relations: list[tuple[str | None, str, str]] = []

    for schema in selected_schemas:
        for table in inspector.get_table_names(schema=schema):
            discovered_relations.append((schema, str(table), "table"))
        if include_views:
            for view in inspector.get_view_names(schema=schema):
                discovered_relations.append((schema, str(view), "view"))

    if requested_tables is not None:
        available = {
            f"{schema}.{table}" if schema else table
            for schema, table, _ in discovered_relations
        } | {table for _, table, _ in discovered_relations}
        missing = sorted(requested_tables - available)
        if missing:
            raise RegistrationError(
                "unknown database tables/views: " + ", ".join(missing)
            )

    multi_schema = len({schema for schema, _, _ in discovered_relations}) > 1
    bindings: list[SQLAlchemyTableBinding] = []
    used_names: set[str] = set()

    for schema, table_name, relation_kind in sorted(
        discovered_relations,
        key=lambda item: ((item[0] or ""), item[1], item[2]),
    ):
        qualified = f"{schema}.{table_name}" if schema else table_name
        if requested_tables is not None and (
            table_name not in requested_tables and qualified not in requested_tables
        ):
            continue

        columns = inspector.get_columns(table_name, schema=schema)
        if not columns:
            continue
        primary_key = (
            inspector.get_pk_constraint(table_name, schema=schema) or {}
            if relation_kind == "table"
            else {}
        )
        pk_columns = tuple(
            str(value)
            for value in (primary_key.get("constrained_columns") or ())
        )

        fields: list[FieldSpec] = []
        properties: dict[str, Any] = {}
        for column in columns:
            name = str(column["name"])
            nullable = bool(column.get("nullable", True))
            column_schema = _column_schema(
                column.get("type"),
                nullable=nullable,
            )
            fields.append(
                FieldSpec(
                    name=name,
                    description=f"{qualified} column {name}",
                    json_schema=column_schema,
                    aliases=[name.replace("_", " ")],
                    identifier=name in pk_columns,
                    source_type="database",
                )
            )
            properties[name] = column_schema

        row_schema: dict[str, Any] = {
            "type": "object",
            "properties": properties,
            "additionalProperties": False,
        }
        parameters = [
            ParameterSpec(
                name=name,
                description=f"Exact-match filter on primary-key column {name}",
                required=False,
                location="argument",
                json_schema=properties[name],
            )
            for name in pk_columns
            if name in properties
        ]
        parameters.extend(
            [
                ParameterSpec(
                    name="limit",
                    description="Maximum rows to return",
                    required=False,
                    location="argument",
                    json_schema={
                        "type": "integer",
                        "minimum": 1,
                        "maximum": _MAX_LIMIT,
                        "default": max_default_rows,
                    },
                ),
                ParameterSpec(
                    name="offset",
                    description="Rows to skip before returning results",
                    required=False,
                    location="argument",
                    json_schema={
                        "type": "integer",
                        "minimum": 0,
                        "default": 0,
                    },
                ),
            ]
        )

        metadata = MetaData()
        reflected = Table(
            table_name,
            metadata,
            schema=schema,
            autoload_with=engine,
        )

        endpoint = EndpointSpec(
            name=_SELECT_ENDPOINT,
            description=f"Read rows from {relation_kind} {qualified}",
            parameters=parameters,
            output_fields=fields,
            output_schema={"type": "array", "items": row_schema},
            server_projection=ServerProjectionSpec(
                parameter="fields",
                field_map={field.name: field.name for field in fields},
            ),
            read_only=True,
            destructive=False,
            execution_metadata={
                "database_family": "relational",
                "database_kind": "sqlalchemy",
                "database_object": relation_kind,
                "schema": schema,
                "table": table_name,
                "default_limit": max_default_rows,
            },
            metadata={
                "database_family": "relational",
                "database_kind": "sqlalchemy",
                "database_object": relation_kind,
                "schema": schema,
                "table": table_name,
            },
        )

        raw_name = f"{schema}_{table_name}" if multi_schema and schema else table_name
        tool_name = _slug(raw_name)
        if tool_name in used_names:
            tool_name = f"{tool_name}_{len(used_names) + 1}"
        used_names.add(tool_name)

        tool = ToolSpec(
            name=tool_name,
            namespace=namespace or _slug(database_name),
            description=f"Read-only database {relation_kind}: {qualified}",
            endpoints=[endpoint],
            source_type="database",
            provider=database_name,
            access_mode="sqlalchemy",
            remote=remote,
            execution_metadata={
                "adapter": "sqlalchemy_database",
                "database_family": "relational",
                "database_kind": "sqlalchemy",
                "schema": schema,
                "table": table_name,
            },
            metadata={
                "adapter": "sqlalchemy_database",
                "database_family": "relational",
                "database_kind": "sqlalchemy",
                "database_object": relation_kind,
                "schema": schema,
                "table": table_name,
            },
        )

        bindings.append(
            SQLAlchemyTableBinding(
                tool=tool,
                invoker=SQLAlchemyTableInvoker(
                    engine,
                    table=reflected,
                    columns=tuple(field.name for field in fields),
                    filter_columns=tuple(name for name in pk_columns if name in properties),
                    default_limit=max_default_rows,
                ),
            )
        )

    return tuple(bindings)
