# M1 #1560 — research-only original SQLite G5 typed graph journal delta (E0)

**Stacked on #1677 source-verified SQLite semantic posting delta**, rather
than promoting any unknown SQLite database or user-supplied changed-key hint.

`NativeSchemaGraphIndex.refresh_from_sqlite_journal` is explicitly
opt-in and accepts the **exact built-in SQLiteRegistry** type only. It
reads the source-owned bounded SQLite version/changed-tool-key receipt,
calls the original source-scoped `NativeSchemaPostingIndex.
refresh_from_sqlite_journal`, and reuses the single canonical typed
`_refresh_changed_contracts` and `update_capability_dependency_graph`
for only incident edges. The result must match complete
`NativeSchemaPostingIndex.build` plus
`NativeSchemaGraphIndex.build` for full source fingerprints,
snapshot digest, producer/consumer graph and authorized/no-access native
G5 query results.

Negative E0 tests include corrupt/missing source history, more than
64 changed tool keys, unknown/foreign source and injected real
cross-SQLite-connection write during changed-only tool access. Graph
provenance spies forbid full `keys()`/`tools()` and untouched
`get()`. Real input-type incompatibility produces zero native paths;
a compatible native scalar join restores exactly one. This method does
not alter lexical default, query-time current source/policy/RBAC/data
scope/availability verification or run source endpoints.

**Security and correctness boundary:** This is **not** a
cryptographically authenticated change journal. Any local actor with
direct write access to the SQLite tool/meta/journal tables can forge a
complete-looking receipt; no trusted file ownership gate or audit
signature is established here. Do not use on externally mutable
SQLite files. The current API is opt-in E0 only. Concurrent mutations
detected by source-version checks fail closed; there is no
cross-process exactly-once writer/reader execution transaction.
Benchmark #1676 was synthetic in-memory, not SQLite, so no proven
SQLite 500/5000 p95/p99 or commercial throughput claim is supported.
Provider-native task gold and independent agent E2 are not established,
and #1560/#1535 remain OPEN with v0.18 #1356 HARD HOLD and frozen
#432 negative accuracy.
