# Paired quality-conditioned candidate exposure (E0)

Recorded 2026-10-24, before measuring the new paired qualification metrics.
Ownership: existing [#1560](https://github.com/JDeun/SchemaRouter/issues/1560)
and the [research program](../../docs/research/research-program-2026.md).
This is a **pre-agent analysis of existing synthetic 20/50/100/250/500-route
fixtures**, not an independent E2 run or model study.

## Why a new metric, not another router

The existing frozen [realistic break-even matrix](../../docs/research/realistic-break-even-result.md)
already measures 20/50/100/250/500 × low/medium/high ambiguity, schema-aware
lexical and current indexed default quality/CPU p50/p95 and mean selected
contract bytes. Another name/keyword index would duplicate it.

This independent additive report measures **paired per-query route-hit
agreements and disagreements**, including no-fit, plus serialized schema
contract bytes **only on supported cases where BOTH methods retrieved the
known required route**. Otherwise a retrieval method could look cheaper
by simply dropping the relevant tool. All default product/runtime
paths and prior benchmark outputs remain unchanged.

## Preregistered arms and metrics

Frozen exact existing generator: `scripts/benchmark_realistic_break_even.py`.
Fixed K=5 for both `schema_lexical_k5` and `indexed_default_k5`,
same source catalog, query and permitted field evidence, no tool invoker or
agent. Collect by stratum: supported case count, both correct required route
hit, only lexical hit, only indexed hit, neither hit, both/no-fit asymmetries,
full-catalog serialized contract bytes, all-case mean selected bytes, plus
shared-correct-supported mean contract bytes and per-case cheaper/equal count.

**Critical classification:** `indexed_default_k5` uses the **ordinary
indexed lexical+typed SchemaRouter planner, NOT the opt-in G5 native typed
concept graph**. Do not call a favorable result a causal graph win.
The schema-aware lexical method receives case-declared semantic field
constraints from the fixture, so it is a deliberately strong comparator
rather than naive BM25 keyword name matching.

Serialized Python/JSON source contract bytes are **NOT model token
accounting**. A one-sided success is a retrieval-quality difference, not
an admissible cost-saving comparison; unsupported cases with both zero
candidates do not count toward schema cost savings. No bootstrap,
independent publisher cases or semantic final accuracy claims from
this small developer-authored corpus. #1346 E2 external intake and
#1477 genuine paired agent qualification remain required. #1356 v0.18
HARD HOLD unchanged.

## Post-measurement results (separate from preregistration)

Measurement code head `c1c390da62793221395c5ff1a3284fd0163a0a5d`.
GitHub Linux successful test+measurement [run #40027465651](https://github.com/JDeun/SchemaRouter/actions/runs/40027465651),
artifact `paired-context-qualified-e0-40027465651` ID **12533112836**.
Prior failed runs were test-import formatting and `pytest-asyncio` missing
in the workflow, fixed before this result. No failed measurement value was
silently discarded; the first completed result has all 15 matrix cells.

**15 catalog/ambiguity strata, 234 developer-authored cases**: 180 supported
requests (12 per stratum) and 54 unsupported. Identical declared source
catalog/query and strict K=5 across both arms.

| Ambiguity (5 catalog sizes) | Lexical required-route hits | Indexed required-route hits | Indexed-only hits | Shared-correct support | Lexical bytes on shared hits | Indexed bytes on shared hits |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Low | 60/60 | 60/60 | 0 | 60 | 31,572 | 56,760 |
| Medium | 60/60 | 60/60 | 0 | 60 | 94,864 | 104,360 |
| High | 40/60 | 60/60 | **20** | 40 | 110,845 | 110,846 |
| **Total** | **160/180** | **180/180** | **20** | **160** | **237,281** | **271,966** |

Unsupported requests: both arms refused **54/54**. There were no
lexical-only route hits and no neither-hit supported cases. On the
**160 supported cases where both selected the required route**, default
indexed exposure was 34,685 source-contract bytes **higher** overall
(+14.62% relative to lexical); indexed was cheaper in 2 cases, lexical
cheaper in 39, equal in 119. The aggregate pooled byte comparison includes
ONLY shared-correct supported cases, no failed route retrieval
or no-fit cases. Low-ambiguity exposure difference is particularly
unfavorable: 56,760 indexed vs 31,572 lexical (+79.8%). In the 40
shared-correct high-ambiguity cases, bytes were essentially equal, but
indexed recovered 20 additional cases lexical missed; these additional
successes are intentionally not counted as "lower cost".

**Interpretation:** In this specific reproducible synthetic fixture the
current default indexed lexical+typed planner improves *required-route
recall* under high ambiguity without a corresponding shared-success
serialized-contract byte saving versus a strong schema-aware lexical K5.
The evaluation is PRE-AGENT; neither an LLM input token measure, a
multi-step agent success measure nor a new G5 typed graph experiment.
The result cannot establish that the paper's opt-in graph methodology
does or does not lower real token cost. It does establish that route
accuracy and exposure efficiency must be **separate Pareto criteria**,
with fair conditional denominators, before any future cost claim.

The following remains open: independently authored heterogeneous
query→field→route labels (#1346), real K5 G5 graph selector against
proper equal-budgets comparators (#1560), model completion under the
original host executor (#1477), and any production/release promotion.
The historical independent 0.14 negative remains unchanged and v0.18
#1356 stays HARD HOLD.

