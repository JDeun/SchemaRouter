from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmarks.operation_routing_v6c_catalog import (  # noqa: E402
    confirmation_registry,
    development_registry,
)
from benchmarks.schema_adb_baseline import compile_registry_contracts  # noqa: E402
from benchmarks.schema_density_ratio import (  # noqa: E402
    VARIANCE_FLOOR,
    density_ratio,
    fit_tied_diagonal_density,
)


def test_density_ratio_prefers_matching_population() -> None:
    model = fit_tied_diagonal_density(
        tool_key="demo",
        positives=[
            [1.0, 0.0, 0.02],
            [0.99, 0.02, 0.01],
            [0.98, -0.01, 0.03],
        ],
        negatives=[
            [0.0, 1.0, 0.02],
            [0.02, 0.99, 0.01],
            [-0.01, 0.98, 0.03],
        ],
    )
    positive_ratio, positive_d2, positive_negative_d2 = density_ratio(
        [1.0, 0.0, 0.01],
        model,
    )
    negative_ratio, negative_positive_d2, negative_d2 = density_ratio(
        [0.0, 1.0, 0.01],
        model,
    )

    assert positive_ratio > 0.0
    assert positive_d2 < positive_negative_d2
    assert negative_ratio < 0.0
    assert negative_d2 < negative_positive_d2
    assert all(value >= VARIANCE_FLOOR for value in model.variance)


def test_v6c_registries_compile_schema_evidence() -> None:
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


def test_v6c_typed_unit_metadata_survives_compilation() -> None:
    dev = compile_registry_contracts(development_registry())
    pressure = next(
        row
        for row in dev["pressure.current"].data_contract
        if row.get("name") == "pressure"
    )
    assert pressure["semantic_id"] == "environment.pressure"
    assert pressure["source_unit"] == "kPa"
    assert pressure["canonical_unit"] == "Pa"
    assert pressure["dimension"] == "pressure"
    assert pressure["scale"] == 1000.0

    confirm = compile_registry_contracts(confirmation_registry())
    flow = next(
        row
        for row in confirm["flow_rate.current"].data_contract
        if row.get("name") == "volumetric_flow_rate"
    )
    assert flow["semantic_id"] == "process.volumetric_flow_rate"
    assert flow["source_unit"] == "L/min"
    assert flow["canonical_unit"] == "m^3/s"


def test_density_core_contains_no_v6c_route_identities() -> None:
    source = (ROOT / "benchmarks" / "schema_density_ratio.py").read_text(encoding="utf-8")
    for forbidden in (
        "authorizations_api.u71",
        "literature_index.l71",
        "credentials_api.c71",
        "sample_catalog.s71",
    ):
        assert forbidden not in source
