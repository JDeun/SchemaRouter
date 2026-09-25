from __future__ import annotations

import hashlib
import json
import math
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

_REMOTE_ADAPTERS = {"mcp", "openapi", "optimade", "html_proposal"}
_OPENAPI_ENDPOINT_RUNTIME_KEYS = {
    "request_body_discriminator",
    "request_body_mode",
    "request_body_required",
}
_OPTIMADE_ENDPOINT_RUNTIME_KEYS = {"entry_type", "field_projection", "mode"}
_PYTHON_ENDPOINT_RUNTIME_KEYS = {"callable_module", "callable_name"}
_TOOL_RUNTIME_KEYS_BY_ADAPTER = {
    "openapi": {
        "adapter",
        "approved_base_url",
        "execution_bound",
        "requires_explicit_base_url",
    },
    "mcp": {
        "adapter",
        "authenticated_transport",
        "protocol_version",
        "source_url",
    },
    "optimade": {
        "adapter",
        "api_version",
        "versioned_base_url",
    },
    "html_proposal": {
        "adapter",
        "approved_base_url",
        "executable",
    },
    "python": {"adapter"},
}


def _validate_execution_metadata(value: dict[str, Any]) -> None:
    try:
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        )
    except ValueError as exc:
        raise ValueError(
            "execution_metadata must contain only finite JSON numbers"
        ) from exc
    except TypeError as exc:
        raise ValueError(
            "execution_metadata must contain only JSON-safe values"
        ) from exc


def _legacy_endpoint_execution_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    keys: set[str] = set()
    if any(key in metadata for key in _OPENAPI_ENDPOINT_RUNTIME_KEYS):
        keys.update(_OPENAPI_ENDPOINT_RUNTIME_KEYS)
    if "entry_type" in metadata or "field_projection" in metadata:
        keys.update(_OPTIMADE_ENDPOINT_RUNTIME_KEYS)
    if "callable_module" in metadata or "callable_name" in metadata:
        keys.update(_PYTHON_ENDPOINT_RUNTIME_KEYS)
    return {key: metadata[key] for key in keys if key in metadata}


def _legacy_tool_execution_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    adapter = metadata.get("adapter")
    if not isinstance(adapter, str):
        return {}
    keys = _TOOL_RUNTIME_KEYS_BY_ADAPTER.get(adapter)
    if keys is None:
        return {}
    return {key: metadata[key] for key in keys if key in metadata}



class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class ParameterSpec(StrictModel):
    name: str
    wire_name: str | None = None
    description: str = ""
    required: bool = False
    location: Literal["path", "query", "header", "body", "body_root", "argument"] = "argument"
    style: str | None = None
    explode: bool | None = None
    allow_reserved: bool = False
    json_schema: dict[str, Any] = Field(default_factory=dict)
    aliases: list[str] = Field(default_factory=list)


class ServerProjectionSpec(StrictModel):
    """Trusted contract for server-side response-field selection."""

    parameter: str
    separator: str = ","
    field_map: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_projection(self) -> ServerProjectionSpec:
        if not self.parameter.strip():
            raise ValueError("server projection parameter must be non-empty")
        if not self.separator:
            raise ValueError("server projection separator must be non-empty")
        if any(not key or not value for key, value in self.field_map.items()):
            raise ValueError("server projection field_map requires non-empty keys and values")
        return self

    def selector_for(self, field: FieldSpec) -> str:
        return self.field_map.get(field.name, field.name)


class UnitNormalizationSpec(StrictModel):
    """Explicit affine conversion from a provider unit to one canonical unit.

    The runtime never infers conversion factors from unit strings. Adapters/applications must
    declare the conversion contract locally.

    canonical_value = source_value * scale + offset
    """

    dimension: str
    canonical_unit: str
    scale: float = 1.0
    offset: float = 0.0

    @model_validator(mode="after")
    def validate_unit_normalization(self) -> UnitNormalizationSpec:
        if not self.dimension.strip():
            raise ValueError("unit normalization dimension must be non-empty")
        if not self.canonical_unit.strip():
            raise ValueError("unit normalization canonical_unit must be non-empty")
        if not math.isfinite(self.scale) or self.scale <= 0:
            raise ValueError("unit normalization scale must be finite and positive")
        if not math.isfinite(self.offset):
            raise ValueError("unit normalization offset must be finite")
        return self


class ResultFieldContract(StrictModel):
    """Minimal field contract carried with a projected ToolResult."""

    semantic_id: str | None = None
    json_schema: dict[str, Any] = Field(default_factory=dict)
    source_unit: str | None = None
    unit: str | None = None
    dimension: str | None = None


class FieldSpec(StrictModel):
    name: str
    semantic_id: str | None = None
    description: str = ""
    json_schema: dict[str, Any] = Field(default_factory=dict)
    aliases: list[str] = Field(default_factory=list)
    path: list[str] = Field(default_factory=list)
    result_path: list[str] = Field(default_factory=list)
    unit: str | None = None
    unit_normalization: UnitNormalizationSpec | None = None
    identifier: bool = False
    source_type: str | None = None
    license: str | None = None

    @model_validator(mode="after")
    def validate_path(self) -> FieldSpec:
        if self.semantic_id is not None and not self.semantic_id.strip():
            raise ValueError("field semantic_id must be non-empty when provided")
        if any(not isinstance(part, str) or not part for part in self.path):
            raise ValueError("field path requires non-empty string segments")
        if any(not isinstance(part, str) or not part for part in self.result_path):
            raise ValueError("field result_path requires non-empty string segments")
        if self.unit_normalization is not None and self.unit is None:
            raise ValueError(
                "unit_normalization requires the provider source unit in field.unit"
            )
        explicit_type = self.json_schema.get("type")
        if self.unit is not None and explicit_type is not None:
            allowed = (
                set(explicit_type)
                if isinstance(explicit_type, list)
                else {explicit_type}
            )
            allowed.discard("null")
            numeric_scalar = bool(allowed) and allowed <= {"number", "integer"}
            numeric_array = False
            if allowed == {"array"}:
                items = self.json_schema.get("items")
                if isinstance(items, dict):
                    item_type = items.get("type")
                    item_types = (
                        set(item_type)
                        if isinstance(item_type, list)
                        else {item_type}
                    )
                    item_types.discard("null")
                    numeric_array = bool(item_types) and item_types <= {
                        "number",
                        "integer",
                    }
            if not numeric_scalar and not numeric_array:
                raise ValueError(
                    "a field with unit metadata must declare a numeric scalar or numeric-array "
                    "json_schema type"
                )
        return self

    @property
    def projection_path(self) -> tuple[str, ...]:
        return tuple(self.path or [self.name])

    @property
    def result_projection_path(self) -> tuple[str, ...]:
        return tuple(self.result_path or self.projection_path)


class EndpointSpec(StrictModel):
    name: str
    description: str = ""
    parameters: list[ParameterSpec] = Field(default_factory=list)
    output_fields: list[FieldSpec] = Field(default_factory=list)
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    method: str | None = None
    path: str | None = None
    read_only: bool | None = None
    destructive: bool | None = None
    server_projection: ServerProjectionSpec | None = None
    execution_metadata: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def migrate_legacy_execution_metadata(cls, value: Any) -> Any:
        if not isinstance(value, dict) or "execution_metadata" in value:
            return value
        metadata = value.get("metadata")
        if not isinstance(metadata, dict):
            return value
        execution_metadata = _legacy_endpoint_execution_metadata(metadata)
        if not execution_metadata:
            return value
        migrated = dict(value)
        migrated["execution_metadata"] = execution_metadata
        return migrated

    @model_validator(mode="after")
    def validate_unique_names(self) -> EndpointSpec:
        _validate_execution_metadata(self.execution_metadata)
        pnames = [p.name for p in self.parameters]
        fnames = [f.name for f in self.output_fields]
        if len(pnames) != len(set(pnames)):
            raise ValueError(f"duplicate parameter name in endpoint {self.name!r}")
        if len(fnames) != len(set(fnames)):
            raise ValueError(f"duplicate output field name in endpoint {self.name!r}")

        if self.server_projection is not None:
            remapped_source_fields = [
                field.name
                for field in self.output_fields
                if field.projection_path != (field.name,)
            ]
            if remapped_source_fields and not self.output_schema:
                raise ValueError(
                    "server projection with provider-specific field paths requires an explicit "
                    "output_schema in endpoint "
                    f"{self.name!r}: " + ", ".join(sorted(remapped_source_fields))
                )

            unknown_projection_fields = sorted(
                set(self.server_projection.field_map) - set(fnames)
            )
            if unknown_projection_fields:
                raise ValueError(
                    "server projection field_map contains undeclared output fields in endpoint "
                    f"{self.name!r}: " + ", ".join(unknown_projection_fields)
                )

            projection_parameter = self.server_projection.parameter
            conflicting_parameters = [
                parameter
                for parameter in self.parameters
                if (parameter.wire_name or parameter.name) == projection_parameter
                and parameter.location != "query"
            ]
            if conflicting_parameters:
                raise ValueError(
                    "server projection parameter conflicts with a non-query parameter in endpoint "
                    f"{self.name!r}: {projection_parameter!r}"
                )

        paths = [(field.name, field.projection_path) for field in self.output_fields]
        if len({path for _, path in paths}) != len(paths):
            raise ValueError(f"duplicate output field path in endpoint {self.name!r}")
        for index, (left_name, left_path) in enumerate(paths):
            for right_name, right_path in paths[index + 1 :]:
                shorter, longer = (
                    (left_path, right_path)
                    if len(left_path) <= len(right_path)
                    else (right_path, left_path)
                )
                if longer[: len(shorter)] == shorter:
                    raise ValueError(
                        "overlapping output field paths in endpoint "
                        f"{self.name!r}: {left_name!r} and {right_name!r}"
                    )

        result_paths = [
            (field.name, field.result_projection_path)
            for field in self.output_fields
        ]
        if len({path for _, path in result_paths}) != len(result_paths):
            raise ValueError(f"duplicate output result path in endpoint {self.name!r}")
        for index, (left_name, left_path) in enumerate(result_paths):
            for right_name, right_path in result_paths[index + 1 :]:
                shorter, longer = (
                    (left_path, right_path)
                    if len(left_path) <= len(right_path)
                    else (right_path, left_path)
                )
                if longer[: len(shorter)] == shorter:
                    raise ValueError(
                        "overlapping output result paths in endpoint "
                        f"{self.name!r}: {left_name!r} and {right_name!r}"
                    )
        return self

    @property
    def fingerprint(self) -> str:
        payload = self.model_dump(mode="json", exclude={"metadata"})
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class ToolSpec(StrictModel):
    name: str
    namespace: str | None = None
    description: str = ""
    endpoints: list[EndpointSpec]
    source_type: str | None = None
    license: str | None = None
    provider: str | None = None
    access_mode: str | None = None
    remote: bool = False
    execution_metadata: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def migrate_legacy_execution_metadata(cls, value: Any) -> Any:
        if not isinstance(value, dict) or "execution_metadata" in value:
            return value
        metadata = value.get("metadata")
        if not isinstance(metadata, dict):
            return value
        execution_metadata = _legacy_tool_execution_metadata(metadata)
        if not execution_metadata:
            return value
        migrated = dict(value)
        migrated["execution_metadata"] = execution_metadata
        return migrated

    @model_validator(mode="before")
    @classmethod
    def migrate_legacy_remote_classification(cls, value: Any) -> Any:
        if not isinstance(value, dict) or "remote" in value:
            return value
        metadata = value.get("metadata")
        if not isinstance(metadata, dict):
            return value
        adapter = metadata.get("adapter")
        if not (bool(metadata.get("remote")) or adapter in _REMOTE_ADAPTERS):
            return value
        migrated = dict(value)
        migrated["remote"] = True
        return migrated

    @model_validator(mode="after")
    def validate_endpoints(self) -> ToolSpec:
        _validate_execution_metadata(self.execution_metadata)
        if self.provider is not None and not self.provider.strip():
            raise ValueError("tool provider must be non-empty when provided")
        if self.access_mode is not None and not self.access_mode.strip():
            raise ValueError("tool access_mode must be non-empty when provided")
        names = [e.name for e in self.endpoints]
        if not names:
            raise ValueError("tool must define at least one endpoint")
        if len(names) != len(set(names)):
            raise ValueError(f"duplicate endpoint name in tool {self.name!r}")
        return self

    @property
    def key(self) -> str:
        return f"{self.namespace}.{self.name}" if self.namespace else self.name

    @property
    def fingerprint(self) -> str:
        payload = self.model_dump(
            mode="json",
            exclude={"metadata", "endpoints"},
        )
        payload["endpoints"] = [
            endpoint.model_dump(mode="json", exclude={"metadata"})
            for endpoint in self.endpoints
        ]
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def endpoint(self, name: str) -> EndpointSpec:
        for endpoint in self.endpoints:
            if endpoint.name == name:
                return endpoint
        raise KeyError(name)


class EvidenceRequirements(StrictModel):
    provenance: bool = False
    license: bool = False
    units: bool = False
    source_type: str | None = None


class QueryIntent(StrictModel):
    concepts: list[str] = Field(default_factory=list)
    preferred_tools: list[str] = Field(default_factory=list)
    preferred_endpoints: list[str] = Field(default_factory=list)
    arguments: dict[str, Any] = Field(default_factory=dict)
    evidence: EvidenceRequirements = Field(default_factory=EvidenceRequirements)


FallbackScope = Literal["disabled", "same_provider", "cross_provider"]


class PlanRequest(StrictModel):
    query: str
    concepts: list[str] = Field(default_factory=list)
    preferred_tools: list[str] = Field(default_factory=list)
    arguments: dict[str, Any] = Field(default_factory=dict)
    evidence: EvidenceRequirements = Field(default_factory=EvidenceRequirements)
    max_calls: int = Field(default=1, ge=1, le=32)
    fallback_scope: FallbackScope = "disabled"
    max_fallbacks: int = Field(default=2, ge=0, le=8)


class ScoreComponent(StrictModel):
    """One deterministic contribution to candidate ranking."""

    kind: str
    value: float
    matched: str | None = None


FieldSelectionReason = Literal[
    "identifier",
    "field_exact",
    "field_lexical",
    "field_substring",
    "recall_fallback",
    "decision_backend",
]
CandidateSelectionSource = Literal[
    "deterministic",
    "decision_backend",
    "decision_recall",
]


class FieldSelectionExplanation(StrictModel):
    """Machine-readable reason a declared output field is retained."""

    field: str
    reason: FieldSelectionReason


class PlanExplanation(StrictModel):
    """Auditable structural explanation for one planned call.

    This records locally observable routing signals, not model chain-of-thought.
    """

    candidate_selection: CandidateSelectionSource = "deterministic"
    score_components: list[ScoreComponent] = Field(default_factory=list)
    field_selection: list[FieldSelectionExplanation] = Field(default_factory=list)
    ignored_arguments: list[str] = Field(default_factory=list)


class ToolCall(StrictModel):
    tool: str
    endpoint: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    fields: list[str] = Field(default_factory=list)
    evidence: EvidenceRequirements = Field(default_factory=EvidenceRequirements)
    schema_fingerprint: str
    tool_fingerprint: str | None = None
    missing_required_arguments: list[str] = Field(default_factory=list)
    score: float = 0.0
    explanation: PlanExplanation | None = None

    @property
    def executable(self) -> bool:
        return not self.missing_required_arguments


class FallbackRoute(StrictModel):
    """Precompiled alternatives for one primary call in an ExecutionPlan."""

    primary_call_index: int = Field(ge=0)
    alternatives: list[ToolCall] = Field(default_factory=list)


class ExecutionPlan(StrictModel):
    query: str
    registry_version: int
    calls: list[ToolCall] = Field(default_factory=list)
    fallback_routes: list[FallbackRoute] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_fallback_routes(self) -> ExecutionPlan:
        seen: set[int] = set()
        for route in self.fallback_routes:
            if route.primary_call_index >= len(self.calls):
                raise ValueError("fallback route primary_call_index is outside plan.calls")
            if route.primary_call_index in seen:
                raise ValueError("duplicate fallback route for primary call index")
            seen.add(route.primary_call_index)
        return self

    @property
    def executable(self) -> bool:
        return bool(self.calls) and all(call.executable for call in self.calls)

    def fallback_route(self, primary_call_index: int) -> FallbackRoute | None:
        return next(
            (
                route
                for route in self.fallback_routes
                if route.primary_call_index == primary_call_index
            ),
            None,
        )


class ToolResult(StrictModel):
    tool: str
    endpoint: str
    data: Any
    projected_fields: list[str] = Field(default_factory=list)
    field_contracts: dict[str, ResultFieldContract] = Field(default_factory=dict)
