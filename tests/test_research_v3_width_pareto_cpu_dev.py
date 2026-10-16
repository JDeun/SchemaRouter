"""Review the bounded source-backed width/CPU Pareto experiment."""
from __future__ import annotations

import math

import pytest

from scripts.research_v1_v2_paired_cpu_dev import frozen_genomes
from scripts.research_v3_width_pareto_cpu_dev import (
    MAX_V1_P95_MULTIPLIER,
    WIDTHS,
    assess,
    evaluate_width,
    p95,
    preload,
)


def test_reviewed_widths_and_actual_historical_incumbent() -> None:
    first, challenger, _ = frozen_genomes()
    assert WIDTHS == (24, 32, 40, 48, 56, 64)
    assert first["width"] == 24
    assert challenger["width"] == 64
    assert MAX_V1_P95_MULTIPLIER == 1.5


def test_cpu_percentile_fails_closed_on_nonfinite_inputs() -> None:
    for bad in ([], [math.inf], [-1.0], [math.nan]):
        with pytest.raises(ValueError):
            p95(bad)
    assert p95([2.0, 1.0, 5.0]) == 5.0


@pytest.mark.parametrize("bad", [0, -1, 6, True])
def test_no_unregistered_exposed_dev_row_budget(bad: int) -> None:
    with pytest.raises(ValueError):
        preload(cases_per_group=bad)
    with pytest.raises(ValueError):
        assess(cases_per_group=bad)


def test_no_unregistered_width_or_missing_tasks() -> None:
    _, v2, _ = frozen_genomes()
    for wrong in (0, 23, 25, 128, True):
        with pytest.raises(ValueError):
            evaluate_width([], width=wrong, weights=v2["weights"])


def test_real_current_api_comparison_at_all_reviewed_widths() -> None:
    result = assess(cases_per_group=1)
    assert result["id"] == "frozen_V1_V2_intermediate_width_retrospective_DEV"
    assert result["registered_pool_widths"] == list(WIDTHS)
    assert result["cases_per_candidate"] == 3 * 48
    assert result["actual_current_planner_retrieval_calls"] == 3 * 48 * 6
    assert result["v1_baseline"]["width"] == 24
    assert len(result["attempts"]) == len(WIDTHS)
    for row in result["attempts"]:
        assert row["strict_pairing_guard"]["can_merge_product_code"] is False
        assert row["measured_retrieval_plus_ranking_p95_ms"] > 0
        assert row["passes_all_retrospective_dev_guards"] in (False, True)
        assert len(row["cohorts"]) == 3 * 6 * 3
    assert result["source_scope"]["independent_confirmation"] is False
    assert result["source_scope"]["automatic_product_change"] is False
    assert result["source_scope"]["may_release"] is False
    if result["best_retrospective_DEV_candidate"] is not None:
        assert result["best_retrospective_DEV_candidate"]["pool_width"] in WIDTHS
