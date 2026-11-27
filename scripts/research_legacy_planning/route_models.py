"""Historical lightweight lexical route DTOs (source checkout only)."""

from __future__ import annotations

from pydantic import Field

from schemarouter.models import StrictModel
from scripts.research_legacy_planning.plan_models import CandidateSelectionSource, ScoreComponent


class CapabilityRouteCandidate(StrictModel):
    """One lightweight ranked route reference returned without schema materialization."""

    rank: int = Field(ge=1)
    route_id: str
    tool: str
    endpoint: str
    score: float
    matched_fields: list[str] = Field(default_factory=list)
    score_components: list[ScoreComponent] = Field(default_factory=list)
    selection_source: CandidateSelectionSource = "deterministic"
    read_only: bool | None = None
    destructive: bool | None = None
    provider: str | None = None
    access_mode: str | None = None
    tool_fingerprint: str
    endpoint_fingerprint: str


class CapabilityRouteRetrieval(StrictModel):
    """Ordered Top-K lightweight route references for downstream preselection."""

    query: str
    registry_version: int
    requested_k: int = Field(ge=1)
    total_ranked: int = Field(ge=0)
    executable_only: bool = False
    candidates: list[CapabilityRouteCandidate] = Field(default_factory=list)
