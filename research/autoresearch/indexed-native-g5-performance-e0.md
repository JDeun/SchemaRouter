# G5 full-catalog E0 CPU/RSS profile and availability guards

Issue [#1564](https://github.com/JDeun/SchemaRouter/issues/1564).
Original product index [#1560](https://github.com/JDeun/SchemaRouter/issues/1560);
one-hop integrated G5 [#1563](https://github.com/JDeun/SchemaRouter/pull/1563).

## What is implemented

`scripts/benchmark_indexed_native_graph_g5_cpu_e0.py` creates 2
one-hop-compatible source-native registered ToolSpecs and **5,100
irrelevant registered native ToolSpecs** in one process, then builds
`NativeSchemaPostingIndex` and `NativeSchemaGraphIndex` once. It
verifies exactly one matching source→consumer graph candidate with
strict K5. Five prewarm queries are excluded. The CPU profile
uses a bounded number of repeated real index queries and reports
build-wall duration, per-query wall p50/p95/p99/mean, process CPU
p50/p95/p99 and Linux `ru_maxrss` in KiB. Report includes Python
and host platform; raw tool IDs/credentials/prompts/values are excluded.

The existing `_retrieval_authority_witness` already prevents `G5`
and its supporting field index from returning candidates when the
**availability predicate callable changes during lookup**. New negative
regressions verify this existing fail-closed guard. No duplicate
availability-check implementation is introduced. This is **not** a guarantee
against a malicious stateful availability callback changing its own
answer without changing identity or an external provider changing
real-world state between lookup and tool execution.

## Evidence boundary

All output is `E0_SYNTHETIC_CPU_NOT_INDEPENDENT`: tool catalog, concept,
query and expected one-hop match are developer-authored for sanity
and reproducibility. It does **not** measure independent Recall@5,
confidence intervals, multilingual model understanding, external
provider latency, actual agent task success, or quality ranked Top-K5
under many matching candidates. No default retrieval or execution
code is changed.

Do not compare CI runner wall time with an independently unpaired
provider/model run or promote a single benchmark observation to a
production SLO. Machine load, repeated runs, declared traffic
distribution, memory allocations and schema churn must be measured
separately before production claims.

Maintain original #432 negative result and v0.18 #1356 release HOLD,
and continue #1346 independent publisher-native gold / #1477 E2.
