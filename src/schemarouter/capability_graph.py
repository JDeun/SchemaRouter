from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from pydantic import PrivateAttr

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
    edges: tuple[CapabilityDependencyEdge, ...] = ()

    _successors_by_id: dict[str, tuple[str, ...]] = PrivateAttr(default_factory=dict)
    _predecessors_by_id: dict[str, tuple[str, ...]] = PrivateAttr(default_factory=dict)

    def model_post_init(self, __context: Any) -> None:
        del __context
        self._rebuild_adjacency_indexes()

    def __setattr__(self, name: str, value: Any) -> None:
        super().__setattr__(name, value)
        if (
            name in {"capability_ids", "edges"}
            and "capability_ids" in self.__dict__
            and "edges" in self.__dict__
        ):
            self._rebuild_adjacency_indexes()

    def model_copy(
        self,
        *,
        update: Mapping[str, Any] | None = None,
        deep: bool = False,
    ) -> CapabilityDependencyGraph:
        copied = super().model_copy(update=update, deep=deep)
        copied._rebuild_adjacency_indexes()
        return copied

    def _rebuild_adjacency_indexes(self) -> None:
        successors: dict[str, list[str]] = {
            capability_id: []
            for capability_id in self.capability_ids
        }
        predecessors: dict[str, list[str]] = {
            capability_id: []
            for capability_id in self.capability_ids
        }
        for edge in self.edges:
            successors.setdefault(edge.producer_id, []).append(edge.consumer_id)
            predecessors.setdefault(edge.consumer_id, []).append(edge.producer_id)

        self._successors_by_id = {
            capability_id: tuple(values)
            for capability_id, values in successors.items()
        }
        self._predecessors_by_id = {
            capability_id: tuple(values)
            for capability_id, values in predecessors.items()
        }

    def successors(self, capability_id: str) -> tuple[str, ...]:
        return self._successors_by_id.get(capability_id, ())

    def predecessors(self, capability_id: str) -> tuple[str, ...]:
        return self._predecessors_by_id.get(capability_id, ())


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
        edges=tuple(edges),
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
            edges=tuple(
                sorted(
                    graph.edges,
                    key=lambda edge: (edge.producer_id, edge.consumer_id),
                )
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
        edges=tuple(
            edge_by_pair[pair]
            for pair in sorted(edge_by_pair)
        ),
    )
