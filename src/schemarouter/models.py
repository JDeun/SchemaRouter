from __future__ import annotations

import hashlib
import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

_REMOTE_ADAPTERS = {"mcp", "openapi", "optimade", "html_proposal"}
_LEGACY_ENDPOINT_EXECUTION_METADATA_KEYS = {
    "callable_module",
    "callable_name",
    "entry_type",
    "field_projection",
    "mode",
    "request_body_discriminator",
    "request_body_mode",
    "request_body_required",
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


_LEGACY_TOOL_EXECUTION_METADATA_KEYS = {
    "adapter",
    "approved_base_url",
    "authenticated_transport",
    "execution_bound",
    "executable",
    "protocol_version",
    "requires_explicit_base_url",
    "resolved_schema_url",
    "source_url",
    "suggested_base_url",
    "versioned_base_url",
}


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


class FieldSpec(StrictModel):
    name: str
    description: str = ""
    json_schema: dict[str, Any] = Field(default_factory=dict)
    aliases: list[str] = Field(default_factory=list)
    path: list[str] = Field(default_factory=list)
    unit: str | None = None
    identifier: bool = False
    source_type: str | None = None
    license: str | None = None

    @model_validator(mode="after")
    def validate_path(self) -> FieldSpec:
        if any(not isinstance(part, str) or not part for part in self.path):
            raise ValueError("field path requires non-empty string segments")
        return self

    @property
    def projection_path(self) -> tuple[str, ...]:
        return tuple(self.path or [self.name])


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
        execution_metadata = {
            key: metadata[key]
            for key in _LEGACY_ENDPOINT_EXECUTION_METADATA_KEYS
            if key in metadata
        }
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
        execution_metadata = {
            key: metadata[key]
            for key in _LEGACY_TOOL_EXECUTION_METADATA_KEYS
            if key in metadata
        }
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


class PlanRequest(StrictModel):
    query: str
    concepts: list[str] = Field(default_factory=list)
    preferred_tools: list[str] = Field(default_factory=list)
    arguments: dict[str, Any] = Field(default_factory=dict)
    evidence: EvidenceRequirements = Field(default_factory=EvidenceRequirements)
    max_calls: int = Field(default=1, ge=1, le=32)


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


class ExecutionPlan(StrictModel):
    query: str
    registry_version: int
    calls: list[ToolCall] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @property
    def executable(self) -> bool:
        return bool(self.calls) and all(call.executable for call in self.calls)


class ToolResult(StrictModel):
    tool: str
    endpoint: str
    data: Any
    projected_fields: list[str] = Field(default_factory=list)
