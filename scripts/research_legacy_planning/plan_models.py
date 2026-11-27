"""Historical lexical plan metadata and wire models (source checkout only).

Extend the canonical execution contracts only inside research. The installed
ToolCall never exposes lexical scores or explanation fields.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from schemarouter.models import ExecutionPlan as ProductExecutionPlan
from schemarouter.models import FallbackRoute as ProductFallbackRoute
from schemarouter.models import StrictModel
from schemarouter.models import ToolCall as ProductToolCall


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
    "semantic_recall",
    "endpoint_disambiguation",
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


class ToolCall(ProductToolCall):
    """Historical ranked call, sharing the canonical execution fields."""

    score: float = 0.0
    explanation: PlanExplanation | None = None


class FallbackRoute(ProductFallbackRoute):
    """Preserve historical alternative call metadata during serialization."""

    alternatives: list[ToolCall] = Field(default_factory=list, max_length=8)


class ExecutionPlan(ProductExecutionPlan):
    """Historical wire contract, including nested lexical explanations."""

    calls: list[ToolCall] = Field(default_factory=list, max_length=32)
    fallback_routes: list[FallbackRoute] = Field(default_factory=list, max_length=32)
