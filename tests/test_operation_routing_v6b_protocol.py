from __future__ import annotations

import json
from pathlib import Path

from benchmarks.operation_routing_v6a_catalog import (
    CONFIRM_ROUTE_SPECS as V6A_CONFIRM_ROUTE_SPECS,
)
from benchmarks.operation_routing_v6a_catalog import (
    DEV_ROUTE_SPECS as V6A_DEV_ROUTE_SPECS,
)
from benchmarks.operation_routing_v6b_catalog import (
    CONFIRM_ROUTE_SPECS,
    DEV_ROUTE_SPECS,
    confirmation_registry,
    development_registry,
)
from benchmarks.schema_adb_baseline import ACTION_PHRASES, compile_registry_contracts
from benchmarks.schema_hard_negative_ellipsoid import hard_negative_texts
from scripts.generate_operation_routing_v6a import build as build_v6a
from scripts.generate_operation_routing_v6b import build

ROOT = Path(__file__).resolve().parents[1]


def test_v6b_preregistration_is_frozen_before_scoring() -> None:
    path = (\n        ROOT\n        / "benchmarks"\n        / "operation-routing-v6b-hard-negative-ellipsoid-preregistration.json"\n    )
    data = json.loads(path.read_text(encoding="utf-8"))

    assert data["issue"] == 395
    assert data["status"] == "preregistered_before_v6b_corpus_generation_or_scoring"
    assert data["boundary"]["rank"] == "min(8, n_positive - 1)"
    assert data["boundary"]["membership"] == "distance <= 1.0"
    assert data["optimization"]["learning_rate"] == 0.01
    assert data["optimization"]["steps"] == 400
    assert data["optimization"]["negative_loss"] == "mean(relu(1.10 - d_neg))"
    assert data["optimization"]["dev_selected_hyperparameters"] is False
    assert data["authority"]["positive_rerank"] is False
    assert data["authority"]["endpoint_switch"] is False
    assert data["authority"]["rank2_fallback"] is False
    assert data["authority"]["pseudo_route"] is False


def test_v6b_dev_and_confirmation_counts_and_identity_disjointness() -> None:
    dev, dev_manifest = build("development")
    confirm, confirm_manifest = build("confirmation")

    assert dev_manifest["case_count"] == 552
    assert dev_manifest["supported_cases"] == 228
    assert dev_manifest["near_domain_cases"] == 252
    assert dev_manifest["out_of_domain_cases"] == 72

    assert confirm_manifest["case_count"] == 552
    assert confirm_manifest["supported_cases"] == 228
    assert confirm_manifest["near_domain_cases"] == 252
    assert confirm_manifest["out_of_domain_cases"] == 72

    assert {row["id"] for row in dev}.isdisjoint({row["id"] for row in confirm})
    assert {row["query"] for row in dev}.isdisjoint({row["query"] for row in confirm})
    assert {
        row["expected"] for row in dev if row["expected"] is not None
    }.isdisjoint(
        {
            row["expected"]
            for row in confirm
            if row["expected"] is not None
        }
    )


def test_v6b_route_and_query_identity_is_disjoint_from_v6a() -> None:
    v6b_routes = {
        spec.route_id
        for spec in (*DEV_ROUTE_SPECS, *CONFIRM_ROUTE_SPECS)
    }
    v6a_routes = {
        spec.route_id
        for spec in (*V6A_DEV_ROUTE_SPECS, *V6A_CONFIRM_ROUTE_SPECS)
    }
    assert v6b_routes.isdisjoint(v6a_routes)

    v6b_dev, _ = build("development")
    v6b_confirm, _ = build("confirmation")
    v6a_dev, _ = build_v6a("development")
    v6a_confirm, _ = build_v6a("confirmation")

    v6b_queries = {
        row["query"]
        for row in (*v6b_dev, *v6b_confirm)
    }
    v6a_queries = {
        row["query"]
        for row in (*v6a_dev, *v6a_confirm)
    }
    assert v6b_queries.isdisjoint(v6a_queries)


def test_v6b_hard_negatives_are_tool_level_complements() -> None:
    for registry in (development_registry(), confirmation_registry()):
        contracts = compile_registry_contracts(registry)
        by_tool: dict[str, list[object]] = {}
        for contract in contracts.values():
            by_tool.setdefault(contract.tool_key, []).append(contract)

        for contracts_for_tool in by_tool.values():
            supported = {
                str(contract.leaf)
                for contract in contracts_for_tool
            }
            expected_count = (len(ACTION_PHRASES) - len(supported)) * 6
            for contract in contracts_for_tool:
                rows = hard_negative_texts(
                    resource_anchor=contract.resource_anchor,
                    supported_leaves=supported,
                )
                assert len(rows) == expected_count
                for leaf in supported:
                    assert all(
                        f"{ACTION_PHRASES[leaf][language]}: {contract.resource_anchor}"
                        not in rows
                        for language in ACTION_PHRASES[leaf]
                    )


def test_v6b_typed_unit_metadata_survives_compilation() -> None:
    dev = compile_registry_contracts(development_registry())
    viscosity = next(
        row
        for row in dev["viscosity.current"].data_contract
        if row.get("name") == "dynamic_viscosity"
    )
    assert viscosity["type"] == "number"
    assert viscosity["semantic_id"] == "material.dynamic_viscosity"
    assert viscosity["source_unit"] == "mPa·s"
    assert viscosity["canonical_unit"] == "Pa·s"
    assert viscosity["dimension"] == "dynamic_viscosity"
    assert viscosity["scale"] == 0.001
    assert viscosity["offset"] == 0.0

    confirm = compile_registry_contracts(confirmation_registry())
    density = next(
        row
        for row in confirm["density.current"].data_contract
        if row.get("name") == "mass_density"
    )
    assert density["source_unit"] == "g/cm^3"
    assert density["canonical_unit"] == "kg/m^3"
    assert density["dimension"] == "mass_density"
    assert density["scale"] == 1000.0


def test_v6b_training_and_evaluation_surface_banks_are_distinct() -> None:
    for role, registry in (
        ("development", development_registry()),
        ("confirmation", confirmation_registry()),
    ):
        rows, _ = build(role)
        queries = {row["query"] for row in rows}
        contracts = compile_registry_contracts(registry)

        training: set[str] = set()
        by_tool: dict[str, list[object]] = {}
        for contract in contracts.values():
            by_tool.setdefault(contract.tool_key, []).append(contract)
            training.update(contract.synthetic_positives)

        for contracts_for_tool in by_tool.values():
            supported = {
                str(contract.leaf)
                for contract in contracts_for_tool
            }
            for contract in contracts_for_tool:
                training.update(
                    hard_negative_texts(
                        resource_anchor=contract.resource_anchor,
                        supported_leaves=supported,
                    )
                )

        assert queries.isdisjoint(training)
