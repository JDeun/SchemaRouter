"""Regression gates for maintainer-repinned DEV-only ClicShopping comparison."""
from __future__ import annotations

from copy import deepcopy

import pytest

from scripts.run_clicshopping_v433_dev import PACKAGE, load_json
from scripts.run_clicshopping_v433_repin_dev import (
    pin_new_inventory, run, validate_repin_cases,
)


def inputs() -> tuple[dict, dict, dict, dict]:
    return (
        load_json(PACKAGE / "source-inventory.json"),
        load_json(PACKAGE / "maintainer-repin-8ada7f1.json"),
        load_json(PACKAGE / "dev-cases.json"),
        load_json(PACKAGE / "visible-dev-repin-cases-8ada7f1.json"),
    )


def test_source_repin_adds_only_new_customer_orders_page() -> None:
    old, transition, _, _ = inputs()
    new = pin_new_inventory(old, transition)
    assert old["upstream"]["commit"].startswith("3bac851")
    assert new["upstream"]["commit"].startswith("8ada7f1")
    assert old["endpoints"]["customerOrders"]["page_source"]["present"] is False
    assert new["endpoints"]["customerOrders"]["page_source"]["present"] is True
    assert set(new["endpoints"]["customerOrders"]["dispatch_actions"]) == {
        "list_orders", "read_order", "history", "cancel_order", "send_message"
    }
    for name in ("AnthropicEcommerce", "CustomersProducts", "ChatRagBI"):
        assert new["endpoints"][name] == old["endpoints"][name]


def test_all_new_queries_are_valid_visible_development_not_heldout() -> None:
    old, transition, prior, fresh = inputs()
    validate_repin_cases(fresh, prior, pin_new_inventory(old, transition))
    assert fresh["counts"] == {
        "total": 10, "supported": 5, "forbidden": 3,
        "unsupported": 1, "ambiguous": 1,
    }


@pytest.mark.parametrize("change", [
    lambda d: d.update(independent_cases=True),
    lambda d: d.update(top_k=100),
    lambda d: d.update(live_requests=1),
    lambda d: d["cases"][0].update(id="clic433-001"),
    lambda d: d["cases"][0].update(required_routes=["customerOrders.erase_all"]),
    lambda d: d["counts"].update(total=9),
])
def test_unapproved_protocol_or_case_changes_fail_closed(change) -> None:
    old, transition, prior, fresh = inputs()
    modified = deepcopy(fresh)
    change(modified)
    with pytest.raises(ValueError):
        validate_repin_cases(
            modified, prior, pin_new_inventory(old, transition)
        )


def test_real_offline_dev_comparison_runs_without_native_execution() -> None:
    result = run()
    assert result["status"] == "development_only_not_independent_heldout"
    assert result["live_requests"] == result["model_calls"] == 0
    assert result["independent_confirmation"] is False
    assert result["native_rest_execution"] is False
    assert result["customer_id_runtime_scope_verified"] is False
    old, _, _, _ = inputs()
    assert old["endpoints"]["customerOrders"]["page_source"]["present"] is False
    cohorts = result["cohorts"]
    assert [c["case_count"] for c in cohorts] == [32, 10]
    for cohort in cohorts:
        assert cohort["summary"]["forbidden_exposures"] == 0
        assert all(
            len(x["selected_routes"]) <= result["top_k"]
            for x in cohort["per_case"]
        )
    assert "customerOrders.list_orders" in {
        route
        for row in cohorts[1]["per_case"]
        if row["label"] == "supported"
        for route in (
            ["customerOrders.list_orders"]
            if row["id"] == "clic433r-001" else []
        )
    }
