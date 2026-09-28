from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmarks.operation_routing_v5_catalog import (  # noqa: E402
    confirmation_registry,
    development_registry,
)
from benchmarks.query_first_typed_frame import (  # noqa: E402
    compile_registry_contracts,
    contract_contradicts,
    parse_request_frame,
)


def test_parser_extracts_multilingual_explicit_actions() -> None:
    cases = {
        "delete the record": "delete",
        "기록을 삭제해줘": "delete",
        "elimina el registro": "delete",
        "記録を削除して": "delete",
        "lösche den eintrag": "delete",
        "record를 delete해줘": "delete",
        "translate the document": "translate",
        "문서를 번역해줘": "translate",
        "restart device D-9": "restart",
        "주문 O-42를 환불해줘": "refund",
    }
    for query, expected in cases.items():
        frame = parse_request_frame(query)
        assert frame.actions == (expected,)


def test_specific_action_dominates_generic_read_wording() -> None:
    frame = parse_request_frame("show me a translated version of this document")
    assert frame.actions == ("translate",)


def test_parser_extracts_explicit_temporal_scope() -> None:
    assert parse_request_frame("show current status").temporal_scope == "current"
    assert parse_request_frame("과거 기록을 보여줘").temporal_scope == "historical"
    assert parse_request_frame("forecast future values").temporal_scope == "future"


def test_development_contracts_cover_native_openapi_and_mcp() -> None:
    contracts = compile_registry_contracts(development_registry())
    adapters = {contract.adapter or "native" for contract in contracts.values()}

    assert adapters == {"native", "openapi", "mcp"}
    assert len(contracts) == 18
    assert contracts["contacts_api.beta_23"].action == "create"
    assert contracts["contacts_api.gamma_41"].action == "update"
    assert contracts["media_ops.z8"].action == "delete"
    assert contracts["shipments.eta"].action == "forecast"
    assert contracts["shipments.status"].temporal_scope == "current"


def test_confirmation_contracts_use_disjoint_route_identities() -> None:
    dev = set(compile_registry_contracts(development_registry()))
    confirm = set(compile_registry_contracts(confirmation_registry()))
    assert dev.isdisjoint(confirm)
    assert len(confirm) == 21


def test_explicit_unsupported_action_creates_contradiction() -> None:
    contracts = compile_registry_contracts(development_registry())
    frame = parse_request_frame("delete shipment T-1")

    assert contract_contradicts(frame, contracts["shipments.status"])
    assert contract_contradicts(frame, contracts["shipments.eta"])


def test_unknown_frame_does_not_invent_contradiction() -> None:
    contracts = compile_registry_contracts(development_registry())
    frame = parse_request_frame("shipment T-1")

    assert frame.actions == ()
    assert frame.temporal_scope is None
    assert not contract_contradicts(frame, contracts["shipments.status"])


def test_temporal_contradiction_is_only_applied_when_both_sides_are_known() -> None:
    contracts = compile_registry_contracts(development_registry())
    future = parse_request_frame("show future shipment arrival")
    assert contract_contradicts(future, contracts["shipments.status"])
    assert not contract_contradicts(future, contracts["shipments.eta"])
