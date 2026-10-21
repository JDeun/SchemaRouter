# #1560 — Verified copy-on-write native semantic posting refresh (E0)

2026-10-21 engineering-only incremental update slice. **Not a production
incremental graph engine, speedup claim, independent relevance/E2, or default
model promotion.**

- Source: `NativeSchemaPostingIndex.build` retains the exact native
  tool fingerprint manifest (including registered tools with no endpoints)
  alongside its immutable scalar semantic posting map and route revisions.
- New **opt-in** `NativeSchemaPostingIndex.refresh(previous, registry,
  changed_tool_keys=(...))` copies the old indexed postings, removes
  source routes for changed/deleted tool keys, and indexes ONLY those
  named changed native tool contracts. It produces the **same SHA-256
  snapshot ID, source revision, postings, route fingerprints and locations**
  as a fresh full `build` of the same stable registry.
- **Changed key hints are untrusted.** To prevent missed or false
  additions/deletions, it enumerates the current key manifest and verifies
  every unchanged tool's complete original fingerprint before publishing a
  new immutable index. Missing hinted changes, impossible keys, an alien
  registry, mismatched keys, concurrent version drift and malformed change
  sets fail closed. It never returns privileged field evidence itself; the
  existing principal/data-scope/availability checks remain in `lookup`.
- Offline no-model E0 tests compare exact refreshed and full-rebuild
  snapshots plus EN/KO/JA analyst/viewer query results after add, replace,
  remove and mixed atomic batch update. Negative tests inject omitted
  changed tool, runtime mutation during manifest enumeration, stale and
  foreign registry, malformed hints. No network, provider, source executor,
  query gold or agent invocation.

## Unsolved engineering requirements

This is a safe **posting-only refresh**, not `NativeSchemaGraphIndex`
incremental adjacency rebuild. It still requires **O(all registered
tools)** fingerprint verification at update time. There is NO atomic
registry change journal to support a truly bounded delta cost, no
constant-time 5000-route churn target, and no new p95/p99 latency
claim. Graph index callers must currently rebuild typed edges from
the refreshed posting index via `NativeSchemaGraphIndex.build`. A future
registry-owned versioned mutation receipt/journal must be reviewed for
atomic batch semantics and SQLite persistence before removing the
full-fingerprint verification. Query-time full-catalog scans remain
forbidden. This E0 does not unblock publisher-independent #1346,
paired actual agent #1477, multilingual no-fit #1339, or the v0.18
release HARD HOLD #1356. Frozen #432 negative remains unchanged.
