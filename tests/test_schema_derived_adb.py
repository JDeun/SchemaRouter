from __future__ import annotations

import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmarks.operation_routing_v6a_catalog import (  # noqa: E402
    confirmation_registry,
    development_registry,
)
from benchmarks.schema_derived_adb import (  # noqa: E402
    ADB_MIN_VIEWS,
    SchemaDerivedADBRouter,
    compile_registry_contracts,
    learn_adb_radius,
    schema_positive_views,
)
from schemarouter import EndpointSpec, InMemoryRegistry, ToolSpec  # noqa: E402


def test_adb_radius_is_positive_finite_and_deterministic() -> None:
    distances = [0.10, 0.18, 0.22, 0.31, 0.44, 0.53]
    first = learn_adb_radius(distances)
    second = learn_adb_radius(distances)

    assert math.isfinite(first)
    assert first > 0.0
    assert first == second


def test_schema_positive_views_use_only_trusted_endpoint_metadata() -> None:
    registry = development_registry()
    tool = next(tool for tool in registry.tools() if tool.key == "voltage")
    endpoint = next(endpoint for endpoint in tool.endpoints if endpoint.name == "current")
    views = schema_positive_views(tool, endpoint)

    assert len(views) >= ADB_MIN_VIEWS
    assert any("Retrieve the current voltage observation" in view for view in views)
    assert any("Voltage observation and forecast service" in view for view in views)
    assert any("electrical.voltage" in view for view in views)
    assert not any("v6a-dev" in view for view in views)


def test_all_evaluation_endpoints_have_adb_ready_views() -> None:
    for registry in (development_registry(), confirmation_registry()):
        for tool in registry.tools():
            for endpoint in tool.endpoints:
                assert len(schema_positive_views(tool, endpoint)) >= ADB_MIN_VIEWS


def test_typed_unit_metadata_is_preserved_in_contract() -> None:
    dev = compile_registry_contracts(development_registry())
    voltage = next(
        row
        for row in dev["voltage.current"].data_contract
        if row.get("name") == "voltage"
    )
    assert voltage["type"] == "number"
    assert voltage["semantic_id"] == "electrical.voltage"
    assert voltage["source_unit"] == "mV"
    assert voltage["canonical_unit"] == "V"
    assert voltage["dimension"] == "electric_potential"
    assert voltage["scale"] == 0.001
    assert voltage["offset"] == 0.0
    assert voltage["qualifiers"] == {"statistic": "instantaneous"}

    confirm = compile_registry_contracts(confirmation_registry())
    velocity = next(
        row
        for row in confirm["velocity.current"].data_contract
        if row.get("name") == "velocity"
    )
    assert velocity["source_unit"] == "km/h"
    assert velocity["canonical_unit"] == "m/s"
    assert velocity["dimension"] == "velocity"
    assert math.isclose(velocity["scale"], 1.0 / 3.6)


def test_behavior_source_contains_no_evaluation_route_identities() -> None:
    source = (ROOT / "benchmarks" / "schema_derived_adb.py").read_text()
    for forbidden in (
        "licenses_api.l17",
        "registry_ops.g17",
        "certificates_api.c17",
        "reference_ops.r17",
        "shipments.status",
        "profiles_api.r17",
    ):
        assert forbidden not in source


def test_unknown_boundary_fails_open_and_preserves_raw_route() -> None:
    registry = InMemoryRegistry()
    registry.register(
        ToolSpec(
            name="opaque",
            description="",
            endpoints=[
                EndpointSpec(
                    name="x17",
                    description="",
                    read_only=None,
                    destructive=None,
                )
            ],
        )
    )

    def embed(texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0] for _ in texts]

    router = SchemaDerivedADBRouter(registry, embed)
    result = router.route("perform an unknown action")

    assert result["raw_top_route"] == "opaque.x17"
    assert result["missing_boundary"] is True
    assert result["predicted"] == result["raw_top_route"]


def test_boundary_never_switches_positive_route() -> None:
    registry = InMemoryRegistry()
    registry.register(
        ToolSpec(
            name="demo",
            description="Demo record operations",
            endpoints=[
                EndpointSpec(
                    name="retrieve",
                    description="Retrieve one already-identified demo record",
                    read_only=True,
                ),
                EndpointSpec(
                    name="update",
                    description="Update fields on an existing demo record",
                    read_only=False,
                ),
            ],
        )
    )

    def embed(texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            lowered = text.casefold()
            if "update" in lowered:
                vectors.append([0.0, 1.0])
            elif "retrieve" in lowered or "demo record" in lowered:
                vectors.append([1.0, 0.0])
            else:
                vectors.append([1.0, 1.0])
        return vectors

    router = SchemaDerivedADBRouter(registry, embed)
    for query in ("retrieve demo record", "update demo record", "unsupported demo action"):
        result = router.route(query)
        assert result["predicted"] is None or result["predicted"] == result["raw_top_route"]
