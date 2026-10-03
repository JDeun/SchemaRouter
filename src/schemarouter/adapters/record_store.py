from __future__ import annotations

import inspect
import re
from collections.abc import Awaitable, Iterable
from dataclasses import dataclass
from typing import Any, Literal, Protocol

from pydantic import Field, model_validator

from ..errors import RegistrationError, SchemaValidationError
from ..models import EndpointSpec, FieldSpec, ParameterSpec, StrictModel, ToolCall, ToolSpec

_QUERY_ENDPOINT = "query"
_MAX_LIMIT = 1000
_RESERVED_ARGUMENTS = {"query", "limit", "start_time", "end_time"}

RecordModel = Literal["document", "search", "key_value", "time_series"]


class RecordFieldSpec(StrictModel):
    """One model-visible field discovered from a document/search/KV/time-series source."""

    name: str
    description: str = ""
    json_schema: dict[str, Any] = Field(default_factory=dict)
    identifier: bool = False
    filterable: bool = False

    @model_validator(mode="after")
    def validate_field(self) -> "RecordFieldSpec":
        if not self.name.strip():
            raise ValueError("record field name must be non-empty")
        return self


class RecordSourceSpec(StrictModel):
    """Provider-neutral schema descriptor for non-relational record stores."""

    name: str
    model: RecordModel
    description: str = ""
    fields: tuple[RecordFieldSpec, ...]
    supports_text_search: bool = False
    time_field: str | None = None
    public_metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_source(self) -> "RecordSourceSpec":
        if not self.name.strip():
            raise ValueError("record source name must be non-empty")
        names = [field.name for field in self.fields]
        if not names:
            raise ValueError("record source must expose at least one field")
        if len(names) != len(set(names)):
            raise ValueError("record source field names must be unique")
        if self.time_field is not None and self.time_field not in set(names):
            raise ValueError("record source time_field must reference a declared field")
        return self


class RecordStoreBackend(Protocol):
    """Trusted backend contract for document/search/key-value/time-series adapters."""

    def list_sources(
        self,
    ) -> Iterable[RecordSourceSpec] | Awaitable[Iterable[RecordSourceSpec]]: ...

    def query(
        self,
        *,
        source: str,
        text_query: str | None,
        filters: dict[str, Any],
        start_time: str | None,
        end_time: str | None,
        limit: int,
        include_fields: tuple[str, ...],
    ) -> list[dict[str, Any]] | Awaitable[list[dict[str, Any]]]: ...


def _slug(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9_]+", "_", value.strip()).strip("_").lower()
    return normalized or "source"


def _filter_parameter_name(field_name: str) -> str:
    return f"filter__{field_name}"


async def _await_if_needed(value: Any) -> Any:
    return await value if inspect.isawaitable(value) else value


@dataclass(frozen=True)
class RecordSourceBinding:
    tool: ToolSpec
    invoker: "RecordSourceInvoker"


class RecordSourceInvoker:
    """Bounded record-query invoker with trusted backend-owned execution."""

    projects_fields = True

    def __init__(
        self,
        backend: RecordStoreBackend,
        *,
        source: RecordSourceSpec,
        default_limit: int,
    ) -> None:
        self._backend = backend
        self._source = source
        self._default_limit = default_limit
        self._fields = tuple(field.name for field in source.fields)
        self._filterable = {
            _filter_parameter_name(field.name): field.name
            for field in source.fields
            if field.filterable or field.identifier
        }

    async def invoke_call(self, call: ToolCall) -> list[dict[str, Any]]:
        if call.endpoint != _QUERY_ENDPOINT:
            raise RuntimeError(f"unknown record-store endpoint: {call.endpoint!r}")

        text_query = call.arguments.get("query")
        if text_query is not None:
            if not self._source.supports_text_search:
                raise RuntimeError("text search is not enabled for this source")
            if not isinstance(text_query, str) or not text_query.strip():
                raise RuntimeError("query must be a non-empty string")

        filters = {
            field_name: call.arguments[parameter_name]
            for parameter_name, field_name in self._filterable.items()
            if parameter_name in call.arguments
        }

        start_time = call.arguments.get("start_time")
        end_time = call.arguments.get("end_time")
        if self._source.time_field is None and (
            start_time is not None or end_time is not None
        ):
            raise RuntimeError("time bounds are not enabled for this source")
        for label, value in (("start_time", start_time), ("end_time", end_time)):
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise RuntimeError(f"{label} must be a non-empty string")

        limit = int(call.arguments.get("limit", self._default_limit))
        if limit < 1 or limit > _MAX_LIMIT:
            raise RuntimeError(f"record-store limit must be between 1 and {_MAX_LIMIT}")

        selected_fields = tuple(call.fields) or self._fields
        unknown = sorted(set(selected_fields) - set(self._fields))
        if unknown:
            raise RuntimeError(
                "record-store query requested unknown fields: " + ", ".join(unknown)
            )

        raw_results = await _await_if_needed(
            self._backend.query(
                source=self._source.name,
                text_query=text_query if isinstance(text_query, str) else None,
                filters=filters,
                start_time=start_time if isinstance(start_time, str) else None,
                end_time=end_time if isinstance(end_time, str) else None,
                limit=limit,
                include_fields=selected_fields,
            )
        )
        if not isinstance(raw_results, list):
            raise SchemaValidationError("record-store backend query must return a list")

        selected = set(selected_fields)
        rows: list[dict[str, Any]] = []
        for index, raw in enumerate(raw_results):
            if not isinstance(raw, dict):
                raise SchemaValidationError(
                    f"record-store backend result {index} must be an object"
                )
            rows.append({key: value for key, value in raw.items() if key in selected})
        return rows


async def introspect_record_backend(
    backend: RecordStoreBackend,
    *,
    database_name: str,
    namespace: str | None = None,
    sources: set[str] | tuple[str, ...] | list[str] | None = None,
    default_limit: int = 100,
    remote: bool = True,
) -> tuple[RecordSourceBinding, ...]:
    """Compile non-relational source descriptors into typed bounded query capabilities."""

    if not database_name.strip():
        raise ValueError("database_name must be non-empty")
    if default_limit < 1 or default_limit > _MAX_LIMIT:
        raise ValueError(f"default_limit must be between 1 and {_MAX_LIMIT}")

    discovered_raw = await _await_if_needed(backend.list_sources())
    discovered = tuple(
        value if isinstance(value, RecordSourceSpec) else RecordSourceSpec.model_validate(value)
        for value in discovered_raw
    )
    names = [source.name for source in discovered]
    if len(names) != len(set(names)):
        raise RegistrationError("record-store backend returned duplicate source names")

    selected = None if sources is None else {str(value) for value in sources}
    if selected is not None:
        missing = sorted(selected - set(names))
        if missing:
            raise RegistrationError("unknown record-store sources: " + ", ".join(missing))

    bindings: list[RecordSourceBinding] = []
    used_names: set[str] = set()

    for source in discovered:
        if selected is not None and source.name not in selected:
            continue

        fields = [
            FieldSpec(
                name=field.name,
                description=field.description,
                json_schema=dict(field.json_schema),
                aliases=[field.name.replace("_", " ")],
                identifier=field.identifier,
                source_type="database",
            )
            for field in source.fields
        ]

        parameters: list[ParameterSpec] = []
        if source.supports_text_search:
            parameters.append(
                ParameterSpec(
                    name="query",
                    description="Plain-text search query interpreted by the trusted backend",
                    required=False,
                    location="argument",
                    json_schema={"type": "string", "minLength": 1},
                )
            )

        for field in source.fields:
            if field.filterable or field.identifier:
                parameters.append(
                    ParameterSpec(
                        name=_filter_parameter_name(field.name),
                        description=f"Exact-match filter on {field.name}",
                        required=False,
                        location="argument",
                        json_schema=dict(field.json_schema),
                    )
                )

        if source.time_field is not None:
            parameters.extend(
                [
                    ParameterSpec(
                        name="start_time",
                        description=f"Inclusive lower time bound for {source.time_field}",
                        required=False,
                        location="argument",
                        json_schema={"type": "string"},
                    ),
                    ParameterSpec(
                        name="end_time",
                        description=f"Exclusive upper time bound for {source.time_field}",
                        required=False,
                        location="argument",
                        json_schema={"type": "string"},
                    ),
                ]
            )

        parameters.append(
            ParameterSpec(
                name="limit",
                description="Maximum records to return",
                required=False,
                location="argument",
                json_schema={
                    "type": "integer",
                    "minimum": 1,
                    "maximum": _MAX_LIMIT,
                    "default": default_limit,
                },
            )
        )

        endpoint = EndpointSpec(
            name=_QUERY_ENDPOINT,
            description=f"Bounded query over {source.model} source {source.name}",
            parameters=parameters,
            output_fields=fields,
            output_schema={
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        field.name: field.json_schema or {}
                        for field in fields
                    },
                    "additionalProperties": False,
                },
            },
            read_only=True,
            destructive=False,
            execution_metadata={
                "database_family": "record",
                "record_model": source.model,
                "source": source.name,
                "time_field": source.time_field,
                "default_limit": default_limit,
            },
            metadata={
                "database_family": "record",
                "record_model": source.model,
                "source": source.name,
                "supports_text_search": source.supports_text_search,
                "time_field": source.time_field,
                "public_metadata": dict(source.public_metadata),
            },
        )

        tool_name = _slug(source.name)
        if tool_name in used_names:
            tool_name = f"{tool_name}_{len(used_names) + 1}"
        used_names.add(tool_name)

        tool = ToolSpec(
            name=tool_name,
            namespace=namespace or _slug(database_name),
            description=source.description or f"{source.model} source {source.name}",
            endpoints=[endpoint],
            source_type="database",
            provider=database_name,
            access_mode="record",
            remote=remote,
            execution_metadata={
                "adapter": "record_store",
                "database_family": "record",
                "record_model": source.model,
                "source": source.name,
            },
            metadata={
                "adapter": "record_store",
                "database_family": "record",
                "record_model": source.model,
                "source": source.name,
            },
        )
        bindings.append(
            RecordSourceBinding(
                tool=tool,
                invoker=RecordSourceInvoker(
                    backend,
                    source=source,
                    default_limit=default_limit,
                ),
            )
        )

    return tuple(bindings)
