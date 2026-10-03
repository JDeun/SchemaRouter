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
