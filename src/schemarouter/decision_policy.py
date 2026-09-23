from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

DecisionFallback = Literal["deterministic", "error"]
CandidateAbstention = Literal["deterministic", "no_route", "error"]


class DecisionPolicy(BaseModel):
    """Opt-in controls for experimental bounded-decision assistance."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    enabled: bool = False
    tool_selection: bool = False
    endpoint_selection: bool = False
    field_selection: bool = False
    evidence_sufficiency: bool = False
    recall_on_empty: bool = False
    candidate_abstention: CandidateAbstention = "deterministic"
    fallback: DecisionFallback = "deterministic"

    @property
    def candidate_selection_enabled(self) -> bool:
        return self.enabled and (self.tool_selection or self.endpoint_selection)

    @property
    def candidate_recall_on_empty_enabled(self) -> bool:
        return self.candidate_selection_enabled and self.recall_on_empty

    @property
    def field_selection_enabled(self) -> bool:
        return self.enabled and self.field_selection

    @property
    def evidence_sufficiency_enabled(self) -> bool:
        return self.enabled and self.evidence_sufficiency

    @property
    def reserved_surfaces_enabled(self) -> bool:
        """Backward-compatible indicator for not-yet-implemented decision surfaces."""
        return False
