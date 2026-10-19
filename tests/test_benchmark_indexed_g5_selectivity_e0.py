"""G5 controlled synthetic selectivity contrast: integrity, not E2 claims."""
from __future__ import annotations

import json

import pytest

from scripts.benchmark_indexed_g5_selectivity_e0 import (
    EVIDENCE,
    benchmark_selectivity,
)


def test_same_native_index_scopes_exact_k_and_never_leaks_gold_paths():
    report = benchmark_selectivity(noise_routes=25, iterations=10,
                                   broad_iterations=2)
    assert report["evidence_tier"] == EVIDENCE
    assert report["independent_e2_qualified"] is False
    assert report["provider_network_or_model_calls"] == 0
    assert report["synthetic_registered_routes"] == 33
    assert report["graph_roots"] == 1
    assert report["graph_consumers"] == 7
    assert report["broad_posting_count"] == 25
    assert report["strict_k"] == 5
    assert report["peak_process_rss_kib"] > 0
    cases = report["scenarios"]
    assert len(cases) == 7
    for case, expected in (
        ("one_authorized", 1),
        ("five_authorized", 5),
        ("seven_eligible_overflow", 7),
        ("root_denied", 0),
        ("root_identifier_hidden", 0),
        ("two_consumers_unavailable", 5),
        ("broad_semantic_no_path", 0),
    ):
        row = cases[case]
        assert row["verified_path_count"] == expected
        assert row["returned_path_count"] == (expected if expected <= 5 else 0)
        assert row["status"] == (
            "over_k_unranked" if expected > 5
            else "no_proven_hit" if expected == 0 else "complete"
        )
        assert row["measured_queries"] >= 2
        assert 0 <= row["wall_ms"]["p50"] <= row["wall_ms"]["p95"]
        assert row["wall_ms"]["p95"] <= row["wall_ms"]["p99"]
        assert 0 <= row["process_cpu_ms"]["p50"] <= row["process_cpu_ms"]["p99"]
    payload = json.dumps(report, ensure_ascii=False)
    for secret in (
        "contact_directory", "case_service", "case_variant_",
        "customer_id", "expected_routes", "gold_answer",
    ):
        assert secret not in payload
    assert "independent" in " ".join(report["limitations"]).lower()


@pytest.mark.parametrize("noise,loops,broad", (
    (0, 10, 2), (10001, 10, 2), (True, 10, 2),
    (5, 9, 2), (5, 101, 2), (5, 10.0, 2),
    (5, 10, 1), (5, 10, 11), (5, 10, False),
))
def test_reject_misconfigured_or_expensive_benchmark(noise, loops, broad):
    with pytest.raises(ValueError, match="invalid bounded"):
        benchmark_selectivity(
            noise_routes=noise, iterations=loops, broad_iterations=broad,
        )
