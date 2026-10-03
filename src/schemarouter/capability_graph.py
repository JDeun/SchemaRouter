from __future__ import annotations

from pydantic import Field

from .capability_contracts import (
    CapabilityComposition,
    CapabilityContract,
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


def build_capability_dependency_graph(
    capabilities: list[CapabilityContract],
    *,
    context: CompatibilityContext | None = None,
) -> CapabilityDependencyGraph:
    """Build contract-compatible edges; this does not choose or execute a workflow."""

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
                edges.append(CapabilityDependencyEdge(
                    producer_id=producer.capability_id,
                    consumer_id=consumer.capability_id,
                    compatibility=compatibility,
                ))

    return CapabilityDependencyGraph(
        capability_ids=tuple(ids),
        edges=edges,
    )


def dependency_cycles(graph: CapabilityDependencyGraph) -> list[tuple[str, ...]]:
    """Return deterministic simple cycle witnesses without planning around them."""

    adjacency = {
        capability_id: graph.successors(capability_id)
        for capability_id in graph.capability_ids
    }
    cycles: set[tuple[str, ...]] = set()

    def visit(start: str, current: str, path: tuple[str, ...]) -> None:
        for next_id in adjacency.get(current, ()):
            if next_id == start:
                cycle = path
                rotations = [cycle[index:] + cycle[:index] for index in range(len(cycle))]
                cycles.add(min(rotations))
            elif next_id not in path:
                visit(start, next_id, path + (next_id,))

    for capability_id in graph.capability_ids:
        visit(capability_id, capability_id, (capability_id,))
    return sorted(cycles)


def satisfiable_capability_ids(
    capabilities: list[CapabilityContract],
    available_fields: list,
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
