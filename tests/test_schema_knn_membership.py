from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmarks.operation_routing_v6e_catalog import (  # noqa: E402
    confirmation_registry,
    development_registry,
)
from benchmarks.schema_adb_baseline import compile_registry_contracts  # noqa: E402
from benchmarks.schema_knn_membership import (  # noqa: E402
    BACKGROUND_ANCHORS,
    K_NEIGHBORS,
    EvidencePoint,
    knn_mean_cosine_distance,
)


def test_knn3_uses_three_nearest_cosine_neighbors() -> None:
    points = (
        EvidencePoint("same", (1.0, 0.0)),
        EvidencePoint("near", (0.8, 0.6)),
        EvidencePoint("mid", (0.6, 0.8)),
        EvidencePoint("far", (0.0, 1.0)),
    )
    distance, nearest = knn_mean_cosine_distance([1.0, 0.0], points)

    assert K_NEIGHBORS == 3
    assert [row[0] for row in nearest] == ["same", "near", "mid"]
    assert abs(distance - ((0.0 + 0.2 + 0.4) / 3.0)) < 1e-12


def test_background_bank_is_frozen_16_anchor_bank() -> None:
    assert len(BACKGROUND_ANCHORS) == 16
    assert BACKGROUND_ANCHORS[0] == "sports scores, team standings, and game results"
    assert BACKGROUND_ANCHORS[-1] == (
        "general knowledge, trivia, and casual conversation"
    )


def test_v6e_registries_compile_schema_evidence() -> None:
    for registry in (development_registry(), confirmation_registry()):
        contracts = compile_registry_contracts(registry)
        assert len(contracts) == 19
        assert all(contract.leaf is not None for contract in contracts.values())
        assert all(
            len(contract.synthetic_positives) == 18
            for contract in contracts.values()
        )
        assert {contract.adapter or "native" for contract in contracts.values()} == {
            "native",
            "openapi",
            "mcp",
        }


def test_v6e_typed_unit_metadata_survives_compilation() -> None:
    dev = compile_registry_contracts(development_registry())
    expansion = next(
        row
        for row in dev["expansion_coefficient.current"].data_contract
        if row.get("name") == "expansion_coefficient"
    )
    assert expansion["semantic_id"] == "material.thermal_expansion_coefficient"
    assert expansion["source_unit"] == "1/K"
    assert expansion["canonical_unit"] == "1/K"
    assert expansion["dimension"] == "thermal_expansion_coefficient"
    assert expansion["scale"] == 1.0

    confirm = compile_registry_contracts(confirmation_registry())
    heat = next(
        row
        for row in confirm["heat_capacity.current"].data_contract
        if row.get("name") == "heat_capacity"
    )
    assert heat["semantic_id"] == "material.specific_heat_capacity"
    assert heat["source_unit"] == "J/(kg·K)"
    assert heat["canonical_unit"] == "J/(kg·K)"
    assert heat["dimension"] == "specific_heat_capacity"
    assert heat["scale"] == 1.0


def test_knn_core_contains_no_v6e_route_identities() -> None:
    source = (ROOT / "benchmarks" / "schema_knn_membership.py").read_text(
        encoding="utf-8"
    )
    for forbidden in (
        "consents_api.g41",
        "assay_index.h41",
        "tokens_api.j41",
        "batch_index.k41",
    ):
        assert forbidden not in source
