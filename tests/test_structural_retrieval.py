from __future__ import annotations

import pytest

from schemarouter import EndpointSpec, InMemoryRegistry, SchemaPlanner, SchemaRouter, ToolSpec


def _ranking_registry() -> InMemoryRegistry:
    registry = InMemoryRegistry()
    registry.register(
        ToolSpec(
            name="jobs",
            description="Registered job lifecycle",
            endpoints=[
                EndpointSpec(
                    name="cancel",
                    description="Cancel a running computation job",
                    read_only=False,
                ),
                EndpointSpec(
                    name="status",
                    description="Read current computation job status",
                    read_only=True,
                ),
            ],
        )
    )
    registry.register(
        ToolSpec(
            name="aux_job_001",
            description="Auxiliary job lifecycle",
            endpoints=[
                EndpointSpec(
                    name="cancel",
                    description="Cancel auxiliary job records",
                    read_only=False,
                ),
            ],
        )
    )
    return registry


def test_structural_retrieval_is_default_off() -> None:
    registry = _ranking_registry()

    implicit = SchemaPlanner(registry).retrieve(
        "job cancellation",
        k=3,
    )
    explicit = SchemaPlanner(
        registry,
        structural_retrieval=False,
    ).retrieve(
        "job cancellation",
        k=3,
    )

    assert [
        (candidate.route_id, candidate.score)
        for candidate in implicit.candidates
    ] == [
        (candidate.route_id, candidate.score)
        for candidate in explicit.candidates
    ]


def test_structural_retrieval_boosts_complete_tool_identifier() -> None:
    registry = _ranking_registry()
    result = SchemaPlanner(
        registry,
        structural_retrieval=True,
    ).retrieve(
        "job cancellation",
        k=3,
    )

    assert result.candidates[0].route_id == "jobs.cancel"
    components = {
        component.kind: component.value
        for component in result.candidates[0].score_components
    }
    assert components["tool_identifier"] == 4.5
    assert components["operation_family"] == 1.5

    auxiliary = next(
        candidate
        for candidate in result.candidates
        if candidate.route_id == "aux_job_001.cancel"
    )
    assert all(
        component.kind != "tool_identifier"
        for component in auxiliary.score_components
    )


def test_structural_operation_family_survives_candidate_index_planning() -> None:
    registry = InMemoryRegistry()
    registry.register(
        ToolSpec(
            name="operations",
            endpoints=[
                EndpointSpec(
                    name="cancel",
                    description="Stop a running operation",
                    read_only=False,
                )
            ],
        )
    )

    baseline = SchemaPlanner(
        registry,
        candidate_index=True,
    ).plan("cancellation")
    structural = SchemaPlanner(
        registry,
        candidate_index=True,
        structural_retrieval=True,
    ).plan("cancellation")

    assert baseline.calls == []
    assert structural.calls
    assert structural.calls[0].tool == "operations"
    assert structural.calls[0].endpoint == "cancel"


def test_structural_specificity_breaks_equal_score_ties() -> None:
    registry = InMemoryRegistry()
    registry.register(
        ToolSpec(
            name="a_generic",
            description="Read record value",
            endpoints=[
                EndpointSpec(
                    name="read",
                    description="Read record value",
                    read_only=True,
                )
            ],
        )
    )
    registry.register(
        ToolSpec(
            name="z_specific",
            description="Read record value unique spectroscopy archive",
            endpoints=[
                EndpointSpec(
                    name="read",
                    description="Read record value unique Raman provenance",
                    read_only=True,
                )
            ],
        )
    )

    baseline = SchemaPlanner(registry).retrieve("read value", k=2)
    structural = SchemaPlanner(
        registry,
        structural_retrieval=True,
    ).retrieve("read value", k=2)

    assert baseline.candidates[0].score == baseline.candidates[1].score
    assert baseline.candidates[0].route_id == "a_generic.read"
    assert structural.candidates[0].score == structural.candidates[1].score
    assert structural.candidates[0].route_id == "z_specific.read"


def test_structural_specificity_cache_tracks_registry_version() -> None:
    registry = _ranking_registry()
    planner = SchemaPlanner(
        registry,
        structural_retrieval=True,
    )

    planner.retrieve("job cancellation", k=2)
    first = planner._structural_specificity_cache  # noqa: SLF001
    assert first is not None
    first_version = first[0]

    registry.register(
        ToolSpec(
            name="reports",
            endpoints=[
                EndpointSpec(
                    name="search",
                    description="Search reports",
                    read_only=True,
                )
            ],
        )
    )
    planner.retrieve("job cancellation", k=2)
    second = planner._structural_specificity_cache  # noqa: SLF001
    assert second is not None
    assert second[0] == registry.version
    assert second[0] != first_version


@pytest.mark.asyncio
async def test_structural_sync_async_retrieval_parity() -> None:
    registry = _ranking_registry()
    planner = SchemaPlanner(
        registry,
        structural_retrieval=True,
    )

    sync_result = planner.retrieve("job cancellation", k=3)
    async_result = await planner.aretrieve("job cancellation", k=3)

    assert [
        (candidate.route_id, candidate.score)
        for candidate in sync_result.candidates
    ] == [
        (candidate.route_id, candidate.score)
        for candidate in async_result.candidates
    ]



def test_schema_router_exposes_opt_in_structural_retrieval() -> None:
    registry = _ranking_registry()
    router = SchemaRouter(
        registry=registry,
        structural_retrieval=True,
    )

    result = router.retrieve("job cancellation", k=3)

    assert router.planner.structural_retrieval is True
    assert result.candidates[0].route_id == "jobs.cancel"
