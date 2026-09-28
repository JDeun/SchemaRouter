from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmarks.factorized_resource_action import (  # noqa: E402
    ACTION_PROTOTYPES,
    FactorizedResourceActionRouter,
    _tool_resource_text,
    compile_registry_contracts,
)
from benchmarks.operation_routing_v5c_catalog import (  # noqa: E402
    confirmation_registry,
    development_registry,
)


def test_resource_view_excludes_operation_authority_and_keeps_data_semantics() -> None:
    registry = development_registry()
    specimens = next(tool for tool in registry.tools() if str(tool.key) == "specimens_api")
    text = _tool_resource_text(specimens).casefold()

    assert "specimen" in text
    assert "storage" in text
    assert "number" in text
    assert "k" in text

    # Operation semantics must not be resource-ranking evidence.
    assert "retrieve" not in text
    assert "update" not in text
    assert "delete" not in text
    assert "patch" not in text


def test_typed_unit_metadata_survives_contract_compilation() -> None:
    contracts = compile_registry_contracts(development_registry())
    route = contracts["specimens_api.s17"]
    temperature = next(
        row for row in route.data_contract
        if row.get("name") == "storage_temperature"
    )

    assert temperature["type"] == "number"
    assert temperature["source_unit"] == "K"


def test_resource_and_action_axes_are_separate_static_surfaces() -> None:
    source = (ROOT / "benchmarks" / "factorized_resource_action.py").read_text()

    assert "operation_aliases_excluded" not in source
    assert "_tool_resource_text" in source
    assert "_conditioned_action_text" in source
    assert "resource_vectors" in source
    assert "conditioned_vectors" in source
    assert "tool_ranked = self._rank_tools(query_vector)" in source


def test_action_ontology_is_reused_without_route_identities() -> None:
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

    source = (ROOT / "benchmarks" / "factorized_resource_action.py").read_text()
    for forbidden in (
        "specimens_api.s17",
        "notebook_ops.n01",
        "reservations_api.r11",
        "records_ops.q01",
        "weather.current",
        "materials.search",
    ):
        assert forbidden not in source


def test_development_and_confirmation_contracts_are_disjoint() -> None:
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


def test_router_class_does_not_use_global_route_top1_as_domain_authority() -> None:
    source = (ROOT / "benchmarks" / "factorized_resource_action.py").read_text()

    assert "resource_tool, resource_score = tool_ranked[0]" in source
    assert "raw_tool =" not in source
    assert "cross_tool" not in source
    assert FactorizedResourceActionRouter.__name__ == "FactorizedResourceActionRouter"
