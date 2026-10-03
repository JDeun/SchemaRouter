from __future__ import annotations

import pytest

from schemarouter import (
    CapabilityFieldContract,
    EndpointSpec,
    ObservedStateField,
    PlanRequest,
    QueryIntent,
    SchemaRouter,
    ToolSpec,
    TypedExecutionState,
)


def _router() -> SchemaRouter:
    router = SchemaRouter()
    for name in ("a_route", "b_route", "c_route", "d_route"):
        router.add_tool(
            ToolSpec(
                name=name,
                description="same capability surface",
                endpoints=[
                    EndpointSpec(
                        name="read",
                        description="same capability surface",
                        read_only=True,
                    )
                ],
            )
        )
    return router


def _missing_requirement() -> CapabilityFieldContract:
    return CapabilityFieldContract(
        semantic_id="resource.material_id",
        json_schema={"type": "string"},
    )


def test_reretrieval_backfills_beyond_initial_top_k() -> None:
    router = _router()
    requirements = {"a_route.read": [_missing_requirement()]}

    fixed = router.retrieve_state_aware(
        "unrelated query",
        execution_state=TypedExecutionState(),
        k=2,
        state_requirements=requirements,
    )
    refreshed = router.reretrieve_state_aware(
        "unrelated query",
        execution_state=TypedExecutionState(),
        k=2,
        state_requirements=requirements,
    )

    assert [item.candidate.route_id for item in fixed.candidates] == [
        "b_route.read"
    ]
    assert [item.candidate.route_id for item in refreshed.candidates] == [
        "b_route.read",
        "c_route.read",
    ]
    assert [item.candidate.rank for item in refreshed.candidates] == [2, 3]
    assert [item.candidate.route_id for item in refreshed.excluded] == [
        "a_route.read"
    ]
    assert refreshed.excluded[0].eligibility.status == "missing_required_state"
    assert refreshed.total_ranked == 4
    assert refreshed.requested_k == 2


def test_reretrieval_returns_all_available_when_eligible_surface_is_smaller_than_k() -> None:
    router = _router()
    missing = _missing_requirement()
    requirements = {
        "a_route.read": [missing],
        "b_route.read": [missing],
        "c_route.read": [missing],
    }

    result = router.reretrieve_state_aware(
        "unrelated query",
        execution_state=TypedExecutionState(),
        k=3,
        state_requirements=requirements,
    )

    assert [item.candidate.route_id for item in result.candidates] == [
        "d_route.read"
    ]
    assert len(result.excluded) == 3


def test_reretrieval_never_expands_planner_visibility_surface() -> None:
    router = _router()
    router.mark_access_unavailable("c_route", "read", cooldown_seconds=60)

    result = router.reretrieve_state_aware(
        "unrelated query",
        execution_state=TypedExecutionState(),
        k=4,
    )

    route_ids = [item.candidate.route_id for item in result.candidates]
    assert "c_route.read" not in route_ids
    assert result.total_ranked == 3


def test_reretrieval_satisfies_declared_state_without_inference() -> None:
    router = _router()
    required = _missing_requirement()
    state = TypedExecutionState(
        observed_fields=[
            ObservedStateField(
                contract=required,
                stable_identifier="mp-149",
            )
        ]
    )

    result = router.reretrieve_state_aware(
        "unrelated query",
        execution_state=state,
        k=2,
        state_requirements={"a_route.read": [required]},
    )

    assert [item.candidate.route_id for item in result.candidates] == [
        "a_route.read",
        "b_route.read",
    ]
    assert result.excluded == []


class _AsyncAnalyzer:
    async def analyze(self, request: PlanRequest, registry) -> QueryIntent:
        del registry
        return QueryIntent(
            concepts=list(request.concepts),
            preferred_tools=request.preferred_tools,
            arguments=request.arguments,
            evidence=request.evidence,
            field_evidence=request.field_evidence,
        )


@pytest.mark.asyncio
async def test_async_reretrieval_matches_sync_ordering() -> None:
    sync_router = _router()
    async_router = _router()
    async_router.planner.analyzer = _AsyncAnalyzer()
    requirements = {"a_route.read": [_missing_requirement()]}

    expected = sync_router.reretrieve_state_aware(
        "unrelated query",
        execution_state=TypedExecutionState(),
        k=2,
        state_requirements=requirements,
    )
    actual = await async_router.areretrieve_state_aware(
        "unrelated query",
        execution_state=TypedExecutionState(),
        k=2,
        state_requirements=requirements,
    )

    assert [
        item.candidate.route_id for item in actual.candidates
    ] == [
        item.candidate.route_id for item in expected.candidates
    ]
    assert [
        item.candidate.rank for item in actual.candidates
    ] == [
        item.candidate.rank for item in expected.candidates
    ]


def test_configured_router_exposes_reretrieval_surface() -> None:
    router = _router()
    configured = router.with_config({})
    requirements = {"a_route.read": [_missing_requirement()]}

    direct = router.reretrieve_state_aware(
        "unrelated query",
        execution_state=TypedExecutionState(),
        k=2,
        state_requirements=requirements,
    )
    configured_result = configured.reretrieve_state_aware(
        "unrelated query",
        execution_state=TypedExecutionState(),
        k=2,
        state_requirements=requirements,
    )

    assert configured_result == direct


def test_state_conditioned_result_has_no_execution_authority() -> None:
    result = _router().reretrieve_state_aware(
        "unrelated query",
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
