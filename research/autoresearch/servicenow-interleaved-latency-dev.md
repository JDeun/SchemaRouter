# ServiceNow interleaved request-latency DEV — issue #1228

**Evidence role: source-pinned development only, not independently authored
held-out queries, tool execution, operational safety or agent task success.**

This additive experiment does not edit or replay gold labels to tune the product.
It retains the original 24 public development questions (20 supported, four
unsupported), the originally pinned **12 real, publisher-authored readonly MCP
tools/list contracts**, and their separately pinned native SHA-256. Source:
Xerrion/servicenow-platform-mcp at commit
5bcb83b29ab5b30aee07cabaa8df974881c47126. Native package is actual
readonly; no ServiceNow tenant, credentials, model, writes, or live tool calls.

The original scorer reported **p95 across 24 per-case median timings**. That
is *not* request-level p95; the maintainer identified the distinction before
the freeze. This supplementary comparison predeclares 20 warmed repetitions
per case with three arms and seed **20261016**. Each repetition shuffles case
order using the seeded Python PRNG, then cyclically rotates the order of:

1. the full 12-tool static readonly baseline;
2. SchemaRouter retrieval with K=3, the historical secondary DEV budget;
3. SchemaRouter retrieval with K=5, the maintainer-preferred primary budget.

Each timed sample covers **local selection plus exact native tool-contract
canonical JSON serialization**; there is no inference or tool execution.
The index build and initial per-query warmups are excluded from timings and
documented separately. This isolates steady-state preselection overhead; it
is **not** network or agent end-to-end latency.

The raw record contains arm, case ID, repetition index, order, measured
duration, exact source-native selected tool IDs, canonical contract digest,
and visible schema bytes. Validation enforces exact schedule identity,
1,440 total samples, no invalid or nonfinite timings, valid native route
identities, contract SHA-256, and each arm's declared width.

The report distinguishes:
- request_p50_ms and request_p95_ms: percentiles over 480 **individual
  measured requests per arm**, with linear interpolation of sorted samples.
- p95_of_per_case_medians_ms_not_request_p95: historical-style aggregation
  for comparison only, never a production SLO.
- Required-tool and **native input-parameter availability** recall, unsupported
  **nonempty candidate exposure**, context schema size, and tool counts.
  Field availability is not actual model argument extraction or output-field
  selection. Nonempty unsupported retrieval is not unauthorized execution and
  is not calibrated no-fit false acceptance.

Original DEV misses (sn-dev-006, sn-dev-007, sn-dev-015 at K=5) and
negative cases remain unchanged. This is reproducible instrumentation,
**not** independent confirmation, E2 completion, commercial SLA, or release
approval. Maintainer review, disjoint frozen test tasks, and runtime input
constraint checks are still required. Keep #1228/#1346 OPEN and held
v0.18.0 PR #1356 UNMERGED.
