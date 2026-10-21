# M1 #1560 — journal-gated canonical G5 native graph refresh (E0)

This is a deliberately narrow opt-in route that follows merged #1672's
source-owned in-memory semantic-posting journal fast path.

- `NativeSchemaGraphIndex.refresh_from_inmemory_journal(previous,
  registry)` requires the exact built-in `InMemoryRegistry` type,
  obtains an atomic bounded changed-key receipt, and uses the same
  source-owned posting delta method to re-index only changed native
  ToolSpecs. It rejects a foreign/SQLite/proxy source, unchanged or
  expired receipt, and a race between atomic receipt and posting
  version before returning typed paths.
- Both conservative `refresh` and journal refresh call the SAME
  native typed-contract/edge-delta assembler. The canonical existing
  `update_capability_dependency_graph` is the ONLY compatibility
  engine; changed/removed native producer/consumer nodes are
  re-derived, unchanged typed nodes and edges remain reusable.
- Actual adapter E0 tests compare journal vs fresh complete
  `NativeSchemaGraphIndex.build` for addition, consumer scalar type
  incompatibility, deletion, unrelated source mutation and transient
  insert+delete; inspect the full graph's compatibility edges,
  authorized viewer/analyst EN/KO/JA K5 response and source version.
  Negative tests deny SQLite, foreign or stale source, inject an
  inflight source mutation and fail if any unchanged ToolSpec or
  global source keys/tools are queried during journal refresh.

The exact receipt is *not* itself a principal/execution credential.
Even a graph retrieved via this path still checks live registered
source fingerprints for selected routes and current policy, data-scope
and availability during native lookup. No model is executed.

**Boundaries:** This is ONLY in-memory and E0. Copying immutable graph
contracts/posting maps, traversing canonical graph nodes/edges and
snapshot digest remain O(catalog), even if actual tool-payload
rehashing is O(delta). SQLiteRegistry's optional E0 mutation journal
PR #1673 is explicitly NOT allowed through this method. No full
typed-graph 500/5000 route p95/p99 speed claim, commercial production
or independent provider task E2. No source executor, default lexical
planner, strict K5 or experimental ranking behavior is promoted.
#1560, #1535, #1346 and #1477 open; release #1356 HARD HOLD and frozen
#432 negative unchanged.
