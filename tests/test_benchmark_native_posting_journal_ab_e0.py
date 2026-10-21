"""Bounded E0 posting-index benchmark telemetry; no production latency claim."""
from __future__ import annotations

import json

import pytest

from scripts.benchmark_native_posting_journal_ab_e0 import EVIDENCE, benchmark


def test_paired_native_posting_journal_benchmark_oracle():
    report = benchmark(registered_routes=24, pairs=2)
    assert report["evidence_tier"] == EVIDENCE
    assert report["independent_e2_qualified"] is False
    assert report["production_p95_qualified"] is False
    assert report["graph_delta_included"] is False
    assert report["registered_source_routes"] == 24
    assert report["paired_samples"] == 2
    assert report["exact_full_build_index_oracle_pairs"] == 2
    assert report["peak_process_rss_kib"] > 0
    assert 0 <= report["delta_faster_pairs"] <= 2
    for arm in ("full_rebuild", "journal_refresh"):
        for metric in ("wall_ms", "process_cpu_ms"):
            stat = report[metric][arm]
            assert 0 <= stat["p50"] <= stat["p95"] <= stat["p99"]
    output = json.dumps(report)
    assert "contact_directory" not in output
    assert "case_service" not in output
    assert "customer_id" not in output


@pytest.mark.parametrize("n,k", [
    (0, 2), (1, 2), (5103, 2), (False, 2), (3.2, 2),
    (24, 0), (24, 1), (24, 13), (24, True), (24, 2.5),
])
def test_paired_journal_benchmark_rejects_invalid_or_oversize(n, k):
    with pytest.raises(ValueError, match="bounded source-native"):
        benchmark(registered_routes=n, pairs=k)
