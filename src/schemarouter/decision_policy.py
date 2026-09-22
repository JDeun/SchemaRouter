from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

DecisionFallback = Literal["deterministic", "error"]


class DecisionPolicy(BaseModel):
    """Opt-in controls for experimental bounded-decision assistance."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    enabled: bool = False
    tool_selection: bool = False
    endpoint_selection: bool = False
    field_selection: bool = False
    evidence_sufficiency: bool = False
    fallback: DecisionFallback = "deterministic"

    @property
    def candidate_selection_enabled(self) -> bool:
        return self.enabled and (self.tool_selection or self.endpoint_selection)

    @property
    def field_selection_enabled(self) -> bool:
        return self.enabled and self.field_selection

    @property
    def reserved_surfaces_enabled(self) -> bool:
        return self.enabled and self.evidence_sufficiency
