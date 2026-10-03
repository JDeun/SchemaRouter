from __future__ import annotations

import base64
import re
import sqlite3
from dataclasses import dataclass
from hashlib import sha256
from typing import Any

from ..errors import RegistrationError
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


def _quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _slug(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9_]+", "_", value.strip()).strip("_").lower()
    return normalized or "table"


def _nullable(schema: dict[str, Any], *, not_null: bool) -> dict[str, Any]:
    if not_null or "type" not in schema:
        return schema
    result = dict(schema)
    declared = result["type"]
    if isinstance(declared, str):
        result["type"] = [declared, "null"]
    return result


def _sqlite_column_schema(declared_type: str, *, not_null: bool) -> dict[str, Any]:
    value = declared_type.strip().upper()
    if "INT" in value:
        return _nullable({"type": "integer"}, not_null=not_null)
    if any(marker in value for marker in ("CHAR", "CLOB", "TEXT")):
        return _nullable({"type": "string"}, not_null=not_null)
    if "BLOB" in value:
        return _nullable(
            {"type": "string", "contentEncoding": "base64"},
            not_null=not_null,
        )
    if any(marker in value for marker in ("REAL", "FLOA", "DOUB")):
        return _nullable({"type": "number"}, not_null=not_null)
    if any(marker in value for marker in ("DATE", "TIME")):
        return _nullable({"type": "string"}, not_null=not_null)
    # NUMERIC affinity may surface as int, float, text, or null depending on stored values.
    # Leave it unconstrained rather than overclaiming a stable runtime type.
    return {}


def _json_safe_value(value: Any) -> Any:
    if isinstance(value, bytes):
        return base64.b64encode(value).decode("ascii")
    return value


@dataclass(frozen=True)
class SQLiteTableBinding:
    """One introspected SQLite table/view and its trusted read-only invoker."""

    tool: ToolSpec
    invoker: SQLiteTableInvoker


class SQLiteTableInvoker:
    """Read-only call-aware invoker for one introspected SQLite table or view."""

    projects_fields = True

    def __init__(
        self,
        connection: sqlite3.Connection,
        *,
        table: str,
        columns: tuple[str, ...],
        filter_columns: tuple[str, ...],
    ) -> None:
        self._connection = connection
        self._table = table
        self._columns = columns
        self._filter_columns = filter_columns

    def invoke_call(self, call: ToolCall) -> list[dict[str, Any]]:
        if call.endpoint != _SELECT_ENDPOINT:
            raise RuntimeError(f"unknown SQLite endpoint: {call.endpoint!r}")

        selected = tuple(call.fields) or self._columns
        unknown = sorted(set(selected) - set(self._columns))
        if unknown:
            raise RuntimeError(
                "SQLite selection requested unknown fields: " + ", ".join(unknown)
            )

        where_parts: list[str] = []
        values: list[Any] = []
        for column in self._filter_columns:
            if column not in call.arguments:
                continue
            where_parts.append(f"{_quote_identifier(column)} = ?")
            values.append(call.arguments[column])

        limit = int(call.arguments.get("limit", 100))
        offset = int(call.arguments.get("offset", 0))
        if limit < 1 or limit > _MAX_LIMIT:
            raise RuntimeError(f"SQLite limit must be between 1 and {_MAX_LIMIT}")
        if offset < 0:
            raise RuntimeError("SQLite offset must be non-negative")

        projection = ", ".join(_quote_identifier(column) for column in selected)
        query = f"SELECT {projection} FROM {_quote_identifier(self._table)}"
        if where_parts:
            query += " WHERE " + " AND ".join(where_parts)
        query += " LIMIT ? OFFSET ?"
        values.extend([limit, offset])

        cursor = self._connection.execute(query, values)
        rows = cursor.fetchall()
        return [
            {
                column: _json_safe_value(value)
                for column, value in zip(selected, row, strict=True)
            }
            for row in rows
        ]


def _sqlite_table_rows(
    connection: sqlite3.Connection,
) -> list[tuple[str, str]]:
    rows = connection.execute(
        """
        SELECT name, type
        FROM sqlite_master
        WHERE type IN ('table', 'view')
          AND name NOT LIKE 'sqlite_%'
        ORDER BY name
        """
    ).fetchall()
    return [(str(name), str(kind)) for name, kind in rows]


def _table_info(
    connection: sqlite3.Connection,
    table: str,
) -> list[tuple[int, str, str, int, Any, int]]:
    cursor = connection.execute(
        f"PRAGMA table_info({_quote_identifier(table)})"
    )
    rows = cursor.fetchall()
    return [
        (
            int(cid),
            str(name),
            str(declared_type or ""),
            int(not_null),
            default_value,
            int(primary_key),
        )
        for cid, name, declared_type, not_null, default_value, primary_key in rows
    ]


def introspect_sqlite_database(
    connection: sqlite3.Connection,
    *,
    database_name: str = "sqlite",
    namespace: str | None = None,
    tables: set[str] | tuple[str, ...] | list[str] | None = None,
    max_default_rows: int = 100,
) -> tuple[SQLiteTableBinding, ...]:
    """Compile a caller-owned SQLite database into typed read-only capabilities.

    The database connection remains caller-owned. Schema introspection never persists the
    connection, path, credentials, or query results. One ToolSpec is emitted per selected
    table/view and the trusted invoker only supports bounded projected SELECT operations.
    """

    if not isinstance(connection, sqlite3.Connection):
        raise TypeError("connection must be sqlite3.Connection")
    if not database_name.strip():
        raise ValueError("database_name must be non-empty")
    if max_default_rows < 1 or max_default_rows > _MAX_LIMIT:
        raise ValueError(f"max_default_rows must be between 1 and {_MAX_LIMIT}")

    discovered = _sqlite_table_rows(connection)
    available = {name for name, _ in discovered}
    selected_tables = None if tables is None else {str(value) for value in tables}
    if selected_tables is not None:
        missing = sorted(selected_tables - available)
        if missing:
            raise RegistrationError(
                "unknown SQLite tables/views: " + ", ".join(missing)
            )

    bindings: list[SQLiteTableBinding] = []
    used_names: set[str] = set()
    for table, object_type in discovered:
        if selected_tables is not None and table not in selected_tables:
            continue

        info = _table_info(connection, table)
        if not info:
            continue

        fields: list[FieldSpec] = []
        properties: dict[str, Any] = {}
        primary_keys: list[tuple[int, str]] = []
        for _, column, declared_type, not_null, _, primary_key in info:
            schema = _sqlite_column_schema(
                declared_type,
                not_null=bool(not_null or primary_key),
            )
            fields.append(
                FieldSpec(
                    name=column,
                    description=f"SQLite {object_type} column {column}",
                    json_schema=schema,
                    aliases=[column.replace("_", " ")],
                    identifier=bool(primary_key),
                    source_type="database",
                )
            )
            properties[column] = schema
            if primary_key:
                primary_keys.append((primary_key, column))

        row_schema: dict[str, Any] = {
            "type": "object",
            "properties": properties,
            "additionalProperties": False,
        }
        filter_columns = tuple(
            column for _, column in sorted(primary_keys)
        )
        parameters = [
            ParameterSpec(
                name=column,
                description=f"Exact-match filter on primary-key column {column}",
                required=False,
                location="argument",
                json_schema=properties[column],
            )
            for column in filter_columns
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

        endpoint = EndpointSpec(
            name=_SELECT_ENDPOINT,
            description=f"Read rows from SQLite {object_type} {table}",
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
                "database_kind": "sqlite",
                "database_object": object_type,
                "table": table,
                "default_limit": max_default_rows,
            },
            metadata={
                "database_family": "relational",
                "database_kind": "sqlite",
                "database_object": object_type,
                "table": table,
            },
        )

        tool_name = _slug(table)
        if tool_name in used_names:
            digest = sha256(table.encode("utf-8")).hexdigest()[:8]
            tool_name = f"{tool_name}_{digest}"
        used_names.add(tool_name)

        tool = ToolSpec(
            name=tool_name,
            namespace=namespace or _slug(database_name),
            description=f"Read-only SQLite {object_type}: {table}",
            endpoints=[endpoint],
            source_type="database",
            provider=database_name,
            access_mode="sqlite",
            remote=False,
            execution_metadata={
                "adapter": "sqlite_database",
                "database_family": "relational",
                "database_kind": "sqlite",
                "table": table,
            },
            metadata={
                "adapter": "sqlite_database",
                "database_family": "relational",
                "database_kind": "sqlite",
                "database_object": object_type,
                "table": table,
            },
        )
        bindings.append(
            SQLiteTableBinding(
                tool=tool,
                invoker=SQLiteTableInvoker(
                    connection,
                    table=table,
                    columns=tuple(field.name for field in fields),
                    filter_columns=filter_columns,
                ),
            )
        )

    return tuple(bindings)
