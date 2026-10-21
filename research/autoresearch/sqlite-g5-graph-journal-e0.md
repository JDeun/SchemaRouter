# #1560 — SQLite-owned one-hop G5 journal graph edge delta E0

This stacked experiment requires #1677’s native SQLite semantic-posting
journal opt-in and merged #1675’s canonical in-memory graph delta.
The new `NativeSchemaGraphIndex.refresh_from_sqlite_journal(previous,
registry)` accepts **only exact built-in SQLiteRegistry**, no custom
registry proxy or arbitrary data adapter. It reads the atomic,
version-bounded and source-owned SQLite mutation receipt, uses the
exact source SQLite posting journal delta and the shared canonical
`update_capability_dependency_graph` typed compatibility update.
It re-reads changed native ToolSpecs only, not all registered schemas.
The endpoint/source fingerprints, source version and original policy,
principal, FieldGroup, data-scope, availability and K5 restrictions
are revalidated along the original read/lookup path.

SQLite-file actual E0 tests compare against *fresh* complete original
posting + graph rebuild for a real scalar input type incompatibility,
native metadata change, tool addition, deletion and ephemeral
add/delete. Verify typed graph nodes and complete edges, original
source snapshot digest, qualified path counts, scoped lookup and
cross-connection journal receipt. Strict spies forbid unchanged
ToolSpec, registry-wide `keys` or `tools` scans. Negative cases
test foreign/no-op source, another SQLite connection mutating source
during delta, and malformed journal rows.

**Security boundary and limits:** the SQLite file must be exclusively
written through the audited built-in SQLiteRegistry API. Possession
of arbitrary write permission on SQLite tables permits coherent
journal forgery; no cryptographic authentication or protected
publisher audit ledger is provided. Do **not** enable this E0
experiment for DB files with external/manual writers. Any changed
source version during copy-on-write assembly fails closed and
requires a full build. Returned candidate paths still require
current principal authorization, field scope and availability.

No default production switch, no paired 500/5000 full graph CPU
p50/p95/p99 for SQLite, no asynchronous multi-host cursor guarantee,
no independence/provider-native gold or true agent E2. No native tool
execution or model request is performed. #1560/#1535 still OPEN,
frozen #432 negative unchanged, #1356 release HARD HOLD.
