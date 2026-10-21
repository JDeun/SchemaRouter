# #1560 — Paired native posting full rebuild vs atomic journal delta E0

Developer-authored, provider-free schema catalog: 500 and 5000 native routes,
exact **InMemoryRegistry** on GitHub Actions Linux CPU. Fixed native typed
CRM producer/consumer plus unrelated synthetic ToolSpecs. After each
metadata-only native tool mutation, both variants read the **same source
registry version**. The old immutable posting index and the registry-owned
atomic version/changed-key receipt are used for journal delta. Compare the
entire SHA-256 index ID, routes, native fingerprints, postings and locations
against an independent `NativeSchemaPostingIndex.build` of that same source
version. The compared route cardinality is unchanged across paired samples.

The order alternates full build first/delta first. Collect separate wall
and process CPU sample arrays, report their p50/p95/p99 and count delta-faster
pairs, peak process RSS and exact-index-oracle success. CI uploads both JSON
reports for audit; no hidden qualitative scoring or automatically tuned
threshold. Results are **observational**, and no speedup is presumed.

Critically, this is **ONLY semantic-posting UPDATE cost**. It does not
time or prove the principal/policy/availability checked G5 query path, graph
edge delta refresh (which still scans all source fingerprints), original
provider native tools, agent execution, commercial p95/p99 or independence.
Copying index maps and recomputing the deterministic SHA-256 index receipt
is still O(all catalog routes). CPU run sizes and 4/6 samples are not
a production service latency distribution. Frozen #432 original negative,
#1346 independent gold blocker, #1477 E2 blocker, #1535 and #1560
acceptance and #1356 v0.18 release HARD HOLD stay unchanged.
