# Issue #708 regression coverage.
from schemarouter.capability_contracts import CapabilityContract, CapabilityFieldContract
from schemarouter.capability_drift import (
    capability_contract_fingerprint,
    compare_capability_graph_snapshot,
)
from schemarouter.capability_graph import build_capability_dependency_graph


def _field(semantic_id: str, *, unit: str | None = None) -> CapabilityFieldContract:
    return CapabilityFieldContract(
        semantic_id=semantic_id,
        json_schema={"type": "number"},
        unit=unit,
        dimension="energy" if unit else None,
    )


def test_fingerprint_is_stable_for_mapping_order() -> None:
    left = CapabilityContract(
        capability_id="a",
        produces=[CapabilityFieldContract(
            semantic_id="energy",
            qualifiers={"phase": "solid", "method": "dft"},
        )],
    )
    right = CapabilityContract(
        capability_id="a",
        produces=[CapabilityFieldContract(
            semantic_id="energy",
            qualifiers={"method": "dft", "phase": "solid"},
        )],
    )
    assert capability_contract_fingerprint(left) == capability_contract_fingerprint(right)


def test_identical_snapshot_does_not_invalidate_graph() -> None:
    producer = CapabilityContract(capability_id="producer", produces=[_field("energy", unit="eV")])
    consumer = CapabilityContract(capability_id="consumer", requires=[_field("energy", unit="eV")])
    graph = build_capability_dependency_graph([producer, consumer])

    report = compare_capability_graph_snapshot(graph, [producer, consumer], [producer, consumer])

    assert report.compatibility == "identical"
    assert report.invalidated_capability_ids == ()
    assert report.changes == []


def test_changed_contract_invalidates_incident_graph_nodes() -> None:
    producer = CapabilityContract(capability_id="producer", produces=[_field("energy", unit="eV")])
    consumer = CapabilityContract(capability_id="consumer", requires=[_field("energy", unit="eV")])
    graph = build_capability_dependency_graph([producer, consumer])
    changed = CapabilityContract(capability_id="producer", produces=[_field("energy", unit="meV")])

    report = compare_capability_graph_snapshot(graph, [producer, consumer], [changed, consumer])

    assert report.compatibility == "breaking"
    assert report.invalidated_capability_ids == ("consumer", "producer")
    assert report.changes[0].kind == "contract_changed"


def test_additive_capability_only_requires_new_node_recompile() -> None:
    existing = CapabilityContract(capability_id="existing")
    added = CapabilityContract(capability_id="added")
    graph = build_capability_dependency_graph([existing])

    report = compare_capability_graph_snapshot(graph, [existing], [existing, added])

    assert report.compatibility == "compatible"
    assert report.invalidated_capability_ids == ("added",)
    assert report.changes[0].kind == "added"


def test_removed_capability_invalidates_existing_neighbors() -> None:
    producer = CapabilityContract(capability_id="producer", produces=[_field("energy", unit="eV")])
    consumer = CapabilityContract(capability_id="consumer", requires=[_field("energy", unit="eV")])
    graph = build_capability_dependency_graph([producer, consumer])

    report = compare_capability_graph_snapshot(graph, [producer, consumer], [consumer])

    assert report.compatibility == "breaking"
    assert report.invalidated_capability_ids == ("consumer", "producer")
    assert report.changes[0].kind == "removed"
