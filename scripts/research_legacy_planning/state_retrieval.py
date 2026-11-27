"""Historical lexical fixed Top-K state filtering (source checkout only)."""

from __future__ import annotations

from pydantic import Field

from schemarouter.capability_contracts import CapabilityFieldContract, CapabilityPrecondition
from schemarouter.execution_state import (
    StateEligibility,
    TypedExecutionState,
    evaluate_preconditions,
    evaluate_state_eligibility,
)
from schemarouter.models import CapabilityCandidate, CapabilityRetrieval, StrictModel


class StateAwareCapabilityCandidate(StrictModel):
    candidate: CapabilityCandidate
    eligibility: StateEligibility


class StateAwareCapabilityRetrieval(StrictModel):
    query: str
    registry_version: int
    requested_k: int = Field(ge=1)
    total_ranked: int = Field(ge=0)
    candidates: list[StateAwareCapabilityCandidate] = Field(default_factory=list)


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
