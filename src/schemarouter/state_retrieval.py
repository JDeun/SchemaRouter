from __future__ import annotations

from pydantic import Field

from .capability_contracts import CapabilityFieldContract
from .execution_state import StateEligibility, TypedExecutionState, evaluate_state_eligibility
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


def candidate_state_requirements(
    candidate: CapabilityCandidate,
) -> list[CapabilityFieldContract]:
    """Read optional host-visible state requirements from a capability candidate.

    State requirements are explicit metadata only. SchemaRouter never infers workflow
    preconditions from endpoint names, descriptions, or prior calls.
    """

    requirements: list[CapabilityFieldContract] = []
    for parameter in candidate.parameters:
        semantic_id = getattr(parameter, "semantic_id", None)
        if semantic_id is None:
            continue
        required = bool(getattr(parameter, "required", False))
        if not required:
            continue
        requirements.append(CapabilityFieldContract(
            semantic_id=semantic_id,
            json_schema=getattr(parameter, "json_schema", {}) or {},
        ))
    return requirements


def filter_retrieval_by_state(
    retrieval: CapabilityRetrieval,
    state: TypedExecutionState,
    *,
    requirements_by_route: dict[str, list[CapabilityFieldContract]] | None = None,
) -> StateAwareCapabilityRetrieval:
    """Filter an existing retrieval result against host-supplied typed state.

    The host may supply route-specific requirements. If omitted, only explicit
    semantic IDs on required parameters are considered. Ranking among surviving
    candidates is preserved and no execution or workflow planning occurs.
    """

    overrides = requirements_by_route or {}
    candidates: list[StateAwareCapabilityCandidate] = []
    for candidate in retrieval.candidates:
        requirements = overrides.get(
            candidate.route_id,
            candidate_state_requirements(candidate),
        )
        eligibility = evaluate_state_eligibility(requirements, state)
        if eligibility.eligible:
            candidates.append(StateAwareCapabilityCandidate(
                candidate=candidate,
                eligibility=eligibility,
            ))
    return StateAwareCapabilityRetrieval(
        query=retrieval.query,
        registry_version=retrieval.registry_version,
        requested_k=retrieval.requested_k,
        total_ranked=retrieval.total_ranked,
        candidates=candidates,
    )
