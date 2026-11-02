"""Public Algorithm 1 planning profile is an E0 source-owned benchmark only."""
from __future__ import annotations

import pytest

from scripts.benchmark_paper_public_pipeline_e0 import (
    EVIDENCE_TIER,
    benchmark,
    build_synthetic_public_case,
)


@pytest.mark.parametrize("hops", [1, 2])
def test_public_algorithm1_pipeline_e0_500_complete_plan_oracle(hops):
    report = benchmark(500, hops=hops, repeats=1, warmup=0)
    assert report["schema_version"] == 1
    assert report["evidence_tier"] == EVIDENCE_TIER
    assert report["registered_routes"] == 500
    assert report["expected_hops"] == hops
    assert len(report["expected_route_ids"]) == hops + 1
    assert report["strict_k"] == 5
    assert len(report["source_snapshot_id"]) == 64
    assert report["prepared_build_wall_ms"] >= 0
    assert report["prepared_build_process_cpu_ms"] >= 0
    for pathway in ("prepared_sync", "prepared_async_model_stub"):
        metrics = report[pathway]
        assert metrics["exact_route_oracle"] is True
        assert metrics["receipt_bytes"] > 0
        assert metrics["wall_ms"]["p50"] >= 0
        assert metrics["wall_ms"]["p95"] >= 0
        assert metrics["wall_ms"]["p99"] >= 0
        assert metrics["process_cpu_ms"]["p99"] >= 0
    assert report["prepared_async_model_stub"]["real_model_calls"] == 0
    assert report["prepared_async_model_stub"]["provider_calls"] == 0
    assert report["independent_e2_qualified"] is False
    assert report["provider_execution_performed"] is False
    assert report["model_latency_measured"] is False


@pytest.mark.parametrize(("routes", "hops"), [
    (0, 1), (499, 1), (5001, 1), (500, 0), (500, 3),
    (True, 1), (500, True),
])
def test_public_algorithm1_pipeline_e0_rejects_invalid_registered_shape(routes, hops):
    with pytest.raises(ValueError):
        build_synthetic_public_case(routes, hops)


@pytest.mark.parametrize(("repeats", "warmup"), [
    (0, 0), (21, 0), (True, 0), (1, -1), (1, 4), (1, True),
])
def test_public_algorithm1_pipeline_e0_rejects_unbounded_bench(repeats, warmup):
    with pytest.raises(ValueError):
        benchmark(500, hops=1, repeats=repeats, warmup=warmup)
