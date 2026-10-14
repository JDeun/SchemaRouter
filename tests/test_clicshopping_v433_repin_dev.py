"""Regression gates for maintainer-repinned DEV-only ClicShopping comparison."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from scripts.run_clicshopping_v433_dev import PACKAGE, load_json
from scripts.run_clicshopping_v433_repin_dev import (
    eligible_catalog,
    pin_new_inventory,
    run,
    validate_repin_cases,
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


@pytest.mark.parametrize(
    "change",
    [
        lambda d: d.update(independent_cases=True),
        lambda d: d.update(top_k=100),
        lambda d: d.update(live_requests=1),
        lambda d: d["cases"][0].update(id="clic433-001"),
        lambda d: d["cases"][0].update(
            required_routes=["customerOrders.erase_all"]
        ),
        lambda d: d["counts"].update(total=9),
    ],
)
def test_unapproved_protocol_or_case_changes_fail_closed(change) -> None:
    old, transition, prior, fresh = inputs()
    modified = deepcopy(fresh)
    change(modified)
    with pytest.raises(ValueError):
        validate_repin_cases(
            modified, prior, pin_new_inventory(old, transition)
        )



def test_separate_customer_order_write_permissions_are_not_merged() -> None:
    old, transition, _, _ = inputs()
    new = pin_new_inventory(old, transition)
    grants = {
        "select_data": True,
        "create_data": False,
        "update_data": False,
        "delete_data": False,
        "create_db": False,
    }
    def exposed() -> set[str]:
        return {x["route"] for x in eligible_catalog(new, grants)}

    assert "customerOrders.cancel_order" not in exposed()
    assert "customerOrders.send_message" not in exposed()

    grants["create_data"] = True
    assert "customerOrders.send_message" in exposed()
    assert "customerOrders.cancel_order" not in exposed()

    grants["create_data"] = False
    grants["update_data"] = True
    assert "customerOrders.cancel_order" in exposed()
    assert "customerOrders.send_message" not in exposed()

    grants["create_data"] = True
    assert {
        "customerOrders.cancel_order", "customerOrders.send_message"
    } <= exposed()

    grants["select_data"] = False
    assert not exposed()



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
    # Verify actual observed candidates, never manufacture an apparent hit.
    first = next(x for x in cohorts[1]["per_case"] if x["id"] == "clic433r-001")
    assert first["eligible_full_routes"] > 0
    assert isinstance(first["selected_routes"], list)
    assert first["required_present"] == (
        "customerOrders.list_orders" in first["selected_routes"]
    )



@pytest.mark.parametrize(("field", "value"), [
    ("top_k", True),
    ("top_k", "3"),
    ("top_k", 0),
    ("hot_repeats", True),
    ("hot_repeats", "5"),
    ("hot_repeats", 0),
    ("model_calls", False),
    ("live_requests", False),
])
def test_repin_dev_never_accepts_bool_or_text_as_numeric_protocol(
    field: str, value: object,
) -> None:
    old, transition, prior, fresh = inputs()
    wrong = deepcopy(fresh)
    wrong[field] = value
    with pytest.raises(ValueError, match="measurement protocol changed"):
        validate_repin_cases(
            wrong, prior, pin_new_inventory(old, transition),
        )


@pytest.mark.parametrize(("field", "value"), [
    ("page_path", "../../secret.php"),
    ("page_sha", "0" * 40),
    ("router_path", "../fake-clicshopping.json"),
    ("router_sha", "0" * 40),
    ("router_target", r"Sites\Shop\Pages\OtherPage"),
])
def test_dev_repin_source_cannot_swap_in_an_unaudited_page_or_route(
    field: str, value: str,
) -> None:
    old, transition, _, _ = inputs()
    wrong = deepcopy(transition)
    if field == "page_path":
        wrong["new_customer_orders_page"]["path"] = value
    elif field == "page_sha":
        wrong["new_customer_orders_page"]["git_blob_sha"] = value
    elif field == "router_path":
        wrong["route_after"]["path"] = value
    elif field == "router_sha":
        wrong["route_after"]["git_blob_sha"] = value
    else:
        wrong["route_after"]["customer_orders"] = value
    with pytest.raises(ValueError, match="source identity|router identity"):
        pin_new_inventory(old, wrong)


@pytest.mark.parametrize(("field", "value"), [
    ("credential_use", True),
    ("php_execution", True),
    ("official_model_scored", True),
    ("live_endpoint_calls", False),
    ("model_calls", False),
])
def test_unapproved_live_or_type_confused_repin_claim_fails_closed(
    field: str, value: object,
) -> None:
    old, transition, _, _ = inputs()
    wrong = deepcopy(transition)
    wrong["source_verification"][field] = value
    with pytest.raises(ValueError, match="unapproved evidence level"):
        pin_new_inventory(old, wrong)


@pytest.mark.parametrize(("label_kind", "value"), [
    ("required_routes", ["customerOrders.list_orders"] * 2),
    ("required_routes", "customerOrders.list_orders"),
    ("forbidden_routes", ["customerOrders.cancel_order"] * 2),
    (
        "ambiguous_routes",
        ["customerOrders.history", "customerOrders.history"],
    ),
    ("ambiguous_routes", ["customerOrders.history", 99]),
])
def test_duplicate_or_malformed_repin_gold_route_labels_are_rejected(
    label_kind: str, value: object,
) -> None:
    old, transition, prior, fresh = inputs()
    wrong = deepcopy(fresh)
    if label_kind == "required_routes":
        index = 0
    elif label_kind == "forbidden_routes":
        index = 5
    else:
        index = 8
    wrong["cases"][index][label_kind] = value
    with pytest.raises(ValueError, match="invalid or duplicated"):
        validate_repin_cases(wrong, prior, pin_new_inventory(old, transition))


def test_repin_case_counts_cannot_be_boolean_or_forged():
    old, transition, prior, fresh = inputs()
    wrong = deepcopy(fresh)
    wrong["counts"]["unsupported"] = True
    with pytest.raises(ValueError, match="case counts drift"):
        validate_repin_cases(wrong, prior, pin_new_inventory(old, transition))


def test_repin_source_role_flags_are_checked_before_case_scoring():
    old, transition, prior, fresh = inputs()
    wrong = deepcopy(prior)
    wrong["roles"]["reader"]["select_data"] = "true"
    with pytest.raises(ValueError, match="malformed frozen role"):
        validate_repin_cases(fresh, wrong, pin_new_inventory(old, transition))


def test_original_42_visible_dev_cases_remain_unscored_heldout():
    results = run()
    assert results["independent_confirmation"] is False
    assert results["field_recall"] is None
    assert results["model_calls"] == 0
    assert results["live_requests"] == 0
    assert [cohort["case_count"] for cohort in results["cohorts"]] == [32, 10]


def test_offline_workflow_uses_only_exact_source_object_mirror() -> None:
    """Fail if the repin workflow silently advances to a different source."""
    workflow = (
        Path(__file__).resolve().parents[1]
        / ".github/workflows/external-validation-clicshopping-v433-repin-dev.yml"
    ).read_text(encoding="utf-8")
    assert "repository: retail-ecommerce/ClicShopping" in workflow
    assert "ref: 8ada7f1f392f3dd2800e825dac8d245dfd53944a" in workflow
    assert '"source_checkout_repository": "retail-ecommerce/ClicShopping"' in workflow
    assert '"upstream_pin": report["source_pin"]' in workflow
    assert "python -m scripts.verify_clicshopping_v433_repin" in workflow
    assert "persist-credentials: false" in workflow
