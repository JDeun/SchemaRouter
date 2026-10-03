# Capability graph drift

SchemaRouter can compare a previously compiled capability-contract snapshot with a refreshed snapshot and identify which capability graph nodes need recompilation.

```python
from schemarouter import compare_capability_graph_snapshot

report = compare_capability_graph_snapshot(graph, previous_contracts, refreshed_contracts)
if report.changed:
    print(report.compatibility)
    print(report.invalidated_capability_ids)
```

The comparison is deterministic. Capability contract fingerprints are SHA-256 digests of canonical JSON, so mapping insertion order does not change the fingerprint.

## Invalidation boundary

A changed or removed contract is breaking and invalidates that capability plus its existing immediate graph predecessors and successors. Those incident edges are the compatibility decisions that may have become stale. A newly added capability is compatible additive drift and invalidates only the new node so a host/compiler can calculate its new edges.

This API produces **invalidation metadata only**. It does not execute a capability, migrate an invocation, widen authorization, or replace the host's execution policy. The host decides when to refresh provider schemas, rebuild affected graph nodes, and deploy a refreshed graph.

Provider-level OpenAPI, MCP, or scientific-provider schema changes should first be normalized into the existing ToolSpec/schema-diff layer. Capability graph drift then compares the provider-neutral capability contracts produced from those refreshed schemas. Runtime health remains a separate overlay and is not part of the deterministic contract fingerprint.
