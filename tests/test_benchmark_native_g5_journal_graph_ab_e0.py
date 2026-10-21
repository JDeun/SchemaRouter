"""Safety and provenance checks for synthetic G5 paired graph CPU E0."""
from __future__ import annotations

import json

import pytest

from scripts.benchmark_native_g5_journal_graph_ab_e0 import EVIDENCE, benchmark


def test_native_g5_paired_graph_updates_match_full_oracle_and_negative_type():
    report = benchmark(registered_routes=22, pairs=4)
    assert report["evidence_tier"] == EVIDENCE
    assert report["independent_e2_qualified"] is False
    assert report["production_p95_qualified"] is False
    assert report["no_real_provider_calls"] is True
    assert report["exact_source_native_full_graph_oracle_pairs"] == 4
    assert report["supported_typed_pairs"] == 2
    assert report["incompatible_typed_pairs"] == 2
    assert report["registered_source_routes"] == 22
    assert 0 <= report["journal_faster_pairs"] <= 4
    for mode in ("full_build", "journal_refresh"):
        for metric in ("wall_ms", "process_cpu_ms"):
            stats = report[metric][mode]
            assert 0 <= stats["p50"] <= stats["p95"] <= stats["p99"]
    serialized = json.dumps(report)
    for secret in ("contact_directory", "case_service", "customer_id"):
        assert secret not in serialized


@pytest.mark.parametrize("size,pairs", [
    (1, 2), (0, 2), (5103, 2), (True, 2), (2.5, 2),
    (22, 0), (22, 1), (22, 11), (22, False), (22, 2.5),
])
def test_native_g5_paired_graph_rejects_invalid_trials(size, pairs):
    with pytest.raises(ValueError, match="bounded native G5"):
        benchmark(registered_routes=size, pairs=pairs)
