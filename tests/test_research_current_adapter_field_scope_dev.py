"""Protocol parser, field-gold and principal visibility DEV regression tests."""
from __future__ import annotations

import pytest

from benchmarks.current_adapter_field_scope_dev_v1 import (
    LANGUAGES,
    SOURCE_CLASS,
    authored_tasks,
    principal,
    registry_and_policy,
    router_and_policy,
)
from scripts.research_current_adapter_field_scope_dev import (
    TRUTH,
    evaluate,
    validate_gold,
)


def test_new_manual_local_fixture_is_not_recycled_v5_gold() -> None:
    tasks = authored_tasks()
    assert len(tasks) == 27
    assert {r["language"] for r in tasks} == set(LANGUAGES)
    assert len({r["query"] for r in tasks}) == len(tasks)
    assert len({r["id"] for r in tasks}) == len(tasks)
    assert all(not r["id"].startswith("v5-") for r in tasks)
    assert SOURCE_CLASS == "newly_authored_local_protocol_shaped_development_only"


def test_parsed_openapi_and_mcp_typed_fields_agree_with_reviewed_gold() -> None:
    registry, policy = registry_and_policy()
    existing = {
        f"{tool.key}.{endpoint.name}": (tool, endpoint)
        for tool in registry.tools() for endpoint in tool.endpoints
    }
    assert len(existing) == 10
    for row in authored_tasks():
        validate_gold(row, existing, policy)
    assert {"billing.getInvoice", "billing.payInvoice"} <= set(existing)
    assert {"research.search_documents", "research.tag_document"} <= set(existing)
    assert {"orders.lookup", "orders.setStatus"} <= set(existing)


def test_host_principal_eligibility_is_checked_by_real_router_api() -> None:
    router, _ = router_and_policy()
    viewer = router.retrieve_authorized(
        "Pay my invoice", principal=principal("viewer"), k=10,
    )
    editor = router.retrieve_authorized(
        "Pay my invoice", principal=principal("editor"), k=10,
    )
    assert "billing.payInvoice" not in {
        row.route_id for row in viewer.candidates
    }
    assert "billing.payInvoice" in {
        row.route_id for row in editor.candidates
    }
    assert not any(row.endpoint == "link" for row in viewer.candidates)


@pytest.mark.parametrize("bad_role", ["", "administrator", "viewer,editor"])
def test_no_unreviewed_implicit_principal_authority(bad_role: str) -> None:
    with pytest.raises(ValueError):
        principal(bad_role)


def test_tampered_required_field_gold_fails_closed() -> None:
    registry, policy = registry_and_policy()
    existing = {
        f"{tool.key}.{endpoint.name}": (tool, endpoint)
        for tool in registry.tools() for endpoint in tool.endpoints
    }
    row = next(task for task in authored_tasks() if task["scenario"] == "invoice_read")
    row["gold_fields"] = ["total_amount", "secret_credit_card"]
    with pytest.raises(ValueError):
        validate_gold(row, existing, policy)


def test_current_authorized_retrieval_with_field_level_dev_is_observational() -> None:
    report = evaluate(k=5)
    assert report["id"] == "hand_authorized_multisource_typed_field_dev_v1"
    assert len(report["raw_dev_cases"]) == 27
    assert report["protocol_adapters"] == ["openapi", "mcp"]
    assert set(report["native_schema_sources"]) == {"database", "vector", "graph"}
    assert report["global"]["unauthorized_retrievals"] == 0
    assert report["scope"]["executed_tools"] == 0
    assert report["scope"]["agent_task_success_measured"] is False
    assert report["scope"]["source_is_live_real_providers"] is False
    assert report["scope"]["independent_confirmation"] is False
    assert report["scope"]["may_release"] is False
    assert set(report["languages"]) == set(LANGUAGES)
    assert report["global"]["required_field_recall"] is not None


@pytest.mark.parametrize("bad", [0, 4, 256, True])
def test_scoring_exposure_is_preregistered_only(bad: int) -> None:
    with pytest.raises(ValueError):
        evaluate(k=bad)


def test_no_runtime_secret_or_hidden_gold_input_in_research_scope() -> None:
    assert TRUTH["principal_visibility_via_current_router"] is True
    assert TRUTH["auth_principal_authenticated_by_host"] is False
    assert TRUTH["field_gold_independently_audited"] is False
    assert TRUTH["may_promote_to_product"] is False
