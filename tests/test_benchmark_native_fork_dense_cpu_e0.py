"""E0 dense fork performance cohorts preserve strict K5 and source authority."""
from __future__ import annotations

import pytest

from scripts.benchmark_native_fork_dense_cpu_e0 import STUDY, benchmark_dense


@pytest.mark.parametrize("fanout", (33, 64))
def test_dense_same_root_benchmark_is_original_source_scoped_and_no_leak(
    fanout: int,
):
    result = benchmark_dense(
        registered_routes=500, extra_status=fanout, iterations=10,
    )
    assert result["study"] == STUDY
    assert result["evidence_tier"].startswith("E0_")
    assert result["registered_base_routes"] == 500
    assert result["registered_native_routes"] == 500 + fanout
    assert result["benchmark_only_original_source_fork_count"] == fanout + 1
    assert result["strict_public_k"] == 5
    assert result["all_aliases_en_ko_ja_match"] is True
    assert result["private_arms_never_exposed"] is True
    assert result["same_source_index_live_health_revocation"] is True
    assert result["dense_over_k"]["status"] == "over_k_unranked"
    assert result["dense_over_k"]["qualified_forks"] == fanout + 1
    assert result["revoked_to_single_fork"]["status"] == "complete"
    assert result["revoked_to_single_fork"]["qualified_forks"] == 1
    assert result["independent_e2_qualified"] is False
    assert result["model_selected_tools"] is False
    assert result["production_slo_qualified"] is False
    assert result["provider_native_http_calls"] == 0
    for condition in ("dense_over_k", "revoked_to_single_fork"):
        for metric in ("wall_ms", "process_cpu_ms"):
            assert all(
                result[condition][metric][p] >= 0
                for p in ("p50", "p95", "p99")
            )


@pytest.mark.parametrize(
    ("routes", "fanout", "iterations"),
    ((499, 33, 10), (500, 32, 10), (500, 65, 10),
     (500, 33, 9), (500, 33, 41), (True, 33, 10),
     (500, True, 10), (500, 33, True)),
)
def test_dense_benchmark_rejects_nonpreregistered_or_unbounded_inputs(
    routes, fanout, iterations,
):
    with pytest.raises(ValueError):
        benchmark_dense(
            registered_routes=routes, extra_status=fanout,
            iterations=iterations,
        )
