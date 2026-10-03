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
        eligibility = evaluate_state_eligibility(
            requirements.get(candidate.route_id, []),
            state,
        )
        if eligibility.eligible:
            eligibility = evaluate_preconditions(
                preconditions.get(candidate.route_id, []),
                state,
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
