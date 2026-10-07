from __future__ import annotations

import pytest

from schemarouter.models import PlanCoverage, SemanticFieldRequirement, ToolCall
from schemarouter.planning_stages import (
    assemble_execution_plan,
    run_candidate_pipeline_async,
    run_candidate_pipeline_sync,
    select_fallbacks_async,
    select_fallbacks_sync,
    select_primary_candidates_async,
    select_primary_candidates_sync,
)


def test_sync_candidate_pipeline_preserves_explicit_stage_order() -> None:
    calls: list[str] = []

    def recall(context: str) -> list[int]:
        assert context == "snapshot-context"
        calls.append("recall")
        return [1, 2]

    def augment(context: str, candidates: list[int]) -> tuple[list[int], list[str]]:
        assert context == "snapshot-context"
        assert candidates == [1, 2]
        calls.append("augment")
        return [1, 2, 3], ["recall-warning"]

    def coverage(context: str, candidates: list[int]) -> set[str]:
        assert context == "snapshot-context"
        assert candidates == [1, 2, 3]
        calls.append("coverage")
        return {"required-field"}

    def capability_fit(
        context: str,
        candidates: list[int],
    ) -> tuple[list[int], list[str]]:
        assert context == "snapshot-context"
        calls.append("capability_fit")
        return [2, 3], ["fit-warning"]

    def operation_fit(
        context: str,
        candidates: list[int],
    ) -> tuple[list[int], list[str]]:
        assert context == "snapshot-context"
        assert candidates == [2, 3]
        calls.append("operation_fit")
        return [3], ["operation-warning"]

    def disambiguate(
        context: str,
        candidates: list[int],
    ) -> tuple[list[int], list[str]]:
        assert context == "snapshot-context"
        assert candidates == [3]
        calls.append("disambiguate")
        return candidates, ["disambiguation-warning"]

    def decide(
        context: str,
        candidates: list[int],
    ) -> tuple[list[int], list[str]]:
        assert context == "snapshot-context"
        assert candidates == [3]
        calls.append("decide")
        return [3, 4], ["decision-warning"]

    def order(context: str, candidates: list[int]) -> list[int]:
        assert context == "snapshot-context"
        assert candidates == [3, 4]
        calls.append("order")
        return [4, 3]

    result = run_candidate_pipeline_sync(
        context="snapshot-context",
        recall=recall,
        augment=augment,
        coverage=coverage,
        capability_fit=capability_fit,
        operation_fit=operation_fit,
        disambiguate=disambiguate,
        decide=decide,
        order=order,
    )

    assert calls == [
        "recall",
        "augment",
        "coverage",
        "capability_fit",
        "operation_fit",
        "disambiguate",
        "decide",
        "order",
    ]
    assert result.all_candidates == (1, 2, 3)
    assert result.candidates == (4, 3)
    assert result.required_coverage == frozenset({"required-field"})
    assert result.warnings == (
        "recall-warning",
        "fit-warning",
        "operation-warning",
        "disambiguation-warning",
        "decision-warning",
    )


@pytest.mark.asyncio
async def test_async_candidate_pipeline_matches_sync_stage_contract() -> None:
    calls: list[str] = []

    def recall(context: str) -> list[int]:
        calls.append("recall")
        return [1]

    async def augment(
        context: str,
        candidates: list[int],
    ) -> tuple[list[int], list[str]]:
        calls.append("augment")
        return [1, 2], ["recall-warning"]

    def coverage(context: str, candidates: list[int]) -> set[str]:
        calls.append("coverage")
        return {"field"}

    async def capability_fit(
        context: str,
        candidates: list[int],
    ) -> tuple[list[int], list[str]]:
        calls.append("capability_fit")
        return candidates, []

    async def operation_fit(
        context: str,
        candidates: list[int],
    ) -> tuple[list[int], list[str]]:
        calls.append("operation_fit")
        return candidates, []

    async def disambiguate(
        context: str,
        candidates: list[int],
    ) -> tuple[list[int], list[str]]:
        calls.append("disambiguate")
        return candidates, []

    async def decide(
        context: str,
        candidates: list[int],
    ) -> tuple[list[int], list[str]]:
        calls.append("decide")
        return candidates, ["decision-warning"]

    def order(context: str, candidates: list[int]) -> list[int]:
        calls.append("order")
        return list(reversed(candidates))

    result = await run_candidate_pipeline_async(
        context="snapshot-context",
        recall=recall,
        augment=augment,
        coverage=coverage,
        capability_fit=capability_fit,
        operation_fit=operation_fit,
        disambiguate=disambiguate,
        decide=decide,
        order=order,
    )

    assert calls == [
        "recall",
        "augment",
        "coverage",
        "capability_fit",
        "operation_fit",
        "disambiguate",
        "decide",
        "order",
    ]
    assert result.all_candidates == (1, 2)
    assert result.candidates == (2, 1)
    assert result.required_coverage == frozenset({"field"})
    assert result.warnings == ("recall-warning", "decision-warning")



def test_sync_primary_selection_covers_required_fields() -> None:
    coverage_by_candidate = {
        "a": {"x"},
        "b": {"y"},
        "c": {"y"},
    }

    result = select_primary_candidates_sync(
        candidates=["a", "b", "c"],
        max_calls=3,
        retrieval_mode="coverage",
        required_coverage={"stale"},
        coverage_matrix=lambda candidates: (
            [coverage_by_candidate[candidate] for candidate in candidates],
            {"x", "y"},
        ),
        compile_candidate=lambda candidate: candidate.upper(),
        provider_key=lambda candidate: candidate,
        corroboration_compatible=lambda *_args: True,
        selected_coverage=lambda candidate, _call: coverage_by_candidate[candidate],
    )

    assert result.pairs == (("a", "A"), ("b", "B"))
    assert result.required_coverage == frozenset({"x", "y"})


@pytest.mark.asyncio
async def test_async_primary_selection_preserves_corroboration_provider_diversity() -> None:
    providers = {
        "a1": "provider-a",
        "a2": "provider-a",
        "b1": "provider-b",
    }

    async def compile_candidate(candidate: str) -> str:
        return candidate.upper()

    result = await select_primary_candidates_async(
        candidates=["a1", "a2", "b1"],
        max_calls=3,
        retrieval_mode="corroborate",
        required_coverage={"field"},
        coverage_matrix=lambda candidates: (
            [{"field"} for _candidate in candidates],
            {"field"},
        ),
        compile_candidate=compile_candidate,
        provider_key=lambda candidate: providers[candidate],
        corroboration_compatible=lambda *_args: True,
        selected_coverage=lambda _candidate, _call: {"field"},
    )

    assert result.pairs == (("a1", "A1"), ("b1", "B1"))
    assert result.required_coverage == frozenset({"field"})



def test_sync_fallback_stage_filters_and_bounds_alternatives() -> None:
    result = select_fallbacks_sync(
        primary_pairs=(("primary", "P"),),
        all_candidates=("primary", "write", "alt1", "alt2"),
        fallback_scope="same_provider",
        max_fallbacks=1,
        is_read_only=lambda candidate: candidate != "write",
        ordered_candidates=lambda _primary, _all, _scope: [
            "write",
            "alt1",
            "alt2",
        ],
        compile_candidate=lambda candidate: candidate.upper(),
        is_executable=lambda _call: True,
        compatible=lambda _pc, _pcall, candidate, _call: candidate != "alt2",
    )

    assert result.routes == ((0, ("ALT1",)),)


@pytest.mark.asyncio
async def test_async_fallback_stage_preserves_executable_compatibility_gates() -> None:
    async def compile_candidate(candidate: str) -> str | None:
        if candidate == "missing":
            return None
        return candidate.upper()

    result = await select_fallbacks_async(
        primary_pairs=(("primary", "P"),),
        all_candidates=("primary", "missing", "blocked", "good"),
        fallback_scope="global",
        max_fallbacks=3,
        is_read_only=lambda _candidate: True,
        ordered_candidates=lambda _primary, _all, _scope: [
            "missing",
            "blocked",
            "good",
        ],
        compile_candidate=compile_candidate,
        is_executable=lambda call: call != "BLOCKED",
        compatible=lambda _pc, _pcall, _candidate, _call: True,
    )

    assert result.routes == ((0, ("GOOD",)),)

def test_final_plan_assembly_preserves_fallback_coverage_and_warnings() -> None:
    primary_call = ToolCall(
        tool="demo",
        endpoint="primary",
        schema_fingerprint="primary-schema",
    )
    fallback_call = ToolCall(
        tool="demo",
        endpoint="fallback",
        schema_fingerprint="fallback-schema",
    )
    fallback_selection = select_fallbacks_sync(
        primary_pairs=(("primary", primary_call),),
        all_candidates=("primary", "fallback"),
        fallback_scope="same_provider",
        max_fallbacks=1,
        is_read_only=lambda _candidate: True,
        ordered_candidates=lambda _primary, _all, _scope: ["fallback"],
        compile_candidate=lambda _candidate: fallback_call,
        is_executable=lambda call: call.executable,
        compatible=lambda *_args: True,
    )

    requirement = SemanticFieldRequirement(semantic_id="field")

    def plan_coverage(
        required: frozenset[str],
        covered: set[str],
        candidates: list[str],
    ) -> PlanCoverage:
        assert required == frozenset({"field"})
        assert covered == set()
        assert candidates == ["primary", "fallback"]
        return PlanCoverage(
            required=[requirement],
            covered=[],
            uncovered=[requirement],
            complete=False,
        )

    plan = assemble_execution_plan(
        query="demo query",
        registry_version=7,
        primary_pairs=(("primary", primary_call),),
        all_candidates=["primary", "fallback"],
        fallback_selection=fallback_selection,
        required_coverage=frozenset({"field"}),
        warnings=["existing warning"],
        selected_coverage=lambda _candidate, _call: set(),
        plan_coverage=plan_coverage,
        coverage_warning=lambda coverage: (
            "coverage warning"
            if coverage is not None and not coverage.complete
            else None
        ),
    )

    assert plan.query == "demo query"
    assert plan.registry_version == 7
    assert plan.calls == [primary_call]
    assert len(plan.fallback_routes) == 1
    assert plan.fallback_routes[0].primary_call_index == 0
    assert plan.fallback_routes[0].alternatives == [fallback_call]
    assert plan.coverage is not None
    assert plan.coverage.uncovered == [requirement]
    assert plan.warnings == ["existing warning", "coverage warning"]

