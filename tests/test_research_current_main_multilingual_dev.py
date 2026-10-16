"""Measure only registered current-source DEV outcomes; reject misleading claims."""
from __future__ import annotations

import copy
import math
from types import SimpleNamespace

import pytest

from benchmarks.agent_utility_v5_catalog import (
    CATALOG_SIZES,
    LANGUAGES,
    STRATA,
    build_tasks,
)
from scripts.research_current_main_multilingual_dev import (
    KS,
    REPORT_SCOPE,
    evaluate,
    percentile,
    score_case,
    select_cases,
    summarize,
    validate_tasks,
)


def candidate(route_id: str) -> SimpleNamespace:
    return SimpleNamespace(
        route_id=route_id,
        model_dump=lambda **_: {"route_id": route_id},
    )


def test_frozen_public_dev_cohort_has_multilingual_and_multi_route_coverage() -> None:
    tasks = build_tasks()
    validate_tasks(tasks)
    assert len(tasks) == 240
    selected = select_cases(tasks, cases_per_group=1)
    assert len(selected) == len(LANGUAGES) * len(STRATA) == 48
    assert set(t["language"] for t in selected) == set(LANGUAGES)
    assert any(len(t["required_route_ids"]) > 1 for t in selected)
    assert any(not t["required_route_ids"] for t in selected)
    assert set(CATALOG_SIZES) == {100, 250, 500}


def test_invalid_selection_and_data_drift_fail_closed() -> None:
    tasks = build_tasks()
    for n in (0, True, 6, -1):
        with pytest.raises(ValueError):
            select_cases(tasks, cases_per_group=n)
    bad = copy.deepcopy(tasks)
    bad[1]["task_id"] = bad[0]["task_id"]
    with pytest.raises(ValueError):
        validate_tasks(bad)
    bad = copy.deepcopy(tasks)
    bad[1]["query"] = bad[0]["query"]
    with pytest.raises(ValueError):
        validate_tasks(bad)
    bad = copy.deepcopy(tasks)
    bad[0]["required_route_ids"] = ["arbitrary.private_route"]
    # A plausible-looking but unregistered route is caught when scoring.
    with pytest.raises(ValueError):
        score_case(
            bad[0], candidates=[candidate("literature.search")],
            k=3, latency_ms=0.1, all_routes={"literature.search"},
        )


def test_required_tool_sets_use_all_required_coverage_not_top1() -> None:
    case = {
        "task_id": "multi",
        "language": "ja",
        "task_stratum": "multi_step_first_hop",
        "required_route_ids": ["a.read", "b.reconcile"],
    }
    registry = {"a.read", "b.reconcile", "z.search"}
    first = score_case(
        case, candidates=[candidate("a.read"), candidate("z.search")],
        k=3, latency_ms=2, all_routes=registry,
    )
    assert first["found_required_count"] == 1
    assert first["full_coverage"] == 0
    assert first["missing_required_route_ids"] == ["b.reconcile"]
    both = score_case(
        case, candidates=[candidate("a.read"), candidate("b.reconcile")],
        k=3, latency_ms=2, all_routes=registry,
    )
    assert both["full_coverage"] == 1
    metrics = summarize([first, both])
    assert metrics["required_route_recall"] == 0.75
    assert metrics["all_required_coverage"] == 0.5


def test_unsupported_nonempty_does_not_become_unauthorized_dispatch_claim() -> None:
    case = {
        "task_id": "unsupported",
        "language": "en",
        "task_stratum": "out_of_domain",
        "required_route_ids": [],
    }
    row = score_case(
        case, candidates=[candidate("a.read")],
        k=3, latency_ms=1, all_routes={"a.read"},
    )
    metrics = summarize([row])
    assert metrics["unsupported_cases"] == 1
    assert metrics["unsupported_nonempty_shortlist_rate"] == 1
    assert metrics["required_route_recall"] is None
    assert metrics["all_required_coverage"] is None
    assert REPORT_SCOPE["tool_execution_tested"] is False
    assert REPORT_SCOPE["host_authorization_tested"] is False
    assert REPORT_SCOPE["independent_confirmation"] is False
    assert REPORT_SCOPE["may_promote"] is False
    assert REPORT_SCOPE["may_release"] is False


@pytest.mark.parametrize("value", [-1, math.inf, math.nan])
def test_bogus_latencies_rejected(value: float) -> None:
    with pytest.raises(ValueError):
        score_case(
            {"required_route_ids": [], "task_id": "x",
             "language": "en", "task_stratum": "out_of_domain"},
            candidates=[], k=3, latency_ms=value, all_routes=set(),
        )
    with pytest.raises(ValueError):
        percentile([value], 0.95)


def test_duplicate_or_undeclared_candidates_rejected() -> None:
    case = {
        "task_id": "x", "language": "ko",
        "task_stratum": "clear_single_tool",
        "required_route_ids": ["a.read"],
    }
    with pytest.raises(ValueError):
        score_case(case, candidates=[candidate("a.read"), candidate("a.read")],
                   k=3, latency_ms=1, all_routes={"a.read"})
    with pytest.raises(ValueError):
        score_case(case, candidates=[candidate("forged.write")],
                   k=3, latency_ms=1, all_routes={"a.read"})
    with pytest.raises(ValueError):
        score_case(case, candidates=[candidate("a.read")],
                   k=4, latency_ms=1, all_routes={"a.read"})


def test_current_public_planner_end_to_end_one_bounded_dev_cell() -> None:
    report = evaluate(sizes=(100,), cases_per_group=1)
    assert report["benchmark"] == "current-code-multilingual-typed-retrieval-dev"
    assert report["scope"]["agent_task_success_tested"] is False
    assert report["scope"]["required_output_field_gold_available"] is False
    assert report["cases_per_catalog"] == 48
    assert len(report["case_rows"]) == 48 * len(KS)
    assert len(report["cohorts"]) == len(KS) * len(LANGUAGES)
    assert all(x["catalog_size"] == 100 for x in report["case_rows"])
    assert {x["k"] for x in report["case_rows"]} == set(KS)
    assert all(0 <= x["found_required_count"] <= x["required_route_count"]
               for x in report["case_rows"])
    assert all(len(x["selected_route_ids"]) <= x["k"] for x in report["case_rows"])


@pytest.mark.parametrize("sizes", [(250, 100), (100, 100), (50,), ()])
def test_invalid_benchmark_sizes_rejected(sizes: tuple[int, ...]) -> None:
    with pytest.raises(ValueError):
        evaluate(sizes=sizes, cases_per_group=1)
