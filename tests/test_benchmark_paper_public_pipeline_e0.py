"""Public Algorithm 1 planning profile is an E0 source-owned benchmark only."""
from __future__ import annotations

from dataclasses import replace

import pytest

from schemarouter.native_graph_index import NativeSchemaGraphIndex
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


@pytest.mark.parametrize(("routes", "hops"), [
    (500, 1), (500, 2), (5000, 2),
])
def test_public_algorithm1_refresh_profile_matches_cold_public_snapshot(routes, hops):
    report = benchmark(
        routes, hops=hops, repeats=2, warmup=0, measure_refresh=True,
    )
    assert report["schema_version"] == 2
    assert report["registered_routes"] == routes
    assert report["strict_k"] == 5
    refreshed = report["incremental_refresh"]
    assert refreshed["measured_changes"] == 2
    assert refreshed["registered_routes"] == routes
    assert refreshed["source_snapshot_matches_cold"] is True
    assert refreshed["stale_sessions_rejected"] is True
    assert refreshed["exact_route_oracle"] is True
    assert refreshed["expected_route_ids"] == report["expected_route_ids"]
    assert refreshed["model_calls"] == refreshed["provider_calls"] == 0
    for phase in ("journal_refresh", "cold_rebuild"):
        for measure in ("wall_ms", "process_cpu_ms"):
            assert set(refreshed[phase][measure]) == {"p50", "p95", "p99"}
            assert all(value >= 0 for value in refreshed[phase][measure].values())


@pytest.mark.parametrize("invalid", [0, 1, "true", None])
def test_public_algorithm1_refresh_profile_rejects_nonboolean_opt_in(invalid):
    with pytest.raises(ValueError):
        benchmark(500, repeats=1, warmup=0, measure_refresh=invalid)


def test_public_algorithm1_refresh_profile_rejects_graph_parity_drift(monkeypatch):
    """A postings-identical but different canonical graph must fail the E0 oracle."""
    original = NativeSchemaGraphIndex.refresh_from_inmemory_journal.__func__

    def corrupt_graph(cls, previous, registry):
        refreshed = original(cls, previous, registry)
        wrong = refreshed.graph.model_copy(deep=True)
        wrong.capability_ids = (*wrong.capability_ids, "unreviewed.ghost")
        return replace(refreshed, graph=wrong)

    monkeypatch.setattr(
        NativeSchemaGraphIndex, "refresh_from_inmemory_journal",
        classmethod(corrupt_graph),
    )
    with pytest.raises(AssertionError, match="graph|parity|snapshot"):
        benchmark(500, hops=2, repeats=1, warmup=0, measure_refresh=True)
