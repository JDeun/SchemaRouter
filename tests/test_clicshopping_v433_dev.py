"""Offline ClicShopping development protocol invariants (not held-out evidence)."""

from __future__ import annotations

from copy import deepcopy

import pytest

from scripts.run_clicshopping_v433_dev import (
    PACKAGE,
    eligible_catalog,
    load_json,
    run,
    validate_cases,
)


def sources() -> tuple[dict, dict]:
    return (
        load_json(PACKAGE / "source-inventory.json"),
        load_json(PACKAGE / "dev-cases.json"),
    )


def test_cases_frozen_against_permissioned_source() -> None:
    inventory, cases = sources()
    validate_cases(cases, inventory)


def test_role_scope_excludes_unverified_and_unauthorized_routes() -> None:
    inventory, cases = sources()
    catalogs = {
        role: {r["route"] for r in eligible_catalog(inventory, flags)}
        for role, flags in cases["roles"].items()
    }
    assert catalogs["no_read"] == set()
    assert "AnthropicEcommerce.order_cancel" not in catalogs["reader"]
    assert "AnthropicEcommerce.order_cancel" in catalogs["manager"]
    assert "ChatRagBI.analyze_sales" in catalogs["reader"]
    assert "ChatRagBI.analyze_sales" not in catalogs["manager"]
    assert "CustomersProducts.products" in catalogs["reader"]
    assert "AnthropicEcommerce.products" in catalogs["reader"]
    assert all(
        not route.startswith("customerOrders.")
        for entries in catalogs.values()
        for route in entries
    )


@pytest.mark.parametrize(
    "tamper",
    [
        lambda f: f["cases"][0].update(
            required_routes=["customerOrders.list_orders"]
        ),
        lambda f: f["cases"][0].update(
            required_routes=["AnthropicEcommerce.order_cancel"]
        ),
        lambda f: f["protocol"].update(field_recall="100%"),
        lambda f: f["protocol"].update(network_calls=True),
        lambda f: f["counts"].update(total=999),
        lambda f: f["cases"][0].update(id=f["cases"][1]["id"]),
    ],
)
def test_no_invalid_case_or_unverified_source_can_be_scored(tamper) -> None:
    inventory, cases = sources()
    broken = deepcopy(cases)
    tamper(broken)
    with pytest.raises(ValueError):
        validate_cases(broken, inventory)


def test_live_free_development_runner_preserves_evidence_boundary() -> None:
    report = run()
    _, cases = sources()
    assert report["status"] == "development_fixture_only_not_independent_confirmation"
    assert report["upstream_commit"] == cases["pinned_upstream_commit"]
    assert report["model_calls"] == report["live_requests"] == 0
    assert report["counts"] == cases["counts"]
    assert report["field_recall"] is None
    assert report["measured_native_wire_bytes"] is None
    assert len(report["per_case"]) == cases["counts"]["total"]
    assert all(
        not route.startswith("customerOrders.")
        for row in report["per_case"]
        for route in row["selected_routes"]
    )
    assert report["summary"]["forbidden_exposures"] == 0
