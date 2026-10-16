"""Gold-blind retrieval vs hypothetical gold-informed pool ceiling regressions."""
from __future__ import annotations

import math

import pytest

from benchmarks.agent_utility_v5_catalog import build_tasks
from scripts.research_candidate_pool_ceiling_dev import (
    CLAIMS,
    POOL_SIZES,
    cohort_summary,
    evaluate,
    measure_case,
    percentile,
)


def _case(gold: list[str]) -> dict:
    return {
        "task_id": "newly-authored-test-case",
        "language": "ja",
        "task_stratum": "multi_step_first_hop",
        "required_route_ids": gold,
    }


def test_pool_24_cannot_recover_absent_required_route_by_reordering() -> None:
    available = {"a.read", "b.write", "c.list"}
    scored = measure_case(
        case=_case(["a.read", "b.write"]),
        retrieved_ids=["a.read", "c.list"],
        all_routes=available, width=24, retrieval_ms=0.2,
    )
    assert scored["actually_in_top5"] == 1
    assert scored["top5_oracle_upper_bound_found"] == 1
    assert scored["top5_oracle_upper_bound_full_coverage"] is False
    assert scored["missing_from_pool"] == ["b.write"]


def test_large_pool_has_theoretical_recall_not_achieved_score() -> None:
    routes = [f"x.item{i}" for i in range(20)]
    scored = measure_case(
        case=_case([routes[0], routes[-1]]),
        retrieved_ids=routes, all_routes=set(routes),
        width=24, retrieval_ms=0.2,
    )
    assert scored["actually_in_top5"] == 1
    assert scored["top5_oracle_upper_bound_found"] == 2
    assert scored["top5_oracle_upper_bound_full_coverage"] is True
    summary = cohort_summary([scored])
    assert summary["actual_top5_route_recall"] == 0.5
    assert summary["potential_top5_oracle_recall"] == 1.0
    assert CLAIMS["independent_confirmation"] is False
    assert CLAIMS["may_promote_to_product"] is False
    assert CLAIMS["agent_task_success"] is False


def test_unsupported_does_not_count_as_unauthorized_execution() -> None:
    scored = measure_case(
        case=_case([]),
        retrieved_ids=["a.read"], all_routes={"a.read"},
        width=24, retrieval_ms=0.0,
    )
    assert scored["required"] == 0
    assert scored["top5_observed_full_coverage"] is False
    assert scored["top5_oracle_upper_bound_full_coverage"] is False
    assert cohort_summary([scored])["actual_top5_route_recall"] is None
    assert CLAIMS["executable_tool_calls"] == 0


@pytest.mark.parametrize("returned", [
    ["a.read", "a.read"],
    ["a.read", "unknown.write"],
])
def test_forged_or_repeated_candidate_rejected(returned: list[str]) -> None:
    with pytest.raises(ValueError):
        measure_case(
            case=_case(["a.read"]),
            retrieved_ids=returned, all_routes={"a.read"},
            width=24, retrieval_ms=1.0,
        )


@pytest.mark.parametrize("bad_width, bad_latency", [
    (32, 0.5),
    (24, math.nan),
    (24, -1.0),
])
def test_unregistered_width_or_measurements_rejected(
    bad_width: int, bad_latency: float,
) -> None:
    with pytest.raises(ValueError):
        measure_case(
            case=_case(["a.read"]),
            retrieved_ids=["a.read"], all_routes={"a.read"},
            width=bad_width, retrieval_ms=bad_latency,
        )


def test_ceiling_only_for_legal_registered_pool_sizes() -> None:
    assert POOL_SIZES == (24, 64, 128)
    for bad in (0, 6, -1, True):
        with pytest.raises(ValueError):
            evaluate(cases_per_group=bad)
    with pytest.raises(ValueError):
        percentile([1.0, math.inf])


def test_exact_current_public_planner_fetches_wider_real_pools() -> None:
    result = evaluate(cases_per_group=1)
    assert result["candidate_pools"] == [24, 64, 128]
    assert result["catalog_sizes"] == [100, 250, 500]
    assert result["actual_retrieval_calls"] == 3 * 48 * 3
    assert len(result["cohorts"]) == 3 * 3 * 6
    assert all(
        len(row["returned_route_ids"]) <= row["pool"]
        for row in result["raw_cases"]
    )
    assert result["scope"]["independent_confirmation"] is False
    assert result["scope"]["may_release"] is False
    assert result["scope"]["executable_tool_calls"] == 0
    assert "oracle" in result["interpretation"].lower() or (
        "Upper bounds" in result["interpretation"]
    )
    assert len(build_tasks()) == 240
