"""Standalone capability-graph diagnostics retained for checkout-only research."""

from __future__ import annotations

from schemarouter.capability_contracts import (
    CapabilityContract,
    CapabilityFieldContract,
    CompatibilityContext,
    compare_capability_composition,
)
from schemarouter.capability_graph import CapabilityDependencyGraph


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
