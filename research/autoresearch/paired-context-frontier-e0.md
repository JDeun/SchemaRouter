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

## Post-measurement result

Append exact run/commit hash and all positive and negative strata **only
after** the first clean GitHub Linux run completes. No new result was
observed when this protocol was written.
