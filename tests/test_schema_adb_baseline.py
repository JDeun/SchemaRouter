from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmarks.operation_routing_v6a_catalog import (  # noqa: E402
    confirmation_registry,
    development_registry,
)
from benchmarks.schema_adb_baseline import (  # noqa: E402
    AdbBoundary,
    SchemaAdbRouter,
    compile_registry_contracts,
    learn_adb_radius,
)
from schemarouter import EndpointSpec, InMemoryRegistry, ToolSpec  # noqa: E402


def test_adb_radius_is_deterministic_and_tracks_positive_geometry() -> None:
    distances = [0.1, 0.2, 0.3, 0.4, 0.5]
    first = learn_adb_radius(distances)
    second = learn_adb_radius(distances)

    assert first == second
    assert 0.20 <= first <= 0.40


def test_every_known_route_compiles_exactly_18_schema_positives() -> None:
    contracts = compile_registry_contracts(development_registry())
    assert contracts
    assert all(contract.leaf is not None for contract in contracts.values())
    assert all(len(contract.synthetic_positives) == 18 for contract in contracts.values())


def test_typed_unit_metadata_survives_boundary_compilation() -> None:
    dev = compile_registry_contracts(development_registry())
    humidity = next(
        item
        for item in dev["humidity.current"].data_contract
        if item.get("name") == "relative_humidity"
    )
    assert humidity["type"] == "number"
    assert humidity["semantic_id"] == "environment.relative_humidity"
    assert humidity["source_unit"] == "%RH"
    assert humidity["canonical_unit"] == "1"
    assert humidity["dimension"] == "relative_humidity"
    assert humidity["scale"] == 0.01
    assert humidity["offset"] == 0.0

    confirm = compile_registry_contracts(confirmation_registry())
    conductivity = next(
        item
        for item in confirm["conductivity.current"].data_contract
        if item.get("name") == "conductivity"
    )
    assert conductivity["source_unit"] == "mS/cm"
    assert conductivity["canonical_unit"] == "S/m"
    assert conductivity["scale"] == 0.1


def _authority_registry() -> InMemoryRegistry:
    registry = InMemoryRegistry()
    registry.register(
        ToolSpec(
            name="demo",
            description="Demo records",
            endpoints=[
                EndpointSpec(
                    name="retrieve",
                    description="Retrieve one existing record",
                    read_only=True,
                ),
                EndpointSpec(
                    name="update",
                    description="Update an existing record",
                    read_only=False,
                ),
            ],
        )
    )
    return registry


def _keyword_embedder(texts: list[str]) -> list[list[float]]:
    vectors: list[list[float]] = []
    for text in texts:
        lowered = text.casefold()
        if text == "cross":
            vectors.append([0.0, 1.0])
        elif "update" in lowered or "modify" in lowered or "수정" in lowered:
            vectors.append([0.0, 1.0])
        else:
            vectors.append([1.0, 0.0])
    return vectors


def test_boundary_can_only_preserve_raw_winner_or_abstain() -> None:
    router = SchemaAdbRouter(_authority_registry(), _keyword_embedder)

    # Force the raw BGE selector to prefer retrieve for the cross query while
    # the query lies inside the update boundary. The ADB layer still may not
    # switch positive execution authority to update.
    router.schema_vectors["demo.retrieve"] = [0.0, 1.0]
    router.action_vectors["demo.retrieve"] = [0.0, 1.0]
    router.schema_vectors["demo.update"] = [1.0, 0.0]
    router.action_vectors["demo.update"] = [1.0, 0.0]
    existing = router.boundaries["demo.update"]
    router.boundaries["demo.update"] = AdbBoundary(
        route_id=existing.route_id,
        tool_key=existing.tool_key,
        leaf=existing.leaf,
        centroid=(0.0, 1.0),
        radius=0.01,
        synthetic_count=existing.synthetic_count,
        distances=existing.distances,
    )

    result = router.route("cross")
    assert result["raw_top_route"] == "demo.retrieve"
    assert any(
        row["route_id"] == "demo.update" and row["inside"]
        for row in result["boundary_rows"]
    )
    assert result["predicted"] == "demo.retrieve"


def test_core_source_contains_no_v6a_evaluation_route_identities() -> None:
    source = (ROOT / "benchmarks" / "schema_adb_baseline.py").read_text()
    for forbidden in (
        "licenses_api.l17",
        "registry_ops.g17",
        "certificates_api.c17",
        "catalogue_ops.q17",
    ):
        assert forbidden not in source


def test_unknown_boundary_semantics_fail_open() -> None:
    registry = InMemoryRegistry()
    registry.register(
        ToolSpec(
            name="opaque",
            description="Opaque registered service",
            endpoints=[
                EndpointSpec(
                    name="x17",
                    description="Perform the registered opaque capability",
                )
            ],
        )
    )
    router = SchemaAdbRouter(registry, _keyword_embedder)
    result = router.route("cross")
    assert result["raw_top_route"] == "opaque.x17"
    assert result["predicted"] == "opaque.x17"
    assert result["tool_has_unknown_leaf"] is True
    assert result["boundary_rows"] == []
