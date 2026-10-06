from __future__ import annotations

import pytest

from schemarouter import (
    EndpointSpec,
    InMemoryRegistry,
    PlanningError,
    SchemaPlanner,
    ToolSpec,
)


def _catalog_tool(name: str) -> ToolSpec:
    return ToolSpec(
        name=name,
        description=f"{name} catalog lookup",
        endpoints=[
            EndpointSpec(
                name="search",
                description=f"Search the {name} catalog",
                read_only=True,
            )
        ],
    )


@pytest.mark.parametrize(
    ("candidate_index", "structural_retrieval"),
    [(True, False), (False, True)],
)
def test_retrieval_version_stays_bound_to_ranked_catalog_snapshot(
    monkeypatch: pytest.MonkeyPatch,
    candidate_index: bool,
    structural_retrieval: bool,
) -> None:
    registry = InMemoryRegistry()
    original = _catalog_tool("alpha_catalog")
    registry.register(original)
    ranked_version = registry.version
    planner = SchemaPlanner(
        registry,
        candidate_index=candidate_index,
        structural_retrieval=structural_retrieval,
    )
    original_sort = planner._sort_candidates  # noqa: SLF001
    mutated = False

    def sort_then_mutate(candidates, *, catalog_snapshot=None):
        nonlocal mutated
        original_sort(candidates, catalog_snapshot=catalog_snapshot)
        if not mutated:
            registry.register(_catalog_tool("late_catalog"))
            mutated = True

    monkeypatch.setattr(planner, "_sort_candidates", sort_then_mutate)

    retrieval = planner.retrieve("alpha catalog lookup", k=5)

    assert retrieval.registry_version == ranked_version
    assert registry.version == ranked_version + 1
    assert [candidate.route_id for candidate in retrieval.candidates] == [
        "alpha_catalog.search"
    ]
    assert retrieval.candidates[0].tool_fingerprint == original.fingerprint


def test_plan_version_stays_bound_when_registry_changes_after_candidate_ranking(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry = InMemoryRegistry()
    original = _catalog_tool("alpha_catalog")
    registry.register(original)
    ranked_version = registry.version
    planner = SchemaPlanner(registry)
    original_sort = planner._sort_candidates  # noqa: SLF001
    mutated = False

    def sort_then_mutate(candidates, *, catalog_snapshot=None):
        nonlocal mutated
        original_sort(candidates, catalog_snapshot=catalog_snapshot)
        if not mutated:
            registry.register(_catalog_tool("late_catalog"))
            mutated = True

    monkeypatch.setattr(planner, "_sort_candidates", sort_then_mutate)

    plan = planner.plan("alpha catalog lookup")

    assert plan.registry_version == ranked_version
    assert registry.version == ranked_version + 1
    assert [(call.tool, call.endpoint) for call in plan.calls] == [
        ("alpha_catalog", "search")
    ]
    assert plan.calls[0].tool_fingerprint == original.fingerprint


class _ChurningRegistry(InMemoryRegistry):
    def __init__(self) -> None:
        super().__init__()
        self._reported_version = 0

    @property
    def version(self) -> int:
        self._reported_version += 1
        return self._reported_version


def test_non_index_snapshot_fails_deterministically_under_continuous_churn() -> None:
    registry = _ChurningRegistry()
    registry.register(_catalog_tool("alpha_catalog"))
    planner = SchemaPlanner(registry, candidate_index=False)

    with pytest.raises(
        PlanningError,
        match="registry changed repeatedly while capturing the planner catalog",
    ):
        planner.retrieve("alpha catalog lookup")
