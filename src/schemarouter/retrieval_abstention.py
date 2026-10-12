"""Explicit, opt-in abstention on *already authorized* capability retrieval results.

A ranker's numeric score is not a probability, and a universal threshold is
not safe. Callers must supply thresholds calibrated for their own frozen
scorer/catalog domain. This module never retrieves additional capabilities,
executes an endpoint, or changes the default SchemaRouter.retrieve behavior.
"""
from __future__ import annotations

import math
from typing import Literal

from pydantic import field_validator, model_validator

from .models import CapabilityRetrieval, StrictModel


class RetrievalAbstentionPolicy(StrictModel):
    """External, domain-calibrated ranking gates (not an authorization policy)."""

    min_score: float | None = None
    min_margin: float | None = None

    @field_validator("min_score", "min_margin", mode="before")
    @classmethod
    def reject_non_numeric_thresholds(cls, value: object) -> object:
        if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float))):
            raise ValueError("thresholds must be numeric, not bool or strings")
        return value

    @model_validator(mode="after")
    def validate_explicit_gates(self) -> RetrievalAbstentionPolicy:
        if self.min_score is None and self.min_margin is None:
            raise ValueError("at least one explicitly calibrated gate is required")
        for label, value in (
            ("min_score", self.min_score),
            ("min_margin", self.min_margin),
        ):
            if value is not None:
                if isinstance(value, bool) or not math.isfinite(value):
                    raise ValueError(f"{label} must be a finite number")
        if self.min_margin is not None and self.min_margin < 0:
            raise ValueError("min_margin must be nonnegative")
        return self


class SelectiveCapabilityRetrieval(CapabilityRetrieval):
    """Original ranked surface, possibly reduced to an auditable empty shortlist."""

    disposition: Literal["selected", "abstained"]
    reason: Literal[
        "selected",
        "empty_catalog",
        "untrusted_ranking",
        "below_min_score",
        "insufficient_margin_evidence",
        "below_min_margin",
    ]
    policy: RetrievalAbstentionPolicy
    observed_top_score: float | None = None
    observed_margin: float | None = None

    @property
    def abstained(self) -> bool:
        return self.disposition == "abstained"


def apply_retrieval_abstention(
    retrieval: CapabilityRetrieval,
    *,
    policy: RetrievalAbstentionPolicy,
) -> SelectiveCapabilityRetrieval:
    """Fail closed when a post-authorization shortlist lacks calibrated evidence.

    Only candidates in the supplied retrieval are ever returned. A missing
    runner-up is **not** evidence for a large margin; request k>=2 to use it.
    No score is construed as probability or permission to execute.
    """

    if not isinstance(retrieval, CapabilityRetrieval):
        raise TypeError("expected an already scoped CapabilityRetrieval")
    if not isinstance(policy, RetrievalAbstentionPolicy):
        raise TypeError("policy must be a validated RetrievalAbstentionPolicy")

    scores = [candidate.score for candidate in retrieval.candidates]
    route_ids = [candidate.route_id for candidate in retrieval.candidates]
    ranks = [candidate.rank for candidate in retrieval.candidates]
    reason: str = "selected"
    top: float | None = None
    margin: float | None = None

    if not retrieval.candidates:
        reason = "empty_catalog"
    elif (
        not all(math.isfinite(score) for score in scores)
        or len(set(route_ids)) != len(route_ids)
        or ranks != list(range(1, len(ranks) + 1))
        or any(scores[i] < scores[i + 1] for i in range(len(scores) - 1))
    ):
        reason = "untrusted_ranking"
    else:
        top = scores[0]
        if policy.min_score is not None and top < policy.min_score:
            reason = "below_min_score"
        elif policy.min_margin is not None:
            if len(scores) < 2:
                reason = "insufficient_margin_evidence"
            else:
                margin = scores[0] - scores[1]
                if margin < policy.min_margin:
                    reason = "below_min_margin"

    data = retrieval.model_dump(mode="python")
    data["candidates"] = (
        list(retrieval.candidates) if reason == "selected" else []
    )
    return SelectiveCapabilityRetrieval(
        **data,
        disposition="selected" if reason == "selected" else "abstained",
        reason=reason,
        policy=policy,
        observed_top_score=top,
        observed_margin=margin,
    )
