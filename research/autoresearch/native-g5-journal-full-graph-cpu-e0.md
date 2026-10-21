# #1560 — Full native G5 graph index paired update CPU (E0)

Synthetic controlled 500 and 5000 source-native ToolSpec/endpoint routes
on GitHub Actions Ubuntu Linux 3.12 CPU. Paired per-source-version
measurement compares an independently fresh
`NativeSchemaPostingIndex.build + NativeSchemaGraphIndex.build` against
the original-source-authoritative `NativeSchemaGraphIndex.
refresh_from_inmemory_journal` introduced by #1675.

Unlike the earlier #1674 posting-only experiment, BOTH arms include
canonical typed capability dependency graph edge building/updating.
Every pair toggles the original consumer input JSON type between
`string` (compatible with producer ID) and `integer` (incompatible).
The read-only, authorized native G5 synthetic query must return the
identical structural result in both arms, with exactly one eligible
path for compatible samples and zero for incompatible samples.
Exact source version, snapshot SHA-256, semantic postings, route
fingerprints, graph node sets/edges, counts and scoped G5 responses
are checked for every matched trial. Execution order alternates.
Record wall/process CPU p50/p95/p99, faster-pair count, RSS and Python
version; upload original immutable JSON as CI artifact.

**Excluded**: original publisher case/gold or data, hosted production
routing, concurrent write workload, HTTP/I/O, network, independent
agent/tool execution, Qwen3/E5 inference, native final-answer E2, SLA,
support/no-fit accuracy calibration. 4 or 6 synthetic CPU samples do
not establish reliable p95 or p99 tail latency. Existing immutable
source contract collection, graph node/edge materialization, posting
snapshot-map copies and digest remain dependent on catalog size;
any observed speedup is conditional on the exact synthetic workload.
No claim of 5000-route commercial readiness or v0.18 qualification.
#1560 and #1535 stay OPEN; frozen #432 negative and release HARD HOLD
#1356 remain unchanged.
