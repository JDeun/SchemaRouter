"""Actual registered 500/5000-route Rank oracle and source-bounded metrics."""

import pytest

from scripts.benchmark_paper_native_rank_b1 import benchmark_paper_rank


@pytest.mark.parametrize("routes", [500, 5000])
def test_original_paper_rank_benchmark_has_independent_topk_oracle(routes):
    report = benchmark_paper_rank(routes, repeats=1)
    assert report["registered_routes"] == routes
    assert report["qualified_routes"] > 5
    assert report["ranked_k"] == 5
    assert len(set(report["oracle_top_k"])) == 5
    assert report["serialized_receipt_bytes"] < 10000
    assert report["median_lookup_cpu_ms"] >= 0
    assert report["lookup_wall_ms"]["p95"] >= report["lookup_wall_ms"]["p50"]
    assert report["lookup_cpu_ms"]["p99"] >= report["lookup_cpu_ms"]["p95"]
    assert report["evidence_tier"] == "E0_SYNTHETIC_NOT_PUBLISHER_E2"


def test_original_paper_rank_benchmark_rejects_unbounded_work():
    with pytest.raises(ValueError):
        benchmark_paper_rank(600)
    with pytest.raises(ValueError):
        benchmark_paper_rank(500, repeats=11)
