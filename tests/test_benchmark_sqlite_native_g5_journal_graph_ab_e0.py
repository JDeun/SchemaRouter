"""Synthetic SQLite WAL native G5 whole-graph paired timing E0 gates."""
from __future__ import annotations

import json

import pytest

from scripts.benchmark_sqlite_native_g5_journal_graph_ab_e0 import (
    EVIDENCE,
    benchmark,
)


def test_sqlite_g5_graph_paired_oracle_and_two_sided_typed_no_fit():
    report = benchmark(registered_routes=22, pairs=4)
    assert report["evidence_tier"] == EVIDENCE
    assert report["registered_source_routes"] == 22
    assert report["paired_samples"] == 4
    assert report["exact_source_native_full_graph_oracle_pairs"] == 4
    assert report["supported_typed_pairs"] == 2
    assert report["incompatible_typed_pairs"] == 2
    assert report["source"] == (
        "builtin_sqlite_registry_wal_synthetic_uncontended_local_file"
    )
    assert report["measures"] == (
        "durable_sqlite_posting_plus_canonical_onehop_graph_update_only"
    )
    assert report["independent_e2_qualified"] is False
    assert report["production_p95_qualified"] is False
    assert report["no_real_provider_calls"] is True
    assert 0 <= report["journal_faster_pairs"] <= 4
    for mode in ("full_build", "journal_refresh"):
        for metric in ("wall_ms", "process_cpu_ms"):
            stats = report[metric][mode]
            assert 0 <= stats["p50"] <= stats["p95"] <= stats["p99"]
    result_text = json.dumps(report)
    for original_source in (
        "contact_directory", "case_service", "customer_id", "source.sqlite3",
    ):
        assert original_source not in result_text


@pytest.mark.parametrize("size,pairs", [
    (0, 2), (1, 2), (5103, 2), (True, 2), (2.5, 2),
    (22, 0), (22, 1), (22, 11), (22, False), (22, 2.5),
])
def test_sqlite_g5_graph_paired_rejects_unbounded_samples(size, pairs):
    with pytest.raises(ValueError, match="bounded SQLite native G5"):
        benchmark(registered_routes=size, pairs=pairs)
