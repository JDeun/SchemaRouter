from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from threading import RLock
from typing import Literal

from .capability_contracts import (
    CapabilityContract,
    CompatibilityContext,
    compare_capability_composition,
)
from .capability_drift import CapabilityGraphDrift, compare_capability_graph_snapshot
from .capability_graph import (
    CapabilityDependencyGraph,
    build_capability_dependency_graph,
    update_capability_dependency_graph,
)
from .capability_snapshot import (
    CapabilityGraphSnapshot,
    CapabilitySourceRevision,
    build_capability_snapshot,
)
from .models import StrictModel

CapabilityRebuildMode = Literal[
    "initial",
    "unchanged",
    "source_only",
    "incremental",
    "full",
]


class CapabilityPublicationConflictError(RuntimeError):
    """Raised when a compare-and-swap publication precondition is stale."""


class CapabilitySnapshotProvenance(StrictModel):
    predecessor_snapshot_id: str | None = None
    successor_snapshot_id: str
    source_revisions: tuple[CapabilitySourceRevision, ...] = ()


class CapabilitySnapshotPublication(StrictModel):
    publication_revision: int
    snapshot: CapabilityGraphSnapshot
    graph: CapabilityDependencyGraph
    rebuild_mode: CapabilityRebuildMode
    provenance: CapabilitySnapshotProvenance
    drift: CapabilityGraphDrift | None = None


PublicationValidator = Callable[[CapabilitySnapshotPublication], None]


def _source_identity(revision: CapabilitySourceRevision) -> tuple[str, str]:
    return revision.provider, revision.access_method or ""


def _validate_source_revisions(
    sources: tuple[CapabilitySourceRevision, ...] | list[CapabilitySourceRevision],
) -> None:
    identities = [_source_identity(item) for item in sources]
    if len(identities) != len(set(identities)):
        raise ValueError(
            "capability source revisions must have unique provider/access_method identities"
        )


def validate_capability_publication(
    publication: CapabilitySnapshotPublication,
    *,
    context: CompatibilityContext | None = None,
) -> None:
    """Validate graph/snapshot integrity without executing capabilities."""

    snapshot = publication.snapshot
    graph = publication.graph
    snapshot_context = snapshot.compatibility_context
    if context is not None and context != snapshot_context:
        raise ValueError(
            "publication compatibility context does not match snapshot semantics"
        )
    effective_context = snapshot_context
    contract_ids = tuple(item.capability_id for item in snapshot.contracts)
    if len(contract_ids) != len(set(contract_ids)):
        raise ValueError("capability snapshot contains duplicate capability IDs")
    if tuple(sorted(contract_ids)) != tuple(sorted(graph.capability_ids)):
        raise ValueError("published graph capability IDs do not match snapshot contracts")

    _validate_source_revisions(snapshot.sources)

    edge_pairs = [
        (edge.producer_id, edge.consumer_id)
        for edge in graph.edges
    ]
    if len(edge_pairs) != len(set(edge_pairs)):
        raise ValueError("published graph contains duplicate dependency edges")

    known_ids = set(contract_ids)
    by_id = {item.capability_id: item for item in snapshot.contracts}
    for edge in graph.edges:
        if edge.producer_id not in known_ids or edge.consumer_id not in known_ids:
            raise ValueError("published graph contains an edge to an unknown capability")
        if edge.producer_id == edge.consumer_id:
            raise ValueError("published graph must not contain self dependency edges")
        expected = compare_capability_composition(
            by_id[edge.producer_id],
            by_id[edge.consumer_id],
            context=effective_context,
        )
        if not expected.satisfies or expected != edge.compatibility:
            raise ValueError(
                "published graph edge does not match declared capability compatibility"
            )

    if publication.provenance.successor_snapshot_id != snapshot.snapshot_id:
        raise ValueError("publication provenance successor does not match snapshot ID")
    if publication.provenance.source_revisions != snapshot.sources:
        raise ValueError("publication provenance sources do not match snapshot sources")
    if publication.publication_revision < 1:
        raise ValueError("publication_revision must be >= 1")


class CapabilitySnapshotStore:
    """Atomic in-process publication of validated immutable capability snapshots.

    The store serializes writers with a process-local lock and supports explicit CAS
    preconditions. Readers receive a deep copy of one complete publication, never a
    partially rebuilt graph. Runtime health is intentionally outside this store.
    """

    def __init__(
        self,
        snapshot: CapabilityGraphSnapshot,
        *,
        graph: CapabilityDependencyGraph | None = None,
        context: CompatibilityContext | None = None,
        validator: PublicationValidator | None = None,
    ) -> None:
        self._lock = RLock()
        if context is not None and context != snapshot.compatibility_context:
            raise ValueError(
                "store compatibility context must be embedded in the supplied snapshot"
            )
        self._context = (
            snapshot.compatibility_context.model_copy(deep=True)
            if snapshot.compatibility_context is not None
            else None
        )
        self._validator = validator

        _validate_source_revisions(snapshot.sources)
        expected_graph = build_capability_dependency_graph(
            list(snapshot.contracts),
            context=self._context,
        )
        if graph is not None and graph != expected_graph:
            raise ValueError(
                "initial capability graph does not match the supplied snapshot contracts"
            )
        initial_graph = graph or expected_graph
        publication = CapabilitySnapshotPublication(
            publication_revision=1,
            snapshot=snapshot.model_copy(deep=True),
            graph=initial_graph.model_copy(deep=True),
            rebuild_mode="initial",
            provenance=CapabilitySnapshotProvenance(
                predecessor_snapshot_id=None,
                successor_snapshot_id=snapshot.snapshot_id,
                source_revisions=tuple(
                    item.model_copy(deep=True)
                    for item in snapshot.sources
                ),
            ),
        )
        self._validate(publication)
        self._publication = publication

    @classmethod
    def from_contracts(
        cls,
        contracts: list[CapabilityContract],
        *,
        sources: list[CapabilitySourceRevision] | None = None,
        builder_version: str | None = None,
        built_at: datetime | None = None,
        context: CompatibilityContext | None = None,
        validator: PublicationValidator | None = None,
    ) -> CapabilitySnapshotStore:
        snapshot = build_capability_snapshot(
            contracts,
            sources=sources,
            builder_version=builder_version,
            built_at=built_at,
            context=context,
        )
        return cls(
            snapshot,
            context=context,
            validator=validator,
        )

    def _validate(self, publication: CapabilitySnapshotPublication) -> None:
        validate_capability_publication(
            publication,
            context=self._context,
        )
        if self._validator is not None:
            self._validator(publication.model_copy(deep=True))

    def read(self) -> CapabilitySnapshotPublication:
        with self._lock:
            return self._publication.model_copy(deep=True)

    @property
    def publication_revision(self) -> int:
        with self._lock:
            return self._publication.publication_revision

    @property
    def snapshot_id(self) -> str:
        with self._lock:
            return self._publication.snapshot.snapshot_id

    def compare_and_publish(
        self,
        contracts: list[CapabilityContract],
        *,
        sources: list[CapabilitySourceRevision] | None = None,
        builder_version: str | None = None,
        built_at: datetime | None = None,
        expected_revision: int | None = None,
        expected_snapshot_id: str | None = None,
        force_full_rebuild: bool = False,
    ) -> CapabilitySnapshotPublication:
        """Build, validate, and atomically publish a successor snapshot.

        Any exception before the final assignment leaves the predecessor publication
        active. The compatibility context is fixed for the lifetime of the store, so an
        incremental graph update cannot silently change semantic-equivalence policy.
        """

        with self._lock:
            current = self._publication
            if (
                expected_revision is not None
                and expected_revision != current.publication_revision
            ):
                raise CapabilityPublicationConflictError(
                    "capability publication revision changed before compare-and-swap"
                )
            if (
                expected_snapshot_id is not None
                and expected_snapshot_id != current.snapshot.snapshot_id
            ):
                raise CapabilityPublicationConflictError(
                    "capability snapshot changed before compare-and-swap"
                )

            source_items = (
                [item.model_copy(deep=True) for item in sources]
                if sources is not None
                else [item.model_copy(deep=True) for item in current.snapshot.sources]
            )
            _validate_source_revisions(source_items)
            next_builder_version = (
                builder_version
                if builder_version is not None
                else current.snapshot.builder_version
            )
            successor = build_capability_snapshot(
                contracts,
                sources=source_items,
                builder_version=next_builder_version,
                built_at=built_at,
                context=self._context,
            )

            if successor.snapshot_id == current.snapshot.snapshot_id:
                return current.model_copy(
                    deep=True,
                    update={"rebuild_mode": "unchanged"},
                )

            old_contracts = list(current.snapshot.contracts)
            new_contracts = list(successor.contracts)
            drift = compare_capability_graph_snapshot(
                current.graph,
                old_contracts,
                new_contracts,
            )

            contracts_unchanged = old_contracts == new_contracts
            if contracts_unchanged:
                next_graph = current.graph.model_copy(deep=True)
                rebuild_mode: CapabilityRebuildMode = "source_only"
            elif force_full_rebuild:
                next_graph = build_capability_dependency_graph(
                    new_contracts,
                    context=self._context,
                )
                rebuild_mode = "full"
            else:
                try:
                    next_graph = update_capability_dependency_graph(
                        current.graph,
                        old_contracts,
                        new_contracts,
                        context=self._context,
                    )
                    rebuild_mode = "incremental"
                except (TypeError, ValueError):
                    next_graph = build_capability_dependency_graph(
                        new_contracts,
                        context=self._context,
                    )
                    rebuild_mode = "full"

            publication = CapabilitySnapshotPublication(
                publication_revision=current.publication_revision + 1,
                snapshot=successor,
                graph=next_graph,
                rebuild_mode=rebuild_mode,
                provenance=CapabilitySnapshotProvenance(
                    predecessor_snapshot_id=current.snapshot.snapshot_id,
                    successor_snapshot_id=successor.snapshot_id,
                    source_revisions=tuple(
                        item.model_copy(deep=True)
                        for item in successor.sources
                    ),
                ),
                drift=drift,
            )
            self._validate(publication)

            # This single reference replacement is the publication boundary.
            self._publication = publication
            return publication.model_copy(deep=True)
