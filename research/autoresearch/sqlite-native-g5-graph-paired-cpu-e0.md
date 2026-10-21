# #1560 — paired real SQLite native G5 index + typed graph CPU E0

This study uses **real SQLite WAL storage and transaction-owned source
journal** with a developer-generated native ToolSpec catalog. It is
explicitly stacked on the unmerged SQLite posting and canonical graph
opt-in research PRs #1677 and #1678. It does not enable them by default.

Compare per exact SQLite source version (A) full semantic posting build
plus canonical typed graph rebuild and (B) SQLite mutation-receipt
posting refresh plus canonical incident-edge graph delta. Each pair
alternates native consumer input type `string` ↔ `integer` to test
true compatible and no-fit native joins, and alternates execution order.
Compare complete snapshot SHA-256, route and tool fingerprints, postings,
graph nodes/edges, typed source count, and independently looked-up
principal-scoped K5 result. Source seed and tool write are not timed.
Report wall/process CPU p50/p95/p99, faster paired samples, peak RSS,
Python version and exact oracle success, retaining 500/5000 route
source-matched JSON artifacts from Linux GitHub Actions.

**Excluded:** original independently published provider contracts or
task gold, Qwen/E5/agent execution, network, concurrent-writer
performance, real user HTTP p95, sustained service throughput,
cross-process exactly-once transactions and production SLA. SQLite is
trusted ONLY when exclusively modified via the built-in registry APIs:
a separate actor with direct table-write privileges can forge journals.
Four or six E0 samples cannot support production p95/p99 accuracy. Full
source snapshot copies and canonical graph materialization still scale
with catalog size.

No issue closure from this E0 result: #1560, #1535, publisher-native
#1346 and real agent E2 #1477 remain open; frozen #432 negative
assessment and v0.18 release #1356 HARD HOLD unchanged.
