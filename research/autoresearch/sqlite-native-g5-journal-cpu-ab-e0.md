# M1 #1560 — SQLite WAL native G5 entire index-update paired CPU E0

This research experiment extends only the SQLite source-owned journal
posting and graph opt-ins of #1677 and #1678. Synthetic CRM source,
500 and 5000 native read-only endpoint routes, GitHub Actions Linux
Python 3.12 CPU and **actual local SQLite WAL file**. Source native
schemas are authored by the research fixture, NOT an independent
provider or author-supplied task gold.

For each matched pair, mutate the original stored consumer's required
`customer_id` scalar input JSON type between `integer` (incompatible)
and `string` (compatible), inside the real SQLiteRegistry
`BEGIN IMMEDIATE` journalled transaction. Fresh-build arm runs
`NativeSchemaPostingIndex.build + NativeSchemaGraphIndex.build`;
journal arm runs `NativeSchemaGraphIndex.refresh_from_sqlite_journal`
against the prior immutable source-version snapshot. Both consume
the **same exact current SQLite source version**. Swap execution order
each iteration; compare exact SHA-256 index ID and native postings,
fingerprints, full canonical graph nodes/typed edges, source-qualified
authorization-scoped native G5 lookup, and expected 0 or 1 compatible
paths. The registrar's synthetic 500/5000 tool **initial write is
outside timed arms**; it may emit a deliberate >64-key NULL mutation
barrier, which does not affect subsequent single-tool source deltas.

GitHub Actions uploads two original JSON artifacts and reports
paired wall/process CPU p50/p95/p99, RSS, oracle parity and
journal-faster count. **Never claim** speedup until actual artifact
is available and inspected. No arbitrary production p95 threshold;
4 or 6 samples are insufficient for reliable tail confidence.
The measurement excludes SQLite initial registration, mutation
commit times, actual API query latency, concurrent live writer load,
storage durability fsync under adversarial failure, remote I/O,
model, agent, original publisher source and E2. Immutable map
copying, graph maintenance and deterministic digest still O(N).
All SQLite files must be exclusively written through audited
SQLiteRegistry API. An external table writer can forge an unsigned
journal; the measured fast path does **not** resolve this attack.

Strict K5, policy, principal visibility and availability unchanged,
#1560 and #1535 OPEN, #1346/#1477 independent external evidence
unqualified, frozen #432 negatives and v0.18 #1356 HARD HOLD.
