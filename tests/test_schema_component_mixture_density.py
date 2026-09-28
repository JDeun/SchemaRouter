from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmarks.operation_routing_v6d_catalog import (  # noqa: E402
    confirmation_registry,
    development_registry,
)
from benchmarks.schema_adb_baseline import compile_registry_contracts  # noqa: E402
from benchmarks.schema_component_mixture_density import (  # noqa: E402
    VARIANCE_FLOOR,
    fit_component_mixture_density,
    mixture_density_ratio,
)


def test_component_mixture_prefers_matching_mode() -> None:
    model = fit_component_mixture_density(
        tool_key="demo",
        positive_components=[
            ("p1", [[1.0, 0.0], [0.98, 0.02], [0.99, -0.01]]),
            ("p2", [[-1.0, 0.0], [-0.98, 0.02], [-0.99, -0.01]]),
        ],
        negative_components=[
            ("n1", [[0.0, 1.0], [0.02, 0.98], [-0.01, 0.99]]),
            ("n2", [[0.0, -1.0], [0.02, -0.98], [-0.01, -0.99]]),
        ],
    )

    positive = mixture_density_ratio([1.0, 0.0], model)
    negative = mixture_density_ratio([0.0, 1.0], model)

    assert positive[0] > 0.0
    assert negative[0] < 0.0
    assert positive[1] > positive[2]
    assert negative[2] > negative[1]
    assert all(value >= VARIANCE_FLOOR for value in model.variance)


def test_v6d_registries_compile_schema_evidence() -> None:
    for registry in (development_registry(), confirmation_registry()):
        contracts = compile_registry_contracts(registry)
        assert len(contracts) == 19
        assert all(contract.leaf is not None for contract in contracts.values())
        assert all(len(contract.synthetic_positives) == 18 for contract in contracts.values())
        assert {contract.adapter or "native" for contract in contracts.values()} == {
            "native",
            "openapi",
            "mcp",
        }


def test_v6d_typed_unit_metadata_survives_compilation() -> None:
    dev = compile_registry_contracts(development_registry())
    tension = next(
        row
        for row in dev["surface_tension.current"].data_contract
        if row.get("name") == "surface_tension"
    )
    assert tension["semantic_id"] == "material.surface_tension"
    assert tension["source_unit"] == "mN/m"
    assert tension["canonical_unit"] == "N/m"
    assert tension["dimension"] == "surface_tension"
    assert tension["scale"] == 0.001

    confirm = compile_registry_contracts(confirmation_registry())
    conductivity = next(
        row
        for row in confirm["thermal_conductivity.current"].data_contract
        if row.get("name") == "thermal_conductivity"
    )
    assert conductivity["semantic_id"] == "material.thermal_conductivity"
    assert conductivity["source_unit"] == "W/(m·K)"
    assert conductivity["canonical_unit"] == "W/(m·K)"
    assert conductivity["dimension"] == "thermal_conductivity"
    assert conductivity["scale"] == 1.0


def test_mixture_core_contains_no_v6d_route_identities() -> None:
    source = (
        ROOT / "benchmarks" / "schema_component_mixture_density.py"
    ).read_text(encoding="utf-8")
    for forbidden in (
        "warrants_api.w14",
        "specimen_index.x14",
        "passes_api.y14",
        "artifact_catalog.z14",
    ):
        assert forbidden not in source
