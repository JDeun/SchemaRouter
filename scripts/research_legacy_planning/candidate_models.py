"""Historical full-schema lexical candidate receipts (source checkout only)."""

from __future__ import annotations

from typing import Any

from pydantic import Field

from schemarouter.models import (
    CandidateSelectionSource,
    FieldSpec,
    ParameterSpec,
    ScoreComponent,
    StrictModel,
)


class CapabilityCandidate(StrictModel):
    """One ranked registered capability returned without execution."""

    rank: int = Field(ge=1)
    route_id: str
    tool: str
    endpoint: str
    tool_description: str = ""
    endpoint_description: str = ""
    score: float
    matched_fields: list[str] = Field(default_factory=list)
    score_components: list[ScoreComponent] = Field(default_factory=list)
    selection_source: CandidateSelectionSource = "deterministic"
    parameters: list[ParameterSpec] = Field(default_factory=list)
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_fields: list[FieldSpec] = Field(default_factory=list)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    read_only: bool | None = None
    destructive: bool | None = None
    source_type: str | None = None
    license: str | None = None
    provider: str | None = None
    access_mode: str | None = None
    tool_fingerprint: str
    endpoint_fingerprint: str


class CapabilityRetrieval(StrictModel):
    """Ordered Top-K capability retrieval result for downstream selection."""

    query: str
    registry_version: int
    requested_k: int = Field(ge=1)
    total_ranked: int = Field(ge=0)
    executable_only: bool = False
    candidates: list[CapabilityCandidate] = Field(default_factory=list)
