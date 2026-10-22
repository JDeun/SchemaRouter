"""E0 paired, balanced native G5 CPU proof-of-measurement, not an SLA."""
from __future__ import annotations

import pytest

from scripts.research_native_fork_interleaved_abba_e0 import (
    STUDY,
    run_interleaved_abba,
)


@pytest.mark.parametrize("extra", (33, 64))
def test_abba_modes_preserve_original_source_k5_and_live_health(extra: int):
    report = run_interleaved_abba(
        registered_routes=500, extra_status=extra, rounds=4,
    )
    assert report["study"] == STUDY
    assert report["native_registered_routes"] == 500 + extra
    assert report["strict_public_k"] == 5
    assert report["same_graph_same_principal_same_policy"] is True
    assert report["source_authorization_still_checked_each_query"] is True
    assert report["en_ko_ja_exact_alias_parity"] is True
    assert report["public_over_k_reveals_no_candidates"] is True
    assert report["dense"]["expected_qualified_forks"] == extra + 1
    assert report["revoked_same_index"]["expected_qualified_forks"] == 1
    assert report["no_source_http_or_agent_execution"] is True
    assert report["independent_publisher_gold"] is False
    assert report["independent_agent_e2"] is False
    assert report["production_slo_qualified"] is False
    for condition in ("dense", "revoked_same_index"):
        assert report[condition]["samples_per_mode"] == 8
        assert report[condition]["order"] == "ALTERNATING_ABBA_BAAB"
        for mode in ("baseline", "indexed_preshard"):
            for metric in ("wall_ms", "cpu_ms"):
                assert all(
                    report[condition][mode][metric][key] >= 0
                    for key in ("p50", "p95", "p99", "mean")
                )


@pytest.mark.parametrize(("catalog", "extra", "rounds"), (
    (499, 33, 4),
    (5001, 33, 4),
    (500, 32, 4),
    (500, 65, 4),
    (500, 33, 3),
    (500, 33, 21),
    (True, 33, 4),
    (500, True, 4),
    (500, 33, True),
))
def test_abba_rejects_nonpreregistered_or_unbounded_inputs(
    catalog, extra, rounds,
):
    with pytest.raises(ValueError):
        run_interleaved_abba(
            registered_routes=catalog, extra_status=extra, rounds=rounds,
        )
