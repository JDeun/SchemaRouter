from __future__ import annotations

from pydantic import Field

from .capability_contracts import CapabilityFieldContract, CapabilityPrecondition
from .execution_state import (
    StateEligibility,
    TypedExecutionState,
    evaluate_preconditions,
    evaluate_state_eligibility,
)
from .models import CapabilityCandidate, CapabilityRetrieval, StrictModel


class StateAwareCapabilityCandidate(StrictModel):
    candidate: CapabilityCandidate
    eligibility: StateEligibility


class StateAwareCapabilityRetrieval(StrictModel):
    query: str
    registry_version: int
    requested_k: int = Field(ge=1)
    total_ranked: int = Field(ge=0)
    candidates: list[StateAwareCapabilityCandidate] = Field(default_factory=list)


class StateConditionedCapabilityRetrieval(StrictModel):
    """Eligible Top-K plus explicit state rejections from the ranked candidate surface."""

    query: str
    registry_version: int
    requested_k: int = Field(ge=1)
    total_ranked: int = Field(ge=0)
    candidates: list[StateAwareCapabilityCandidate] = Field(default_factory=list)
    excluded: list[StateAwareCapabilityCandidate] = Field(default_factory=list)


def evaluate_candidate_state(
    candidate: CapabilityCandidate,
    state: TypedExecutionState,
    *,
    requirements_by_route: dict[str, list[CapabilityFieldContract]] | None = None,
    preconditions_by_route: dict[str, list[CapabilityPrecondition]] | None = None,
) -> StateAwareCapabilityCandidate:
    """Evaluate one already-visible candidate against explicit host-supplied state."""

    requirements = requirements_by_route or {}
    preconditions = preconditions_by_route or {}
    eligibility = evaluate_state_eligibility(
        requirements.get(candidate.route_id, []),
        state,
    )
    if eligibility.eligible:
        eligibility = evaluate_preconditions(
            preconditions.get(candidate.route_id, []),
            state,
        )
    return StateAwareCapabilityCandidate(
        candidate=candidate,
        eligibility=eligibility,
    )


def filter_retrieval_by_state(
    retrieval: CapabilityRetrieval,
    state: TypedExecutionState,
    *,
    requirements_by_route: dict[str, list[CapabilityFieldContract]] | None = None,
    preconditions_by_route: dict[str, list[CapabilityPrecondition]] | None = None,
) -> StateAwareCapabilityRetrieval:
    """Filter retrieval against explicit host-supplied typed state contracts.

    Missing route metadata means no state precondition. SchemaRouter never infers
    workflow state from route names, parameter names, descriptions, or call history.
    """

    candidates: list[StateAwareCapabilityCandidate] = []
    for candidate in retrieval.candidates:
        evaluated = evaluate_candidate_state(
            candidate,
            state,
            requirements_by_route=requirements_by_route,
            preconditions_by_route=preconditions_by_route,
        )
        if evaluated.eligibility.eligible:
            candidates.append(evaluated)
    return StateAwareCapabilityRetrieval(
        query=retrieval.query,
        registry_version=retrieval.registry_version,
        requested_k=retrieval.requested_k,
        total_ranked=retrieval.total_ranked,
        candidates=candidates,
    )


def backfill_ranked_candidates_by_state(
    *,
    query: str,
    registry_version: int,
    requested_k: int,
    ranked_candidates: list[CapabilityCandidate],
    state: TypedExecutionState,
    requirements_by_route: dict[str, list[CapabilityFieldContract]] | None = None,
    preconditions_by_route: dict[str, list[CapabilityPrecondition]] | None = None,
) -> StateConditionedCapabilityRetrieval:
    """Return the first K state-eligible candidates from an already-visible ranked surface.

    The caller owns candidate visibility/authorization. This helper never expands that
    surface; it only evaluates typed state and preconditions over the supplied ranking.
    Original ranks are preserved so hosts can audit which higher-ranked candidates were
    excluded before backfill occurred.
    """

    if requested_k < 1:
        raise ValueError("requested_k must be at least 1")

    eligible: list[StateAwareCapabilityCandidate] = []
    excluded: list[StateAwareCapabilityCandidate] = []
    for candidate in ranked_candidates:
        evaluated = evaluate_candidate_state(
            candidate,
            state,
            requirements_by_route=requirements_by_route,
            preconditions_by_route=preconditions_by_route,
        )
        if evaluated.eligibility.eligible:
            if len(eligible) < requested_k:
                eligible.append(evaluated)
        else:
            excluded.append(evaluated)

    return StateConditionedCapabilityRetrieval(
        query=query,
        registry_version=registry_version,
        requested_k=requested_k,
        total_ranked=len(ranked_candidates),
        candidates=eligible,
        excluded=excluded,
    )
