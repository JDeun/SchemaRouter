"""#1560: original-source fork benchmark telemetry and oracle E0 contracts."""
from __future__ import annotations

import pytest

from scripts.benchmark_native_fork_fieldgroup_e0 import (
    EVIDENCE,
    benchmark,
    build_fixture,
    exhaustive_source_fork_reference,
)


def test_native_fork_500_source_index_matches_original_exhaustive_scan():
    router = build_fixture(500)
    assert router.registry.version == 500
    assert exhaustive_source_fork_reference(router) == (
        ("fork_origin.read", "fork_status.read", "fork_owner.read"),
    )


def test_native_fork_500_benchmark_reports_only_limited_e0_evidence():
    result = benchmark(registered_routes=500, iterations=10)
    assert result["evidence_tier"] == EVIDENCE
    assert result["independent_e2_qualified"] is False
    assert result["registered_native_routes"] == 500
    assert result["exhaustive_original_source_forks"] == 1
    assert result["verified_source_pinned_forks"] == 1
    assert result["en_ko_ja_exact_fieldgroup_parity"] is True
    assert result["same_snapshot_health_revocation_refused"] is True
    assert result["schema_execution_authority"] is False
    assert result["strict_k"] == 5
    assert result["sample_count"] == 10
    for label in ("query_wall_ms", "query_process_cpu_ms"):
        for key in ("p50", "p95", "p99"):
            assert result[label][key] >= 0
    assert result["peak_process_rss_kib"] > 0
    assert result["limitations"]


@pytest.mark.parametrize("size", (0, 499, 501, 5001, True))
def test_native_fork_benchmark_rejects_non_preregistered_catalogs(size):
    with pytest.raises(ValueError, match="500/5000"):
        build_fixture(size)


@pytest.mark.parametrize("count", (0, 9, 101, True, 10.5))
def test_native_fork_benchmark_rejects_invalid_sample_count(count):
    with pytest.raises(ValueError, match="bounded E0"):
        benchmark(registered_routes=500, iterations=count)
