"""Paired catalog quality cost evidence must not reward failed retrieval."""
from __future__ import annotations

import pytest

from scripts.benchmark_realistic_break_even import Case
from scripts.research_paired_context_frontier_e0 import (
    MAX_K,
    analyze_paired_cases,
    evaluate,
)


def _case(supported: bool, route: str | None) -> Case:
    return Case(
        query="dev synthetic",
        request=None,  # only nonmodel pre-agent selection witnesses are evaluated
        required_tool=route,
        required_field=None,
        supported=supported,
    )


def test_quality_conditioned_cost_excludes_one_sided_retrieval_failures():
    cases = [_case(True, "source_a"), _case(True, "source_a"), _case(False, None)]
    metrics = analyze_paired_cases(
        cases,
        [["source_a", "noise"], [], ["noise"]],
        [["source_a"], ["source_a"], []],
        {"source_a": 100, "noise": 100},
    )
    assert metrics["paired_required_route"] == {
        "both_hit": 1, "lexical_only_hit": 0,
        "indexed_only_hit": 1, "neither_hit": 0,
    }
    assert metrics["paired_no_fit"]["indexed_only_no_fit"] == 1
    assert metrics["quality_conditioned_supported"] == {
        "both_hit_case_count": 1,
        "schema_lexical_mean_bytes": 200,
        "indexed_default_mean_bytes": 100,
        "indexed_cheaper_count": 1,
        "lexical_cheaper_count": 0,
        "equal_bytes_count": 0,
    }
    assert metrics["lexical_case_correct"] == 1
    assert metrics["indexed_case_correct"] == 3


def test_no_shared_correct_positive_means_no_claimable_cost_estimate():
    result = analyze_paired_cases(
        [_case(True, "source_a")], [["source_a"]], [[]],
        {"source_a": 123},
    )
    eligible = result["quality_conditioned_supported"]
    assert eligible["both_hit_case_count"] == 0
    assert eligible["schema_lexical_mean_bytes"] is None
    assert eligible["indexed_default_mean_bytes"] is None


@pytest.mark.parametrize("bad", [
    [["source_a", "source_a"]],
    [["invented"]],
    [["source_a"] * (MAX_K + 1)],
    [("source_a",)],
    [[42]],
])
def test_rejects_unsafe_or_unregistered_candidate_sets(bad):
    with pytest.raises(ValueError):
        analyze_paired_cases(
            [_case(True, "source_a")], bad, [["source_a"]],
            {"source_a": 1},
        )


def test_fixed_dev_small_matrix_is_labelled_non_graph_and_not_e2():
    r = evaluate(sizes=(20,))
    assert r["evidence_tier"] == "E0_DEVELOPER_AUTHORED_SYNTHETIC"
    assert r["default_indexed_is_g5_graph"] is False
    assert r["all_model_tokens_measured"] is False
    assert r["source_disjoint_external_e2_qualified"] is False
    assert r["independent_e2_qualified"] is False
    assert r["release_qualified"] is False
    assert len(r["matrix"]) == 3
    for row in r["matrix"]:
        assert row["catalog_size"] == 20
        assert row["supported"] >= 1 and row["unsupported"] >= 1
        assert row["paired_required_route"]["both_hit"] <= row["supported"]
        assert row["lexical_case_correct"] <= row["case_count"]
        assert row["indexed_case_correct"] <= row["case_count"]
        assert row["full_catalog_contract_bytes"] > 0
