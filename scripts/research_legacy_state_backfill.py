"""Historical state-conditioned backfill; outside the installed routing package."""

from __future__ import annotations

from pydantic import Field

from schemarouter.capability_contracts import CapabilityFieldContract, CapabilityPrecondition
from schemarouter.execution_state import TypedExecutionState
from schemarouter.models import CapabilityCandidate, StrictModel
from schemarouter.runtime import ConfiguredSchemaRouter, SchemaRouter
from schemarouter.state_retrieval import StateAwareCapabilityCandidate, evaluate_candidate_state
from scripts.research_legacy_planning.requests import PlanRequest


class StateConditionedCapabilityRetrieval(StrictModel):
    """Eligible Top-K plus explicit state rejections from the ranked candidate surface."""

    query: str
    registry_version: int
    requested_k: int = Field(ge=1)
    total_ranked: int = Field(ge=0)
    candidates: list[StateAwareCapabilityCandidate] = Field(default_factory=list)
    excluded: list[StateAwareCapabilityCandidate] = Field(default_factory=list)


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


def _full_width(router: SchemaRouter | ConfiguredSchemaRouter, k: int) -> int:
    source = router.router if isinstance(router, ConfiguredSchemaRouter) else router
    return max(k, sum(len(tool.endpoints) for tool in source.registry.tools()))


def legacy_reretrieve_state_aware(
    router: SchemaRouter | ConfiguredSchemaRouter,
    request: PlanRequest | str,
    *,
    execution_state: TypedExecutionState,
    k: int = 5,
    state_requirements: dict[str, list[CapabilityFieldContract]] | None = None,
    state_preconditions: dict[str, list[CapabilityPrecondition]] | None = None,
) -> StateConditionedCapabilityRetrieval:
    retrieval = router.retrieve(request, k=_full_width(router, k))
    return backfill_ranked_candidates_by_state(
        query=retrieval.query,
        registry_version=retrieval.registry_version,
        requested_k=k,
        ranked_candidates=retrieval.candidates,
        state=execution_state,
        requirements_by_route=state_requirements,
        preconditions_by_route=state_preconditions,
    )


async def legacy_areretrieve_state_aware(
    router: SchemaRouter | ConfiguredSchemaRouter,
    request: PlanRequest | str,
    *,
    execution_state: TypedExecutionState,
    k: int = 5,
    state_requirements: dict[str, list[CapabilityFieldContract]] | None = None,
    state_preconditions: dict[str, list[CapabilityPrecondition]] | None = None,
) -> StateConditionedCapabilityRetrieval:
    retrieval = await router.aretrieve(request, k=_full_width(router, k))
    return backfill_ranked_candidates_by_state(
        query=retrieval.query,
        registry_version=retrieval.registry_version,
        requested_k=k,
        ranked_candidates=retrieval.candidates,
        state=execution_state,
        requirements_by_route=state_requirements,
        preconditions_by_route=state_preconditions,
    )
