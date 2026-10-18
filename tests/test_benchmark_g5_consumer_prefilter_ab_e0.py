"""Same-source G5 canonical graph prefilter E0 AB instrumentation."""
from __future__ import annotations

import json

import pytest

from scripts.benchmark_g5_consumer_prefilter_ab_e0 import (
    EVIDENCE,
    benchmark_ab,
)


def test_paired_same_process_toggles_only_structural_candidate_superset():
    report = benchmark_ab(noise_routes=24, iterations=3)
    assert report["evidence_tier"] == EVIDENCE
    assert report["independent_e2_qualified"] is False
    assert report["registered_source_routes"] == 26
    assert report["broad_semantic_postings"] == 24
    assert report["canonical_graph_edge_count"] == 1
    assert report["same_original_source_and_graph"] is True
    assert report["measured_ab_cycles"] == 3
    assert report["warmup_ab_cycles"] == 2
    cases = report["query_wall_ms"]
    assert set(cases) == {
        "canonical_prefilter_enabled",
        "canonical_prefilter_disabled_superset",
    }
    for row in cases.values():
        assert 0 <= row["p50"] <= row["p95"] <= row["p99"]
    output = json.dumps(report, ensure_ascii=False)
    for sensitive in ("contact_directory", "customer_id", "case_service", "required_routes"):
        assert sensitive not in output


@pytest.mark.parametrize("routes,reps", (
    (0, 3), (10001, 3), (True, 3),
    (2, 0), (2, 2), (2, 11), (2, False),
))
def test_ab_script_refuses_invalid_load_and_sample_count(routes, reps):
    with pytest.raises(ValueError, match="invalid bounded"):
        benchmark_ab(noise_routes=routes, iterations=reps)
