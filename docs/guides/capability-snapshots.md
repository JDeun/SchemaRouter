# Versioned capability graph snapshots

A capability graph snapshot captures immutable routing-contract state separately from mutable runtime health.

```python
from schemarouter import create_capability_graph_snapshot, require_capability_snapshot

snapshot = create_capability_graph_snapshot(
    graph,
    contracts,
    source_schema_fingerprints={"provider": "..."},
    build_metadata={"builder": "ci"},
)
require_capability_snapshot(snapshot, requested_snapshot_id)
```

The snapshot ID is a SHA-256 digest of canonical graph, contract, and source-schema fingerprint data. Capability and edge order are normalized. Informational build metadata is retained but excluded from identity, so the same routing contract compiled in different environments remains reproducible.

`compare_capability_snapshots()` reports added, removed, and changed capability IDs. A host can pin retrieval/runtime work to an exact snapshot with `require_capability_snapshot()`, which fails closed on mismatch.

Live provider health is deliberately excluded. A snapshot records what the routing contract was, not whether a provider is healthy now. SchemaRouter does not deploy, roll back, execute, or silently accept stale breaking schemas; those lifecycle decisions remain with the host.
