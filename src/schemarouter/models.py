from __future__ import annotations

import hashlib
import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class ParameterSpec(StrictModel):
    name: str
    description: str = ""
    required: bool = False
    location: Literal["path", "query", "header", "body", "argument"] = "argument"
    json_schema: dict[str, Any] = Field(default_factory=dict)
    aliases: list[str] = Field(default_factory=list)


class FieldSpec(StrictModel):
    name: str
    description: str = ""
    json_schema: dict[str, Any] = Field(default_factory=dict)
    aliases: list[str] = Field(default_factory=list)
    unit: str | None = None
    identifier: bool = False
    source_type: str | None = None
    license: str | None = None


class EndpointSpec(StrictModel):
    name: str
    description: str = ""
    parameters: list[ParameterSpec] = Field(default_factory=list)
    output_fields: list[FieldSpec] = Field(default_factory=list)
    method: str | None = None
    path: str | None = None
    read_only: bool | None = None
    destructive: bool | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_unique_names(self) -> "EndpointSpec":
        pnames = [p.name for p in self.parameters]
        fnames = [f.name for f in self.output_fields]
        if len(pnames) != len(set(pnames)):
            raise ValueError(f"duplicate parameter name in endpoint {self.name!r}")
        if len(fnames) != len(set(fnames)):
            raise ValueError(f"duplicate output field name in endpoint {self.name!r}")
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
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_endpoints(self) -> "ToolSpec":
        names = [e.name for e in self.endpoints]
        if not names:
            raise ValueError("tool must define at least one endpoint")
        if len(names) != len(set(names)):
            raise ValueError(f"duplicate endpoint name in tool {self.name!r}")
        return self

    @property
    def key(self) -> str:
        return f"{self.namespace}.{self.name}" if self.namespace else self.name

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
    arguments: dict[str, Any] = Field(default_factory=dict)
    evidence: EvidenceRequirements = Field(default_factory=EvidenceRequirements)


class PlanRequest(StrictModel):
    query: str
    concepts: list[str] = Field(default_factory=list)
    preferred_tools: list[str] = Field(default_factory=list)
    arguments: dict[str, Any] = Field(default_factory=dict)
    evidence: EvidenceRequirements = Field(default_factory=EvidenceRequirements)
    max_calls: int = Field(default=1, ge=1, le=32)


class ToolCall(StrictModel):
    tool: str
    endpoint: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    fields: list[str] = Field(default_factory=list)
    evidence: EvidenceRequirements = Field(default_factory=EvidenceRequirements)
    schema_fingerprint: str
    missing_required_arguments: list[str] = Field(default_factory=list)
    score: float = 0.0

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
