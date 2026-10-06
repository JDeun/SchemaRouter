from __future__ import annotations

from collections.abc import Iterable

from pydantic import Field

from .capability_contracts import (
    CapabilityComposition,
    CapabilityContract,
    CapabilityFieldContract,
    CompatibilityContext,
    compare_capability_composition,
)
from .models import StrictModel


class CapabilityDependencyEdge(StrictModel):
    producer_id: str
    consumer_id: str
    compatibility: CapabilityComposition


class CapabilityDependencyGraph(StrictModel):
    capability_ids: tuple[str, ...] = ()
    edges: list[CapabilityDependencyEdge] = Field(default_factory=list)

    def successors(self, capability_id: str) -> tuple[str, ...]:
        return tuple(
            edge.consumer_id
            for edge in self.edges
            if edge.producer_id == capability_id
        )

    def predecessors(self, capability_id: str) -> tuple[str, ...]:
        return tuple(
            edge.producer_id
            for edge in self.edges
            if edge.consumer_id == capability_id
        )


def _capabilities_by_id(
    capabilities: Iterable[CapabilityContract],
) -> dict[str, CapabilityContract]:
    items = list(capabilities)
    by_id = {item.capability_id: item for item in items}
    if len(by_id) != len(items):
        raise ValueError("capability_id values must be unique")
    return by_id


def _equivalent_semantic_ids(
    semantic_id: str,
    context: CompatibilityContext | None,
) -> frozenset[str]:
    values = {semantic_id}
    if context is None:
        return frozenset(values)
    for equivalence in context.semantic_equivalences:
        if equivalence.contains(semantic_id):
            values.add(equivalence.canonical_id)
            values.update(equivalence.aliases)
    return frozenset(values)


def _producer_semantic_index(
    capabilities: dict[str, CapabilityContract],
) -> dict[str, set[str]]:
    index: dict[str, set[str]] = {}
    for capability_id, capability in capabilities.items():
        for produced in capability.produces:
            index.setdefault(produced.semantic_id, set()).add(capability_id)
    return index


def _candidate_producer_ids(
    consumer: CapabilityContract,
    semantic_index: dict[str, set[str]],
    *,
    context: CompatibilityContext | None,
) -> set[str]:
    """Return a conservative producer superset for one consumer.

    A producer cannot satisfy a requirement unless it emits the exact semantic ID or
    an explicitly equivalent ID. Type/unit/qualifier checks still run through the
    canonical composition comparator, so this index changes search cost only.
    """

    candidate_ids: set[str] | None = None
    for required in consumer.requires:
        matching: set[str] = set()
        for semantic_id in _equivalent_semantic_ids(required.semantic_id, context):
            matching.update(semantic_index.get(semantic_id, ()))
        if not matching:
            return set()
        if candidate_ids is None:
            candidate_ids = matching
        else:
            candidate_ids.intersection_update(matching)
        if not candidate_ids:
            return set()
    return candidate_ids or set()


def _compatible_edges_for_consumers(
    capabilities: dict[str, CapabilityContract],
    consumer_ids: Iterable[str],
    *,
    context: CompatibilityContext | None,
    require_incident_to: set[str] | None = None,
) -> list[CapabilityDependencyEdge]:
    semantic_index = _producer_semantic_index(capabilities)
    edges: list[CapabilityDependencyEdge] = []
    for consumer_id in sorted(set(consumer_ids)):
        consumer = capabilities[consumer_id]
        if not consumer.requires:
            continue
        for producer_id in sorted(
            _candidate_producer_ids(
                consumer,
                semantic_index,
                context=context,
            )
        ):
            if producer_id == consumer_id:
                continue
            if (
                require_incident_to is not None
                and producer_id not in require_incident_to
                and consumer_id not in require_incident_to
            ):
                continue
            compatibility = compare_capability_composition(
                capabilities[producer_id],
                consumer,
                context=context,
            )
            if compatibility.satisfies:
                edges.append(
                    CapabilityDependencyEdge(
                        producer_id=producer_id,
                        consumer_id=consumer_id,
                        compatibility=compatibility,
                    )
                )
    return edges


def build_capability_dependency_graph(
    capabilities: list[CapabilityContract],
    *,
    context: CompatibilityContext | None = None,
) -> CapabilityDependencyGraph:
    """Build contract-compatible edges using semantic indexes.

    The index is only a conservative prefilter. Every emitted edge is still decided by
    :func:`compare_capability_composition`, preserving type, unit, qualifier, and
    explicit semantic-equivalence semantics.
    """

    by_id = _capabilities_by_id(capabilities)
    capability_ids = tuple(sorted(by_id))
    edges = _compatible_edges_for_consumers(
        by_id,
        capability_ids,
        context=context,
    )
    edges.sort(key=lambda edge: (edge.producer_id, edge.consumer_id))
    return CapabilityDependencyGraph(
        capability_ids=capability_ids,
        edges=edges,
    )


def update_capability_dependency_graph(
    graph: CapabilityDependencyGraph,
    previous_capabilities: list[CapabilityContract],
    capabilities: list[CapabilityContract],
    *,
    context: CompatibilityContext | None = None,
) -> CapabilityDependencyGraph:
    """Incrementally rebuild edges incident to added, removed, or changed contracts.

    The compatibility context is assumed to be unchanged. If semantic equivalences or
    unit-conversion policy changes, callers must perform a full build because such a
    context change can affect edges between otherwise unchanged capabilities.
    """

    previous = _capabilities_by_id(previous_capabilities)
    current = _capabilities_by_id(capabilities)
    if set(graph.capability_ids) != set(previous):
        raise ValueError(
            "previous capability IDs must match the supplied dependency graph"
        )

    previous_ids = set(previous)
    current_ids = set(current)
    changed = previous_ids ^ current_ids
    for capability_id in previous_ids & current_ids:
        if previous[capability_id] != current[capability_id]:
            changed.add(capability_id)

    if not changed:
        return CapabilityDependencyGraph(
            capability_ids=tuple(sorted(current)),
            edges=sorted(
                graph.edges,
                key=lambda edge: (edge.producer_id, edge.consumer_id),
            ),
        )

    preserved = [
        edge
        for edge in graph.edges
        if edge.producer_id in current
        and edge.consumer_id in current
        and edge.producer_id not in changed
        and edge.consumer_id not in changed
    ]
    rebuilt = _compatible_edges_for_consumers(
        current,
        current.keys(),
        context=context,
        require_incident_to=changed,
    )
    edge_by_pair = {
        (edge.producer_id, edge.consumer_id): edge
        for edge in [*preserved, *rebuilt]
    }
    return CapabilityDependencyGraph(
        capability_ids=tuple(sorted(current)),
        edges=[
            edge_by_pair[pair]
            for pair in sorted(edge_by_pair)
        ],
    )


def _adjacency(
    graph: CapabilityDependencyGraph,
) -> dict[str, tuple[str, ...]]:
    values: dict[str, list[str]] = {
        capability_id: []
        for capability_id in graph.capability_ids
    }
    for edge in graph.edges:
        if edge.producer_id in values:
            values[edge.producer_id].append(edge.consumer_id)
    return {
        capability_id: tuple(sorted(set(successors)))
        for capability_id, successors in values.items()
    }


def dependency_strongly_connected_components(
    graph: CapabilityDependencyGraph,
) -> tuple[tuple[str, ...], ...]:
    """Return deterministic SCCs using an iterative Tarjan traversal."""

    adjacency = _adjacency(graph)
    index = 0
    tarjan_stack: list[str] = []
    on_stack: set[str] = set()
    indices: dict[str, int] = {}
    lowlinks: dict[str, int] = {}
    components: list[tuple[str, ...]] = []

    def discover(node: str) -> None:
        nonlocal index
        indices[node] = index
        lowlinks[node] = index
        index += 1
        tarjan_stack.append(node)
        on_stack.add(node)

    for root in sorted(graph.capability_ids):
        if root in indices:
            continue

        discover(root)
        frames: list[tuple[str, int]] = [(root, 0)]
        while frames:
            node, successor_index = frames[-1]
            successors = adjacency.get(node, ())

            if successor_index < len(successors):
                successor = successors[successor_index]
                frames[-1] = (node, successor_index + 1)
                if successor not in indices:
                    discover(successor)
                    frames.append((successor, 0))
                    continue
                if successor in on_stack:
                    lowlinks[node] = min(
                        lowlinks[node],
                        indices[successor],
                    )
                continue

            frames.pop()
            if frames:
                parent = frames[-1][0]
                lowlinks[parent] = min(
                    lowlinks[parent],
                    lowlinks[node],
                )

            if lowlinks[node] != indices[node]:
                continue

            component: list[str] = []
            while tarjan_stack:
                member = tarjan_stack.pop()
                on_stack.remove(member)
                component.append(member)
                if member == node:
                    break
            components.append(tuple(sorted(component)))

    return tuple(sorted(components))


def _cycle_witness(
    component: tuple[str, ...],
    adjacency: dict[str, tuple[str, ...]],
) -> tuple[str, ...] | None:
    allowed = set(component)
    if len(component) == 1:
        node = component[0]
        return (node,) if node in adjacency.get(node, ()) else None

    for start in component:
        path = [start]
        path_set = {start}
        frames: list[tuple[str, int]] = [(start, 0)]
        found: tuple[str, ...] | None = None

        while frames:
            current, successor_index = frames[-1]
            successors = adjacency.get(current, ())

            if successor_index >= len(successors):
                frames.pop()
                removed = path.pop()
                path_set.remove(removed)
                continue

            successor = successors[successor_index]
            frames[-1] = (current, successor_index + 1)
            if successor not in allowed:
                continue
            if successor == start:
                found = tuple(path)
                break
            if successor in path_set:
                continue

            path.append(successor)
            path_set.add(successor)
            frames.append((successor, 0))

        if found is not None:
            minimum_index = min(
                range(len(found)),
                key=found.__getitem__,
            )
            return found[minimum_index:] + found[:minimum_index]

    return None


def dependency_cycles(
    graph: CapabilityDependencyGraph,
    *,
    max_witnesses: int = 128,
) -> list[tuple[str, ...]]:
    """Return bounded deterministic cycle witnesses using SCC decomposition.

    At most one simple witness is emitted per cyclic strongly connected component. This
    avoids the exponential behavior of enumerating every simple cycle in dense graphs.
    """

    if isinstance(max_witnesses, bool) or not isinstance(max_witnesses, int) or max_witnesses < 1:
        raise ValueError("max_witnesses must be an integer >= 1")

    adjacency = {
        capability_id: tuple(sorted(graph.successors(capability_id)))
        for capability_id in graph.capability_ids
    }
    cycles: list[tuple[str, ...]] = []
    for component in dependency_strongly_connected_components(graph):
        witness = _cycle_witness(component, adjacency)
        if witness is None:
            continue
        cycles.append(witness)
        if len(cycles) >= max_witnesses:
            break
    return sorted(cycles)


def satisfiable_capability_ids(
    capabilities: list[CapabilityContract],
    available_fields: list[CapabilityFieldContract],
    *,
    context: CompatibilityContext | None = None,
) -> tuple[str, ...]:
    """Return contracts whose declared requirements are satisfied by available fields.

    This is a graph/query primitive only. It does not rank, select, or execute capabilities.
    """

    available = CapabilityContract(
        capability_id="__available_state__",
        produces=list(available_fields),
    )
    result = [
        capability.capability_id
        for capability in capabilities
        if compare_capability_composition(available, capability, context=context).satisfies
    ]
    return tuple(sorted(result))
