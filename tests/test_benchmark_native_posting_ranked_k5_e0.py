"""E0 source-paired K5 timing smoke; results are deliberately not E2 scores."""
import pytest

from scripts.benchmark_native_posting_ranked_k5_e0 import benchmark


def test_pairwise_indexed_decision_stage_uses_identical_source_and_k5():
    result = benchmark(registered_routes=500, iterations=3)
    assert result["independent_quality_evidence"] is False
    assert result["independent_e2_qualified"] is False
    assert result["real_model_or_provider_called"] is False
    assert result["query_encodes_expected_route"] is True
    assert result["new_default_routing"] is False
    assert result["queries"] == 18
    assert result["strict_k"] == 5
    assert result["ranker_candidate_cap"] == 32
    assert result["max_model_input_bytes"] <= 16_384
    assert result["source_scoped_ranker_calls"] == 18 * (3 + 1)
    exposure = result["synthetic_target_exposure"]
    assert exposure == {
        "default_abstain_hits": 0,
        "fixed_first5_hits": 15,
        "decision_ranker_hits": 18,
        "denominator": 18,
    }
    assert result["safety_statuses"] == {
        "one": "complete", "none": "no_proven_hit",
        "hidden": "no_proven_hit", "health": "complete",
    }
    for arm in ("default", "decision_ranker"):
        for metric in ("wall_ms", "process_cpu_ms"):
            assert result[arm][metric]["p50"] >= 0.0
            assert result[arm][metric]["p95"] >= result[arm][metric]["p50"]
            assert result[arm][metric]["p99"] >= result[arm][metric]["p95"]


@pytest.mark.parametrize("count", (0, True, 499, 5001, "500"))
def test_benchmark_rejects_unregistered_catalog_shapes(count):
    with pytest.raises(ValueError, match="500/5000"):
        benchmark(registered_routes=count, iterations=3)


@pytest.mark.parametrize("iterations", (0, True, 1, 2, 13, "3"))
def test_benchmark_rejects_unbounded_iteration_counts(iterations):
    with pytest.raises(ValueError, match="bounded 3-12"):
        benchmark(registered_routes=500, iterations=iterations)
