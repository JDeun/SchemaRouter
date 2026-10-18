"""Ensure benchmark shape and eligibility without promoting synthetic results."""
from __future__ import annotations

import json

import pytest

from scripts.benchmark_indexed_native_graph_g5_cpu_e0 import (
    EVIDENCE,
    benchmark,
)


def test_small_g5_benchmark_returns_only_bounded_aggregate_telemetry():
    report = benchmark(noise_routes=18, iterations=12)
    assert report["evidence_tier"] == EVIDENCE
    assert report["independent_e2_qualified"] is False
    assert report["synthetic_registered_routes"] == 20
    assert report["graph_roots"] == 1
    assert report["graph_consumers"] == 1
    assert report["verified_candidate_paths"] == 1
    assert report["strict_k"] == 5
    assert report["measured_queries"] == 12
    assert report["warmup_queries"] == 5
    assert report["peak_process_rss_kib"] > 0
    for kind in ("query_wall_ms", "query_process_cpu_ms"):
        stats = report[kind]
        assert 0 <= stats["p50"] <= stats["p95"] <= stats["p99"]
    serialized = json.dumps(report, ensure_ascii=False)
    assert "contact_directory" not in serialized
    assert "case_service" not in serialized
    assert "customer_id" not in serialized
    assert "required_routes" not in serialized
    assert "task_complete" not in serialized
    assert "Synthetic" not in report["evidence_tier"]


@pytest.mark.parametrize("bad_noise,bad_runs", (
    (-1, 10), (10001, 10), (False, 10),
    (2, 0), (2, 9), (2, 201), (2, 10.0),
))
def test_benchmark_rejects_out_of_budget_or_noninteger_calls(bad_noise, bad_runs):
    with pytest.raises(ValueError, match="bounded synthetic"):
        benchmark(noise_routes=bad_noise, iterations=bad_runs)
