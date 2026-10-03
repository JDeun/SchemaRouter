from __future__ import annotations

import pytest

from schemarouter import (
    CapabilityContract,
    CapabilityFieldContract,
    build_capability_dependency_graph,
    dependency_cycles,
)


def field(semantic_id: str) -> CapabilityFieldContract:
    return CapabilityFieldContract(semantic_id=semantic_id, json_schema={"type": "string"})


def test_dependency_graph_links_only_satisfied_contracts() -> None:
    search = CapabilityContract(
        capability_id="search_material",
        produces=[field("resource.material_id")],
    )
    structure = CapabilityContract(
        capability_id="get_structure",
        requires=[field("resource.material_id")],
        produces=[field("resource.structure_id")],
    )
    unrelated = CapabilityContract(
        capability_id="get_weather",
        requires=[field("geo.location")],
    )
    graph = build_capability_dependency_graph([search, structure, unrelated])
    assert graph.successors("search_material") == ("get_structure",)
    assert graph.predecessors("get_structure") == ("search_material",)
    assert graph.predecessors("get_weather") == ()


def test_dependency_graph_does_not_create_edges_for_unknown_contracts() -> None:
    producer = CapabilityContract(
        capability_id="producer",
        produces=[CapabilityFieldContract(semantic_id="resource.id")],
    )
    consumer = CapabilityContract(
        capability_id="consumer",
        requires=[field("resource.id")],
    )
    graph = build_capability_dependency_graph([producer, consumer])
    assert graph.edges == []


def test_dependency_graph_rejects_duplicate_capability_ids() -> None:
    duplicate = CapabilityContract(capability_id="same")
    with pytest.raises(ValueError, match="unique"):
        build_capability_dependency_graph([duplicate, duplicate])


def test_cycle_detection_reports_contract_cycle_without_executing_it() -> None:
    first = CapabilityContract(
        capability_id="first",
        requires=[field("state.b")],
        produces=[field("state.a")],
    )
    second = CapabilityContract(
        capability_id="second",
        requires=[field("state.a")],
        produces=[field("state.b")],
    )
    graph = build_capability_dependency_graph([first, second])
    assert dependency_cycles(graph) == [("first", "second")]
