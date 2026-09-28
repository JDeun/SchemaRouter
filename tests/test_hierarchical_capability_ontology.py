from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmarks.hierarchical_capability_ontology import (  # noqa: E402
    LEAF_TO_ROOT,
    ONTOLOGY,
    RequestConstraints,
    compile_registry_contracts,
    contract_compatible,
)
from benchmarks.operation_routing_v5c_catalog import (  # noqa: E402
    confirmation_registry,
    development_registry,
)


def test_ontology_has_expected_hierarchy() -> None:
    assert ONTOLOGY["read"] == ("search", "retrieve", "list")
    assert ONTOLOGY["mutate"] == (
        "create",
        "update",
        "delete",
        "cancel",
        "refund",
    )
    assert ONTOLOGY["transform"] == (
        "export",
        "translate",
        "summarize",
        "compare",
        "merge",
    )
    assert LEAF_TO_ROOT["restart"] == "control"
    assert LEAF_TO_ROOT["forecast"] == "predict"
    assert LEAF_TO_ROOT["compose"] == "non_tool"


def test_ontology_source_contains_no_evaluation_route_identities() -> None:
    source = (
        ROOT / "benchmarks" / "hierarchical_capability_ontology.py"
    ).read_text()
    for forbidden in (
        "cases_api.c17",
        "catalog_ops.k11",
        "accounts_api.a17",
        "library_ops.l10",
        "weather.current",
        "materials.search",
        "profiles_api.r17",
        "shipments.status",
    ):
        assert forbidden not in source


def test_development_contracts_compile_to_hierarchy() -> None:
    contracts = compile_registry_contracts(development_registry())

    assert contracts["catalog_ops.k11"].leaf == "search"
    assert contracts["catalog_ops.k22"].leaf == "retrieve"
    assert contracts["catalog_ops.k33"].leaf == "list"
    assert contracts["cases_api.c28"].leaf == "update"
    assert contracts["cases_api.c39"].leaf == "delete"
    assert contracts["deliveries.send"].leaf == "send"
    assert contracts["deliveries.share"].leaf == "share"
    assert contracts["document_ops.merge"].leaf == "merge"
    assert contracts["workers.execute"].leaf == "execute"
    assert contracts["demand.forecast"].leaf == "forecast"
    assert contracts["membership.refund"].leaf == "refund"


def test_read_root_may_be_known_even_when_leaf_is_unknown() -> None:
    contracts = compile_registry_contracts(development_registry())
    current = contracts["demand.current"]
    assert current.root == "read"
    assert current.leaf == "retrieve"
    assert current.temporal_scope == "current"


def test_exact_leaf_contradiction_is_deterministic() -> None:
    contracts = compile_registry_contracts(development_registry())

    search = RequestConstraints(
        root="read",
        leaf="search",
        temporal_scope=None,
        root_score=-1.0,
        leaf_score=-1.0,
    )
    retrieve = RequestConstraints(
        root="read",
        leaf="retrieve",
        temporal_scope=None,
        root_score=-1.0,
        leaf_score=-1.0,
    )

    assert contract_compatible(search, contracts["catalog_ops.k11"])
    assert not contract_compatible(search, contracts["catalog_ops.k22"])
    assert contract_compatible(retrieve, contracts["catalog_ops.k22"])
    assert not contract_compatible(retrieve, contracts["catalog_ops.k11"])


def test_non_tool_root_matches_no_registered_endpoint() -> None:
    contracts = compile_registry_contracts(development_registry())
    request = RequestConstraints(
        root="non_tool",
        leaf="explain",
        temporal_scope=None,
        root_score=1.0,
        leaf_score=1.0,
    )
    assert not any(
        contract_compatible(request, contract)
        for contract in contracts.values()
    )


def test_development_and_confirmation_route_identities_are_disjoint() -> None:
    dev = set(compile_registry_contracts(development_registry()))
    confirm = set(compile_registry_contracts(confirmation_registry()))
    assert dev.isdisjoint(confirm)


def test_typed_data_contract_is_preserved() -> None:
    contracts = compile_registry_contracts(development_registry())
    demand = contracts["demand.current"]
    value = next(
        field for field in demand.data_contract
        if field.get("name") == "value"
    )
    assert value["type"] == "number"
    assert value["source_unit"] == "unit"
