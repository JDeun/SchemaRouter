"""Scale experiment checks source-locked, actual public scoped API behavior."""
from __future__ import annotations

import math

import pytest

from benchmarks.current_adapter_field_scope_dev_v1 import principal
from benchmarks.current_adapter_scaled_authorized_dev_v1 import build_fixture
from schemarouter import (
    HostFieldContract,
    select_authorized_field_contract,
)
from scripts.research_host_field_contract_scaled_cpu_dev import (
    SCENARIOS,
    SIZES,
    _nearest_rank,
    assess,
)


def test_100_route_current_authorized_full_scan_runs_real_product() -> None:
    report = assess(sizes=(100,), repeats=1)
    assert report["sizes"] == [100]
    assert len(report["rows"]) == 18
    assert report["statistics"]["100"]["registered_routes"] == 100
    assert report["statistics"]["100"]["viewer_authorized_routes"] == 95
    assert report["statistics"]["100"][
        "no_invalid_route_or_wrong_or_unauthorized_selected"
    ]
    assert report["scope"]["may_promote_default_or_release"] is False
    assert report["scope"]["no_actual_tool_executed"] is True
    assert {r["language"] for r in report["rows"]} == {"en", "ko", "ja"}
    assert {r["scenario"] for r in report["rows"]} == {
        item["id"] for item in SCENARIOS
    }
    for row in report["rows"]:
        assert math.isfinite(row["host_contract_end_to_end_ms"])
        assert row["no_tools_invoked"]
        assert row["receipt"]["candidate_count"] == 95


@pytest.mark.parametrize("size", SIZES)
def test_shortlisted_search_can_never_prove_complete_unique_contract(
    size: int,
) -> None:
    router, _ = build_fixture(size)
    selection = select_authorized_field_contract(
        router, "read invoice", principal=principal("viewer"),
        contract=HostFieldContract(
            operation="read",
            required_output_fields=["invoice_id", "total_amount"],
        ),
        k=5,
    )
    assert selection.disposition == "abstained"
    assert selection.reason == "incomplete_authorized_catalog"
    assert selection.selected_route_id is None


def test_nearest_rank_statistic_does_not_invent_percentile_precision() -> None:
    assert _nearest_rank([4.0, 1.0, 3.0, 2.0], 0.95) == 4
    with pytest.raises(ValueError):
        _nearest_rank([], 0.95)


@pytest.mark.parametrize("sizes,repeats", [
    ((), 1), ((100, 100), 1), ((200,), 1),
    ((100,), 0), ((100,), True), ((100,), 9),
])
def test_no_unregistered_catalog_or_unbounded_run(sizes, repeats) -> None:
    with pytest.raises(ValueError):
        assess(sizes=sizes, repeats=repeats)
