"""Real SQLite WAL paired graph index update E0: full typed oracle."""
from __future__ import annotations

import json

import pytest

from scripts.benchmark_sqlite_native_g5_graph_journal_ab_e0 import (
    EVIDENCE,
    benchmark,
)


def test_sqlite_g5_graph_journal_paired_oracle_and_negative_contract():
    result = benchmark(registered_routes=22, pairs=4)
    assert result["evidence_tier"] == EVIDENCE
    assert result["provider_independent_e2_qualified"] is False
    assert result["production_sla_qualified"] is False
    assert result["registered_native_routes"] == 22
    assert result["pairs"] == result["full_oracle_equal_pairs"] == 4
    assert result["supported_typed_pairs"] == 2
    assert result["incompatible_typed_pairs"] == 2
    assert 0 <= result["journal_faster_pairs"] <= 4
    assert result["peak_process_rss_kib"] > 0
    for key in ("full", "journal"):
        for category in ("wall_ms", "process_cpu_ms"):
            lat = result[category][key]
            assert 0 <= lat["p50"] <= lat["p95"] <= lat["p99"]
    report = json.dumps(result)
    for forbidden in ("customer_id", "case_service", "contact_directory"):
        assert forbidden not in report


@pytest.mark.parametrize("size,n", [
    (0, 2), (1, 2), (5103, 2), (True, 2), (2.5, 2),
    (22, 0), (22, 1), (22, 11), (22, False), (22, 2.5),
])
def test_sqlite_g5_graph_journal_rejects_invalid_bench_inputs(size, n):
    with pytest.raises(ValueError, match="bounded synthetic SQLite G5"):
        benchmark(registered_routes=size, pairs=n)
