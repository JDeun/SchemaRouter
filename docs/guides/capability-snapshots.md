# Versioned capability graph snapshots

A capability graph snapshot pins the provider-neutral contracts and source schema revisions used to build a graph. Its SHA-256 identity is deterministic: contract/source ordering and observational build time do not affect the digest.

```python
from schemarouter import build_capability_snapshot, require_snapshot

snapshot = build_capability_snapshot(contracts, sources=source_revisions)
require_snapshot(requested_snapshot_id, snapshot)
graph = snapshot.build_graph()
```

A pinned request fails closed when the requested snapshot ID differs from the loaded graph revision. `compare_capability_snapshots()` identifies added, removed, and changed capability IDs and therefore supports controlled successor snapshots after drift.

## Immutable vs mutable state

Contracts, provider/schema revision references, and builder identity belong to the immutable snapshot. Runtime health does not: health is a mutable overlay and must be evaluated at routing time. A snapshot therefore supports reproducibility without pretending that a provider remains healthy forever. SchemaRouter does not deploy, roll back, or execute snapshots; those lifecycle decisions remain with the host.


## Atomic successor publication

Long-running processes can keep one validated snapshot and dependency graph active with `CapabilitySnapshotStore`:

```python
from schemarouter import CapabilitySnapshotStore

store = CapabilitySnapshotStore.from_contracts(
    contracts,
    sources=source_revisions,
)

current = store.read()

published = store.compare_and_publish(
    refreshed_contracts,
    sources=refreshed_source_revisions,
    expected_revision=current.publication_revision,
    expected_snapshot_id=current.snapshot.snapshot_id,
)
```

Publication uses a process-local serialized compare-and-swap boundary. The successor graph is rebuilt incrementally when the existing graph and fixed compatibility context make that safe; if incremental reconstruction cannot be proven, SchemaRouter falls back to a full graph rebuild. The complete candidate publication is validated before one atomic reference replacement.

A failed validation, stale CAS precondition, or rebuild error leaves the predecessor publication active. Readers therefore observe either the previous complete publication or the new complete publication, never an intermediate graph.

`CapabilitySnapshotPublication.provenance` records predecessor/successor snapshot IDs and source revisions. Runtime health remains outside the immutable snapshot and publication identity. Rechecking health alone therefore cannot change the snapshot digest or publication revision.
