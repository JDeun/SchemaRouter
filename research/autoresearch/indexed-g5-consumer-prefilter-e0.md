# G5 canonical typed consumer prefilter — a measured E0 pathology

Issue [#1570](https://github.com/JDeun/SchemaRouter/issues/1570),
upstream selectivity suite [#1569](https://github.com/JDeun/SchemaRouter/pull/1569),
existing product canonical graph [#1563](https://github.com/JDeun/SchemaRouter/pull/1563).

## Source of performance defect

The same 5,108 registered-route Linux Python3.12 synthetic DEV matrix
observed 763.5113ms wall p50 in a **broad semantic output posting**
`research.label` whose 5,100 tools have NO native typed required input
dependency (3 samples). The earlier high-selectivity single-eligible
CRM case took 1.8593ms p50 (20 samples, same CI run). This is a genuine
structural G5 query cost disparity, not a statistically sound general
SLO or a publisher-independent retrieval metric.

The old G5 algorithm intersects demanded output semantic postings,
then reloads every matching ToolSpec and checks auth, availability
and output fields *before* checking whether any canonical source
dependency can reach the target. With thousands of output-only tools,
there are zero possible one-hop G5 paths but thousands of unnecessary
native model validations.

## Minimal source-safe fix

During the same `NativeSchemaGraphIndex.build`, derive an immutable
`edge_consumer_routes` frozenset from **the already-existing canonical**
`CapabilityDependencyGraph.edges`. At lookup, intersect
`field_index.postings` (complete required output group candidates)
with `edge_consumer_routes` before materializing route ToolSpecs.
If a target has no canonical compatible producer edge, it cannot form
a one-hop G5 source-evidence path, so this prefilter is safe.

There is no independently implemented alternative compatibility
engine, guessed semantic identity or new agent logic. After the
intersection, all remaining consumer AND producer original native
endpoints still undergo the same exact source fingerprint, principal,
field-data-scope, current availability and typed input/output checks.
All G5 strict K5/no-ranked-overflow semantics remain unchanged.

Tests prove the broad no-dependency posting triggers **zero** live
registry.get calls; a compatible target still reads its original
registered ToolSpec AND producer, and existing one/five/seven/denied/
unavailable synthetic comparison outcomes remain identical.

## Limits

This is only a path-specific structural optimization. It does not
promise constant-time queries with thousands of **actual graph
consumers**, independent semantic language understanding, top-K
ranking, external provider correctness or safe execution authority.
External publisher-owned #1346 and paired agent E2 #1477 remain
gates; frozen #432 and v0.18 #1356 HOLD unchanged.


## First measured Linux after-fix observation (not paired on one host)

On head `d6026e0e7eeb5b93d23f573a734e320851d1be7a`,
dedicated GitHub Actions run `39174031188`, job `117812877351`,
Python 3.12.15, Linux Azure, 5,108 registered synthetic routes:

| Case | Before PR #1569 | With canonical prefilter |
|---|---:|---:|
| Broad 5,100 postings with zero dependency paths: wall p50 | 763.5113ms | 0.3899ms |
| Narrow one eligible path: wall p50 | 1.8593ms | 1.8403ms |
| Five eligible paths: wall p50 | 2.9070ms | 2.8953ms |
| Seven eligible paths: result | over_k_unranked | over_k_unranked |

`44 pytest passed`, Ruff passed, Pyright zero errors. Benchmark
matrix verified source-scoped hidden/denied/unavailable results and
K5 overflow remained unchanged. Index build wall in the after-fix
runner was 1,441.2340ms; one-process peak RSS 108,256 KiB.

**Critical interpretation:** these are DIFFERENT Actions jobs/machine
allocations and only three broad-posting timed calls per job, not
a paired, randomized, steady-state workload with confidence intervals.
The fast improvement has a strong structural explanation (zero
unnecessary registry.get reads) but must NOT be promoted to an
independent provider workload p99 guarantee or claimed universally
as a reliable numerical speedup factor.


## Same-process structural AB (stronger diagnostic; still synthetic)

Dedicated CI run `39174307759`, job `117813698438`, Python3.12.15,
Linux Azure, 5,102 registered routes and 5,100 unrelated common output
semantic postings. It ran the SAME exact G5 source-index/canonical
graph, router/principal and `NativeSchemaGraphIndex.lookup` logic in
alternating AB order, changing ONLY the G5 structural target prefilter:
the benchmark-only disabled condition uses a **superset of every registered
route**, while the enabled condition uses canonical graph edge consumers.

| Paired same-process condition | Wall p50 | Wall p95 | Wall p99 |
|---|---:|---:|---:|
| Canonical consumer prefilter disabled | 955.2751ms | 960.8975ms | 960.8975ms |
| Canonical consumer prefilter enabled | 0.3999ms | 0.4678ms | 0.4678ms |

Two full warm-up AB cycles were excluded; **5 measured AB cycles** were
alternated to reduce fixed invocation order bias. Both returned the
same empty `no_proven_hit` result. The disabled-superset experiment is
a benchmark-only `dataclasses.replace` view, not a new alternate
production retrieval engine. 52 focused pytest cases, Ruff and
Pyright 0 errors all passed.

This stronger same-process causal test demonstrates the expected
dramatic reduction for output-only false-positive postings. Nevertheless,
five samples and one synthetic benchmark workload are insufficient to
establish a representative p99, universal speedup or SLO.
