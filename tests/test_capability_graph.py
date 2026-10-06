from __future__ import annotations

from itertools import permutations

import pytest

import schemarouter.capability_graph as capability_graph_module
from schemarouter import (
    CapabilityComposition,
    CapabilityContract,
    CapabilityDependencyEdge,
    CapabilityDependencyGraph,
    CapabilityFieldContract,
    CompatibilityContext,
    SemanticEquivalence,
    build_capability_dependency_graph,
    compare_capability_composition,
    dependency_cycles,
    dependency_strongly_connected_components,
    update_capability_dependency_graph,
)


def field(semantic_id: str) -> CapabilityFieldContract:
    return CapabilityFieldContract(
        semantic_id=semantic_id,
        json_schema={"type": "string"},
    )


def _reference_graph(
    capabilities: list[CapabilityContract],
    *,
    context: CompatibilityContext | None = None,
) -> CapabilityDependencyGraph:
    ids = [capability.capability_id for capability in capabilities]
    if len(ids) != len(set(ids)):
        raise ValueError("capability_id values must be unique")

    edges: list[CapabilityDependencyEdge] = []
    for producer in capabilities:
        for consumer in capabilities:
            if producer.capability_id == consumer.capability_id or not consumer.requires:
                continue
            compatibility = compare_capability_composition(
                producer,
                consumer,
                context=context,
            )
            if compatibility.satisfies:
                edges.append(
                    CapabilityDependencyEdge(
                        producer_id=producer.capability_id,
                        consumer_id=consumer.capability_id,
                        compatibility=compatibility,
                    )
                )
    return CapabilityDependencyGraph(
        capability_ids=tuple(sorted(ids)),
        edges=sorted(edges, key=lambda edge: (edge.producer_id, edge.consumer_id)),
    )


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


def test_dependency_graph_adjacency_indexes_preserve_edge_order() -> None:
    compatibility = CapabilityComposition(status="compatible")
    graph = CapabilityDependencyGraph(
        capability_ids=("a", "b", "c", "d"),
        edges=[
            CapabilityDependencyEdge(
                producer_id="a",
                consumer_id="c",
                compatibility=compatibility,
            ),
            CapabilityDependencyEdge(
                producer_id="a",
                consumer_id="b",
                compatibility=compatibility,
            ),
            CapabilityDependencyEdge(
                producer_id="d",
                consumer_id="b",
                compatibility=compatibility,
            ),
        ],
    )

    assert graph.successors("a") == ("c", "b")
    assert graph.predecessors("b") == ("a", "d")
    assert graph.successors("missing") == ()


def test_dependency_graph_assignment_rebuilds_adjacency_indexes() -> None:
    compatibility = CapabilityComposition(status="compatible")
    graph = CapabilityDependencyGraph(
        capability_ids=("a", "b"),
        edges=[
            CapabilityDependencyEdge(
                producer_id="a",
                consumer_id="b",
                compatibility=compatibility,
            )
        ],
    )
    assert graph.successors("a") == ("b",)

    graph.edges = []

    assert isinstance(graph.edges, tuple)
    assert graph.successors("a") == ()
    assert graph.predecessors("b") == ()


def test_dependency_graph_model_copy_update_rebuilds_adjacency_indexes() -> None:
    compatibility = CapabilityComposition(status="compatible")
    graph = CapabilityDependencyGraph(
        capability_ids=("a", "b", "c"),
        edges=[
            CapabilityDependencyEdge(
                producer_id="a",
                consumer_id="b",
                compatibility=compatibility,
            )
        ],
    )
    replacement = CapabilityDependencyEdge(
        producer_id="b",
        consumer_id="c",
        compatibility=compatibility,
    )

    copied = graph.model_copy(update={"edges": [replacement]}, deep=True)

    assert copied.successors("a") == ()
    assert copied.successors("b") == ("c",)
    assert copied.predecessors("c") == ("b",)
    assert graph.successors("a") == ("b",)


def test_dependency_graph_private_indexes_do_not_change_serialization() -> None:
    graph = CapabilityDependencyGraph(
        capability_ids=("a", "b"),
        edges=[
            CapabilityDependencyEdge(
                producer_id="a",
                consumer_id="b",
                compatibility=CapabilityComposition(status="compatible"),
            )
        ],
    )

    dumped = graph.model_dump(mode="json")

    assert isinstance(graph.edges, tuple)
    assert set(dumped) == {"capability_ids", "edges"}
    assert dumped["capability_ids"] == ["a", "b"]
    assert len(dumped["edges"]) == 1


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
    assert graph.edges == ()


def test_index_prunes_full_comparison_calls_on_sparse_registry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    capabilities = [
        CapabilityContract(
            capability_id=f"cap-{index:03d}",
            requires=[] if index == 0 else [field(f"state.{index - 1}")],
            produces=[field(f"state.{index}")],
        )
        for index in range(200)
    ]
    original = capability_graph_module.compare_capability_composition
    calls = 0

    def counted(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(
        capability_graph_module,
        "compare_capability_composition",
        counted,
    )

    graph = capability_graph_module.build_capability_dependency_graph(capabilities)

    assert len(graph.edges) == 199
    assert calls == 199


def test_dependency_graph_rejects_duplicate_capability_ids() -> None:
    duplicate = CapabilityContract(capability_id="same")
    with pytest.raises(ValueError, match="unique"):
        build_capability_dependency_graph([duplicate, duplicate])


def test_indexed_graph_matches_reference_all_pairs() -> None:
    capabilities = [
        CapabilityContract(
            capability_id="material_search",
            produces=[
                field("resource.material_id"),
                field("resource.formula"),
            ],
        ),
        CapabilityContract(
            capability_id="structure_lookup",
            requires=[field("resource.material_id")],
            produces=[field("resource.structure_id")],
        ),
        CapabilityContract(
            capability_id="paper_lookup",
            requires=[field("resource.material_id")],
            produces=[field("document.abstract")],
        ),
        CapabilityContract(
            capability_id="structure_postprocess",
            requires=[
                field("resource.structure_id"),
                field("resource.material_id"),
            ],
        ),
        CapabilityContract(
            capability_id="weather",
            requires=[field("geo.location")],
        ),
    ]

    indexed = build_capability_dependency_graph(capabilities)
    reference = _reference_graph(capabilities)

    assert indexed == reference


def test_graph_output_is_input_permutation_invariant() -> None:
    capabilities = [
        CapabilityContract(
            capability_id="a",
            produces=[field("state.a")],
            requires=[field("state.c")],
        ),
        CapabilityContract(
            capability_id="b",
            produces=[field("state.b")],
            requires=[field("state.a")],
        ),
        CapabilityContract(
            capability_id="c",
            produces=[field("state.c")],
            requires=[field("state.b")],
        ),
    ]
    expected = build_capability_dependency_graph(capabilities)

    for ordering in permutations(capabilities):
        assert build_capability_dependency_graph(list(ordering)) == expected


def test_index_expands_declared_semantic_equivalence_without_false_negative() -> None:
    producer = CapabilityContract(
        capability_id="producer",
        produces=[field("material.identifier")],
    )
    consumer = CapabilityContract(
        capability_id="consumer",
        requires=[field("resource.material_id")],
    )
    context = CompatibilityContext(
        semantic_equivalences=[
            SemanticEquivalence(
                canonical_id="resource.material_id",
                aliases={"material.identifier", "mp.material_id"},
            )
        ]
    )

    indexed = build_capability_dependency_graph(
        [producer, consumer],
        context=context,
    )
    reference = _reference_graph(
        [producer, consumer],
        context=context,
    )

    assert indexed == reference
    assert indexed.successors("producer") == ("consumer",)


def test_index_and_reference_graph_share_transitive_equivalence_semantics() -> None:
    producer = CapabilityContract(
        capability_id="producer",
        produces=[field("semantic.C")],
    )
    consumer = CapabilityContract(
        capability_id="consumer",
        requires=[field("semantic.A")],
    )
    context = CompatibilityContext(
        semantic_equivalences=[
            SemanticEquivalence(canonical_id="semantic.A", aliases={"semantic.B"}),
            SemanticEquivalence(canonical_id="semantic.B", aliases={"semantic.C"}),
        ]
    )

    indexed = build_capability_dependency_graph(
        [producer, consumer],
        context=context,
    )
    reference = _reference_graph(
        [producer, consumer],
        context=context,
    )

    assert indexed == reference
    assert indexed.successors("producer") == ("consumer",)


def test_incremental_update_matches_full_rebuild_for_add_remove_and_change() -> None:
    old = [
        CapabilityContract(
            capability_id="producer",
            produces=[field("state.a")],
        ),
        CapabilityContract(
            capability_id="consumer",
            requires=[field("state.a")],
        ),
        CapabilityContract(
            capability_id="removed",
            produces=[field("state.removed")],
        ),
    ]
    graph = build_capability_dependency_graph(old)
    new = [
        CapabilityContract(
            capability_id="producer",
            produces=[field("state.b")],
        ),
        CapabilityContract(
            capability_id="consumer",
            requires=[field("state.b")],
        ),
        CapabilityContract(
            capability_id="added",
            requires=[field("state.b")],
        ),
    ]

    incremental = update_capability_dependency_graph(graph, old, new)
    rebuilt = build_capability_dependency_graph(new)

    assert incremental == rebuilt


def test_incremental_update_returns_deterministic_copy_when_nothing_changed() -> None:
    capabilities = [
        CapabilityContract(
            capability_id="producer",
            produces=[field("state.a")],
        ),
        CapabilityContract(
            capability_id="consumer",
            requires=[field("state.a")],
        ),
    ]
    graph = build_capability_dependency_graph(capabilities)

    updated = update_capability_dependency_graph(
        graph,
        capabilities,
        list(reversed(capabilities)),
    )

    assert updated == graph


def test_incremental_update_rejects_mismatched_previous_graph() -> None:
    previous = [CapabilityContract(capability_id="a")]
    graph = CapabilityDependencyGraph(capability_ids=("b",))

    with pytest.raises(ValueError, match="previous capability IDs"):
        update_capability_dependency_graph(graph, previous, previous)


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


def test_scc_cycle_analysis_is_bounded_on_dense_component() -> None:
    ids = tuple(f"n{index:02d}" for index in range(8))
    edges = [
        CapabilityDependencyEdge(
            producer_id=producer,
            consumer_id=consumer,
            compatibility=compare_capability_composition(
                CapabilityContract(
                    capability_id=producer,
                    produces=[field("shared")],
                ),
                CapabilityContract(
                    capability_id=consumer,
                    requires=[field("shared")],
                ),
            ),
        )
        for producer in ids
        for consumer in ids
        if producer != consumer
    ]
    graph = CapabilityDependencyGraph(capability_ids=ids, edges=edges)

    components = dependency_strongly_connected_components(graph)
    cycles = dependency_cycles(graph, max_witnesses=2)

    assert components == (ids,)
    assert len(cycles) == 1
    assert set(cycles[0]).issubset(set(ids))


@pytest.mark.parametrize("value", [0, -1, True, False])
def test_cycle_witness_limit_requires_positive_integer(value: object) -> None:
    with pytest.raises(ValueError, match="max_witnesses"):
        dependency_cycles(CapabilityDependencyGraph(), max_witnesses=value)  # type: ignore[arg-type]


def _linear_dependency_graph(size: int, *, close_cycle: bool) -> CapabilityDependencyGraph:
    ids = tuple(f"node-{index:05d}" for index in range(size))
    compatibility = CapabilityComposition(status="compatible")
    edges = [
        CapabilityDependencyEdge(
            producer_id=ids[index],
            consumer_id=ids[index + 1],
            compatibility=compatibility,
        )
        for index in range(size - 1)
    ]
    if close_cycle:
        edges.append(
            CapabilityDependencyEdge(
                producer_id=ids[-1],
                consumer_id=ids[0],
                compatibility=compatibility,
            )
        )
    return CapabilityDependencyGraph(
        capability_ids=ids,
        edges=edges,
    )


def test_scc_traversal_is_stack_safe_above_python_recursion_depth() -> None:
    graph = _linear_dependency_graph(1500, close_cycle=False)

    components = dependency_strongly_connected_components(graph)

    assert len(components) == 1500
    assert components[0] == ("node-00000",)
    assert components[-1] == ("node-01499",)


def test_cycle_witness_is_stack_safe_for_large_scc() -> None:
    graph = _linear_dependency_graph(1500, close_cycle=True)

    components = dependency_strongly_connected_components(graph)
    cycles = dependency_cycles(graph, max_witnesses=1)

    assert len(components) == 1
    assert len(components[0]) == 1500
    assert len(cycles) == 1
    assert len(cycles[0]) == 1500
    assert cycles[0][0] == "node-00000"
    assert cycles[0][-1] == "node-01499"
