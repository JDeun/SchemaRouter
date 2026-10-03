import pytest

from schemarouter.capability_contracts import CapabilityContract, CapabilityFieldContract
from schemarouter.capability_graph import build_capability_dependency_graph
from schemarouter.capability_snapshot import (
    compare_capability_snapshots,
    create_capability_graph_snapshot,
    require_capability_snapshot,
)


def _contracts(unit: str = "eV") -> list[CapabilityContract]:
    field = CapabilityFieldContract(
        semantic_id="energy",
        json_schema={"type": "number"},
        unit=unit,
        dimension="energy",
    )
    return [
        CapabilityContract(capability_id="producer", produces=[field]),
        CapabilityContract(capability_id="consumer", requires=[field]),
    ]


def test_snapshot_digest_is_stable_and_excludes_build_metadata() -> None:
    contracts = _contracts()
    graph = build_capability_dependency_graph(contracts)

    left = create_capability_graph_snapshot(
        graph,
        contracts,
        source_schema_fingerprints={"materials": "abc"},
        build_metadata={"builder": "ci-a"},
    )
    right = create_capability_graph_snapshot(
        graph,
        list(reversed(contracts)),
        source_schema_fingerprints={"materials": "abc"},
        build_metadata={"builder": "ci-b"},
    )

    assert left.snapshot_id == right.snapshot_id
    assert left.build_metadata != right.build_metadata


def test_drift_creates_successor_snapshot_and_comparison() -> None:
    old_contracts = _contracts("eV")
    new_contracts = _contracts("meV")
    old = create_capability_graph_snapshot(
        build_capability_dependency_graph(old_contracts),
        old_contracts,
    )
    new = create_capability_graph_snapshot(
        build_capability_dependency_graph(new_contracts),
        new_contracts,
    )

    comparison = compare_capability_snapshots(old, new)

    assert comparison.identical is False
    assert comparison.changed_capability_ids == ("consumer", "producer")


def test_pinned_snapshot_fails_closed_on_mismatch() -> None:
    contracts = _contracts()
    snapshot = create_capability_graph_snapshot(
        build_capability_dependency_graph(contracts),
        contracts,
    )

    assert require_capability_snapshot(snapshot, snapshot.snapshot_id) is snapshot
    with pytest.raises(ValueError, match="capability snapshot mismatch"):
        require_capability_snapshot(snapshot, "other")


def test_runtime_health_is_not_part_of_snapshot_model() -> None:
    assert "health" not in CapabilityGraphSnapshot.model_fields
    assert "health_status" not in CapabilityGraphSnapshot.model_fields
