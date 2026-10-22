"""Instrumented native fork work must retain source-bound K5 behavior."""
from __future__ import annotations

import pytest

from scripts.research_native_fork_validation_work_e0 import STUDY, profile


@pytest.mark.parametrize("extra", (33, 64))
def test_original_source_fork_validation_work_and_strict_k(extra: int):
    result = profile(registered_routes=500, extra_status=extra)
    assert result["study"] == STUDY
    assert result["registered_native_routes"] == 500 + extra
    assert result["dense"]["status"] == "over_k_unranked"
    assert result["dense"]["qualified_forks"] == extra + 1
    assert result["extras_unavailable"]["status"] == "complete"
    assert result["extras_unavailable"]["qualified_forks"] == 1
    assert result["strict_public_k"] == 5
    for condition in ("dense", "extras_unavailable"):
        observed = result[condition]["aggregate_validation_events"]
        assert observed["private_arm_query_invocations"] >= 4
        assert observed["graph_required_input_inspections"] > 0
        assert observed["pair_required_input_inspections"] > 0
    assert result["same_index_live_health_revalidated"] is True
    assert result["en_ko_ja_host_alias_parity"] is True
    assert result["source_registry_oracle_not_in_query"] is True
    assert result["product_changed"] is False
    assert result["provider_http_calls"] == 0
    assert result["production_latency_qualified"] is False
    assert result["independent_agent_e2"] is False


@pytest.mark.parametrize(("catalog", "extra"), [
    (499, 33), (5001, 64), (500, 32), (500, 65),
    (True, 33), (500, True),
])
def test_profile_rejects_unapproved_synthetic_budgets(catalog, extra):
    with pytest.raises(ValueError):
        profile(registered_routes=catalog, extra_status=extra)
