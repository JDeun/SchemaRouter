from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmarks.operation_routing_v5b_catalog import (  # noqa: E402
    confirmation_registry,
    development_registry,
)
from benchmarks.semantic_action_ontology import (  # noqa: E402
    ACTION_PROTOTYPES,
    NON_TOOL_ACTIONS,
    compile_registry_contracts,
    parse_temporal_scope,
)


def test_action_ontology_is_fixed_generic_and_complete() -> None:
    assert set(ACTION_PROTOTYPES) == {
        "read",
        "create",
        "update",
        "delete",
        "cancel",
        "refund",
        "send",
        "share",
        "export",
        "translate",
        "summarize",
        "compare",
        "merge",
        "restart",
        "execute",
        "forecast",
        "compose",
        "explain",
        "calculate",
        "chat",
    }
    assert NON_TOOL_ACTIONS == {"compose", "explain", "calculate", "chat"}
    assert all(len(prototypes) == 6 for prototypes in ACTION_PROTOTYPES.values())


def test_action_prototypes_do_not_contain_catalog_resource_identities() -> None:
    text = "\n".join(
        prototype.casefold()
        for prototypes in ACTION_PROTOTYPES.values()
        for prototype in prototypes
    )
    forbidden_resource_roots = {
        "profile",
        "mailbox",
        "dataset",
        "payment",
        "machine",
        "workflow",
        "booking",
        "archive",
        "deployment",
        "invoice",
        "signal",
    }
    for root in forbidden_resource_roots:
        assert root not in text


def test_development_contracts_cover_all_registration_sources() -> None:
    contracts = compile_registry_contracts(development_registry())
    adapters = {contract.adapter or "native" for contract in contracts.values()}

    assert adapters == {"native", "openapi", "mcp"}
    assert len(contracts) == 18
    assert contracts["profiles_api.r17"].action == "read"
    assert contracts["profiles_api.u42"].action == "update"
    assert contracts["profiles_api.d93"].action == "delete"
    assert contracts["mailbox_ops.m33"].action == "send"
    assert contracts["mailbox_ops.m44"].action == "delete"
    assert contracts["exports.export"].action == "export"
    assert contracts["payments.refund"].action == "refund"
    assert contracts["machines.restart"].action == "restart"
    assert contracts["workflow_ops.w50"].action == "execute"


def test_confirmation_contracts_are_identity_disjoint() -> None:
    dev = set(compile_registry_contracts(development_registry()))
    confirm = set(compile_registry_contracts(confirmation_registry()))

    assert len(confirm) == 22
    assert dev.isdisjoint(confirm)


def test_data_contract_keeps_declared_types_and_units() -> None:
    contracts = compile_registry_contracts(development_registry())
    payment = contracts["payments.retrieve"]
    amount = next(
        field
        for field in payment.data_contract
        if field.get("name") == "amount"
    )

    assert amount["role"] == "output"
    assert amount["type"] == "number"
    assert amount["source_unit"] == "USD"
    assert amount["canonical_unit"] is None


def test_temporal_parser_is_explicit_and_deterministic() -> None:
    assert parse_temporal_scope("show the current value") == "current"
    assert parse_temporal_scope("과거 값을 보여줘") == "historical"
    assert parse_temporal_scope("future value please") == "future"
    assert parse_temporal_scope("show the value") is None
