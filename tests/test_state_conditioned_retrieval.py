from __future__ import annotations

import pytest

from schemarouter import (
    CapabilityFieldContract,
    CapabilityPrecondition,
    EndpointSpec,
    InMemoryRegistry,
    KeywordAnalyzer,
    PlanRequest,
    SchemaPlanner,
    SchemaRouter,
    ToolSpec,
    TypedExecutionState,
)
from schemarouter.execution_state import ObservedStateField


def _registry(*endpoint_names: str) -> InMemoryRegistry:
    registry = InMemoryRegistry()
    registry.register(
        ToolSpec(
            name="demo",
            description="continue task",
            endpoints=[
                EndpointSpec(
                    name=name,
                    description="continue task",
                    read_only=True,
                    destructive=False,
                )
                for name in endpoint_names
            ],
        )
    )
    return registry


def _missing_id_requirement() -> CapabilityFieldContract:
    return CapabilityFieldContract(
        semantic_id="resource.id",
        json_schema={"type": "string"},
    )


def test_reretrieve_backfills_past_ineligible_initial_top_k() -> None:
    router = SchemaRouter(registry=_registry("a", "b", "c"))
    requirements = {"demo.a": [_missing_id_requirement()]}

    filtered = router.retrieve_state_aware(
        "continue task",
        execution_state=TypedExecutionState(),
        k=2,
        state_requirements=requirements,
    )
    refreshed = router.reretrieve_state_aware(
        "continue task",
        execution_state=TypedExecutionState(),
        k=2,
        state_requirements=requirements,
    )

    assert [item.candidate.route_id for item in filtered.candidates] == ["demo.b"]
    assert [item.candidate.route_id for item in refreshed.candidates] == [
        "demo.b",
        "demo.c",
    ]
    assert [item.original_rank for item in refreshed.candidates] == [2, 3]
    assert [item.candidate.rank for item in refreshed.candidates] == [1, 2]
    assert refreshed.examined_count == 3
    assert refreshed.surface_exhausted
    assert [item.route_id for item in refreshed.excluded] == ["demo.a"]
    assert refreshed.excluded[0].eligibility.reasons[0].code == "missing_required_state"


def test_reretrieve_recovers_when_all_initial_top_k_are_ineligible() -> None:
    router = SchemaRouter(registry=_registry("a", "b", "c", "d"))
    required = _missing_id_requirement()

    refreshed = router.reretrieve_state_aware(
        "continue task",
        execution_state=TypedExecutionState(),
        k=2,
        state_requirements={
            "demo.a": [required],
            "demo.b": [required],
        },
    )

    assert [item.candidate.route_id for item in refreshed.candidates] == [
        "demo.c",
        "demo.d",
    ]
    assert [item.original_rank for item in refreshed.candidates] == [3, 4]
    assert [item.route_id for item in refreshed.excluded] == ["demo.a", "demo.b"]


def test_reretrieve_reports_exhausted_surface_when_eligible_candidates_are_fewer_than_k() -> None:
    router = SchemaRouter(registry=_registry("a", "b", "c"))
    required = _missing_id_requirement()

    refreshed = router.reretrieve_state_aware(
        "continue task",
        execution_state=TypedExecutionState(),
        k=3,
        state_requirements={
            "demo.a": [required],
            "demo.b": [required],
        },
    )

    assert [item.candidate.route_id for item in refreshed.candidates] == ["demo.c"]
    assert refreshed.examined_count == 3
    assert refreshed.surface_exhausted
    assert refreshed.total_ranked == 3


def test_reretrieve_never_backfills_from_invisible_candidates() -> None:
    registry = _registry("a", "hidden", "z")
    planner = SchemaPlanner(
        registry,
        availability_predicate=lambda _tool, endpoint: endpoint.name != "hidden",
    )

    refreshed = planner.reretrieve_state_aware(
        "continue task",
        execution_state=TypedExecutionState(),
        k=3,
    )

    route_ids = [item.candidate.route_id for item in refreshed.candidates]
    assert route_ids == ["demo.a", "demo.z"]
    assert refreshed.total_ranked == 2
    assert all(item.route_id != "demo.hidden" for item in refreshed.excluded)


def test_reretrieve_exposes_explicit_precondition_failure() -> None:
    router = SchemaRouter(registry=_registry("a", "b"))
    state = TypedExecutionState(
        observed_fields=[
            ObservedStateField(
                contract=CapabilityFieldContract(semantic_id="resource.status"),
                stable_identifier="pending",
            )
        ]
    )

    refreshed = router.reretrieve_state_aware(
        "continue task",
        execution_state=state,
        k=1,
        state_preconditions={
            "demo.a": [
                CapabilityPrecondition(
                    semantic_id="resource.status",
                    operator="equals",
                    value="ready",
                )
            ]
        },
    )

    assert [item.candidate.route_id for item in refreshed.candidates] == ["demo.b"]
    assert refreshed.excluded[0].route_id == "demo.a"
    assert refreshed.excluded[0].eligibility.reasons[0].code == "precondition_failed"


class _AsyncKeywordAnalyzer:
    async def analyze(self, request: PlanRequest, registry: InMemoryRegistry):
        return KeywordAnalyzer().analyze(request, registry)


@pytest.mark.asyncio
async def test_state_conditioned_sync_async_results_are_deterministic() -> None:
    registry = _registry("a", "b", "c")
    required = _missing_id_requirement()
    requirements = {"demo.a": [required]}

    sync_planner = SchemaPlanner(registry)
    async_planner = SchemaPlanner(registry, analyzer=_AsyncKeywordAnalyzer())

    expected = sync_planner.reretrieve_state_aware(
        "continue task",
        execution_state=TypedExecutionState(),
        k=2,
        state_requirements=requirements,
    )
    actual = await async_planner.areretrieve_state_aware(
        "continue task",
        execution_state=TypedExecutionState(),
        k=2,
        state_requirements=requirements,
    )

    assert actual == expected


def test_state_conditioned_result_has_no_execution_authority() -> None:
    router = SchemaRouter(registry=_registry("a"))
    result = router.reretrieve_state_aware(
        "continue task",
        execution_state=TypedExecutionState(),
        k=1,
    )

    forbidden = {
        "execute",
        "invoke",
        "commit",
        "rollback",
        "retry",
        "compensate",
        "plan",
        "schedule",
        "authorize",
    }
    assert forbidden.isdisjoint(dir(result))
    assert forbidden.isdisjoint(dir(result.candidates[0]))
