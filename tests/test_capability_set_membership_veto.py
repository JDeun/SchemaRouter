from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmarks.capability_set_membership_veto import (  # noqa: E402
    LEAF_PROTOTYPES,
    CapabilitySetMembershipVetoRouter,
    compile_registry_contracts,
    decide_veto,
    membership_state,
)
from benchmarks.operation_routing_v5e_catalog import (  # noqa: E402
    confirmation_registry,
    development_registry,
)


def test_membership_state_is_set_based() -> None:
    supported = {"retrieve", "update"}

    assert membership_state("retrieve", supported) == "supported"
    assert membership_state("delete", supported) == "outside_set"
    assert membership_state(None, supported) == "unknown"


def test_explicit_outside_plus_any_semantic_outside_vetoes() -> None:
    vetoed, rule, votes = decide_veto(
        explicit="delete",
        bge_leaf="cancel",
        aux_leaf="retrieve",
        supported_leaves={"retrieve", "update"},
        tool_has_unknown=False,
    )

    assert vetoed
    assert rule == "explicit_plus_membership_agreement"
    assert votes == {
        "explicit": "outside_set",
        "bge": "outside_set",
        "aux": "supported",
    }


def test_semantic_votes_need_not_name_same_leaf() -> None:
    vetoed, rule, votes = decide_veto(
        explicit=None,
        bge_leaf="delete",
        aux_leaf="cancel",
        supported_leaves={"retrieve", "update"},
        tool_has_unknown=False,
    )

    assert vetoed
    assert rule == "dual_semantic_outside_set"
    assert votes["bge"] == "outside_set"
    assert votes["aux"] == "outside_set"


def test_explicit_supported_always_preserves() -> None:
    vetoed, rule, votes = decide_veto(
        explicit="retrieve",
        bge_leaf="delete",
        aux_leaf="cancel",
        supported_leaves={"retrieve", "update"},
        tool_has_unknown=False,
    )

    assert not vetoed
    assert rule is None
    assert votes["explicit"] == "supported"


def test_unknown_endpoint_contract_disables_absence_claim() -> None:
    vetoed, rule, _ = decide_veto(
        explicit="delete",
        bge_leaf="delete",
        aux_leaf="delete",
        supported_leaves={"retrieve"},
        tool_has_unknown=True,
    )

    assert not vetoed
    assert rule is None


def test_registry_compiler_preserves_typed_unit_metadata() -> None:
    contracts = compile_registry_contracts(development_registry())
    current = contracts["thermal_flux.current"]
    value = next(
        field
        for field in current.data_contract
        if field.get("name") == "value"
    )

    assert value["type"] == "number"
    assert value["source_unit"] == "W/m2"


def test_development_and_confirmation_routes_are_disjoint() -> None:
    dev = set(compile_registry_contracts(development_registry()))
    confirm = set(compile_registry_contracts(confirmation_registry()))
    assert dev.isdisjoint(confirm)


def test_model_source_contains_no_v5e_route_identities() -> None:
    source = (
        ROOT / "benchmarks" / "capability_set_membership_veto.py"
    ).read_text()

    for forbidden in (
        "quarry_permits_api.qp17",
        "ledger_index_ops.li11",
        "harbor_clearance_api.hc17",
        "memo_index_ops.mi10",
    ):
        assert forbidden not in source


def test_generic_ontology_shape_is_unchanged_from_preregistered_source() -> None:
    assert set(LEAF_PROTOTYPES) == {
        "search",
        "retrieve",
        "list",
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
    assert all(len(values) == 6 for values in LEAF_PROTOTYPES.values())


def test_router_type_exists_for_frozen_harness() -> None:
    assert CapabilitySetMembershipVetoRouter.__name__ == (
        "CapabilitySetMembershipVetoRouter"
    )
