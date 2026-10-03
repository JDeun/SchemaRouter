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


class StateConditionedCapabilityCandidate(StrictModel):
    """One eligible candidate returned by state-conditioned backfill."""

    candidate: CapabilityCandidate
    eligibility: StateEligibility
    original_rank: int = Field(ge=1)


class StateConditionedExcludedCandidate(StrictModel):
    """One visible ranked candidate excluded by explicit typed state."""

    route_id: str
    original_rank: int = Field(ge=1)
    eligibility: StateEligibility


class StateConditionedCapabilityRetrieval(StrictModel):
    """Eligible Top-K after scanning the visible ranked capability surface."""

    query: str
    registry_version: int
    requested_k: int = Field(ge=1)
    total_ranked: int = Field(ge=0)
    examined_count: int = Field(ge=0)
    surface_exhausted: bool = False
    candidates: list[StateConditionedCapabilityCandidate] = Field(default_factory=list)
    excluded: list[StateConditionedExcludedCandidate] = Field(default_factory=list)


def _route_eligibility(
    route_id: str,
    state: TypedExecutionState,
    *,
    requirements_by_route: dict[str, list[CapabilityFieldContract]],
    preconditions_by_route: dict[str, list[CapabilityPrecondition]],
) -> StateEligibility:
    eligibility = evaluate_state_eligibility(
        requirements_by_route.get(route_id, []),
        state,
    )
    if eligibility.eligible:
        eligibility = evaluate_preconditions(
            preconditions_by_route.get(route_id, []),
            state,
        )
    return eligibility


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

    requirements = requirements_by_route or {}
    preconditions = preconditions_by_route or {}
    candidates: list[StateAwareCapabilityCandidate] = []
    for candidate in retrieval.candidates:
        eligibility = _route_eligibility(
            candidate.route_id,
            state,
            requirements_by_route=requirements,
            preconditions_by_route=preconditions,
        )
        if eligibility.eligible:
            candidates.append(
                StateAwareCapabilityCandidate(
                    candidate=candidate,
                    eligibility=eligibility,
                )
            )
    return StateAwareCapabilityRetrieval(
        query=retrieval.query,
        registry_version=retrieval.registry_version,
        requested_k=retrieval.requested_k,
        total_ranked=retrieval.total_ranked,
        candidates=candidates,
    )


def backfill_retrieval_by_state(
    retrieval: CapabilityRetrieval,
    state: TypedExecutionState,
    *,
    k: int,
    requirements_by_route: dict[str, list[CapabilityFieldContract]] | None = None,
    preconditions_by_route: dict[str, list[CapabilityPrecondition]] | None = None,
) -> StateConditionedCapabilityRetrieval:
    """Return the first K eligible candidates from a complete visible ranking.

    The caller is responsible for supplying a retrieval containing the full visible
    ranked surface. This function never widens that surface and never infers state.
    """

    if not isinstance(k, int) or isinstance(k, bool) or k < 1:
        raise ValueError("k must be an integer >= 1")

    requirements = requirements_by_route or {}
    preconditions = preconditions_by_route or {}
    selected: list[StateConditionedCapabilityCandidate] = []
    excluded: list[StateConditionedExcludedCandidate] = []
    examined_count = 0

    for candidate in retrieval.candidates:
        examined_count += 1
        eligibility = _route_eligibility(
            candidate.route_id,
            state,
            requirements_by_route=requirements,
            preconditions_by_route=preconditions,
        )
        if eligibility.eligible:
            selected.append(
                StateConditionedCapabilityCandidate(
                    candidate=candidate.model_copy(
                        update={"rank": len(selected) + 1},
                        deep=True,
                    ),
                    eligibility=eligibility,
                    original_rank=candidate.rank,
                )
            )
            if len(selected) == k:
                break
        else:
            excluded.append(
                StateConditionedExcludedCandidate(
                    route_id=candidate.route_id,
                    original_rank=candidate.rank,
                    eligibility=eligibility,
                )
            )

    return StateConditionedCapabilityRetrieval(
        query=retrieval.query,
        registry_version=retrieval.registry_version,
        requested_k=k,
        total_ranked=retrieval.total_ranked,
        examined_count=examined_count,
        surface_exhausted=examined_count == len(retrieval.candidates),
        candidates=selected,
        excluded=excluded,
    )
