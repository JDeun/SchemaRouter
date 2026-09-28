from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmarks.operation_routing_v6g_catalog import (  # noqa: E402
    CONFIRM_ROUTE_SPECS,
    DEV_ROUTE_SPECS,
    confirmation_registry,
    development_registry,
)


def _endpoint(registry, route_id: str):
    tool_key, endpoint_name = route_id.split(".", 1)
    tool = next(tool for tool in registry.tools() if tool.key == tool_key)
    return next(endpoint for endpoint in tool.endpoints if endpoint.name == endpoint_name)


def test_v6g_catalog_shape() -> None:
    for registry, specs in (
        (development_registry(), DEV_ROUTE_SPECS),
        (confirmation_registry(), CONFIRM_ROUTE_SPECS),
    ):
        assert len(specs) == 19
        assert len(registry.tools()) == 7
        assert sorted(len(tool.endpoints) for tool in registry.tools()) == [
            2,
            2,
            3,
            3,
            3,
            3,
            3,
        ]


def test_v6g_shear_modulus_unit_contract() -> None:
    endpoint = _endpoint(development_registry(), "shear_modulus.current")
    field = endpoint.output_fields[0]
    assert field.semantic_id == "material.shear_modulus"
    assert field.unit == "GPa"
    assert field.unit_normalization is not None
    assert field.unit_normalization.dimension == "elastic_modulus"
    assert field.unit_normalization.canonical_unit == "Pa"
    assert field.unit_normalization.scale == 1_000_000_000.0


def test_v6g_electrical_conductivity_unit_contract() -> None:
    endpoint = _endpoint(
        confirmation_registry(),
        "electrical_conductivity.current",
    )
    field = endpoint.output_fields[0]
    assert field.semantic_id == "material.electrical_conductivity"
    assert field.unit == "mS/cm"
    assert field.unit_normalization is not None
    assert field.unit_normalization.dimension == "electrical_conductivity"
    assert field.unit_normalization.canonical_unit == "S/m"
    assert field.unit_normalization.scale == 0.1
