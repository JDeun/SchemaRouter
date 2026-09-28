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
    RequestFrame,
    compile_registry_contracts,
    contract_compatible,
)


def test_action_ontology_is_fixed_and_registry_independent() -> None:
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

    source = (ROOT / "benchmarks" / "semantic_action_ontology.py").read_text()
    for forbidden in (
        "profiles_api.r17",
        "mailbox_ops.m11",
        "bookings_api.b17",
        "archive_ops.a01",
        "weather.current",
        "materials.search",
    ):
        assert forbidden not in source


def test_development_contracts_infer_generic_actions() -> None:
    contracts = compile_registry_contracts(development_registry())

    assert contracts["profiles_api.r17"].action == "read"
    assert contracts["profiles_api.u42"].action == "update"
    assert contracts["profiles_api.d93"].action == "delete"
    assert contracts["mailbox_ops.m11"].action == "read"
    assert contracts["mailbox_ops.m22"].action == "read"
    assert contracts["mailbox_ops.m33"].action == "send"
    assert contracts["mailbox_ops.m44"].action == "delete"
    assert contracts["exports.export"].action == "export"
    assert contracts["payments.refund"].action == "refund"
    assert contracts["machines.restart"].action == "restart"
    assert contracts["workflow_ops.w40"].action == "cancel"
    assert contracts["workflow_ops.w50"].action == "execute"


def test_confirmation_contracts_are_disjoint_and_cover_all_adapters() -> None:
    dev = compile_registry_contracts(development_registry())
    confirm = compile_registry_contracts(confirmation_registry())

    assert set(dev).isdisjoint(confirm)
    assert {contract.adapter or "native" for contract in dev.values()} == {
        "native",
        "openapi",
        "mcp",
    }
    assert {contract.adapter or "native" for contract in confirm.values()} == {
        "native",
        "openapi",
        "mcp",
    }


def test_non_tool_actions_never_match_registered_capabilities() -> None:
    contracts = compile_registry_contracts(development_registry())
    for action in NON_TOOL_ACTIONS:
        frame = RequestFrame(
            action=action,
            temporal_scope=None,
            action_score=1.0,
        )
        assert not any(
            contract_compatible(frame, contract)
            for contract in contracts.values()
        )


def test_action_contract_matching_is_structural_not_probabilistic() -> None:
    contracts = compile_registry_contracts(development_registry())

    delete_frame = RequestFrame(
        action="delete",
        temporal_scope=None,
        action_score=-1.0,
    )
    read_frame = RequestFrame(
        action="read",
        temporal_scope=None,
        action_score=-1.0,
    )

    assert contract_compatible(delete_frame, contracts["profiles_api.d93"])
    assert not contract_compatible(delete_frame, contracts["profiles_api.r17"])
    assert contract_compatible(read_frame, contracts["profiles_api.r17"])
    assert not contract_compatible(read_frame, contracts["profiles_api.d93"])


def test_unit_and_datatype_metadata_remain_in_compiled_contract() -> None:
    contracts = compile_registry_contracts(development_registry())
    payment = contracts["payments.retrieve"]
    amount = next(
        field for field in payment.data_contract
        if field.get("name") == "amount"
    )

    assert amount["role"] == "output"
    assert amount["type"] == "number"
    assert amount["source_unit"] == "USD"
