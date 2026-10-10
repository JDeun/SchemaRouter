# 0.14 intent-manual DEV result

Tracking issue: #434  
Canonical DEV workflow: 36547832179  
Canonical source: `9cf85e3c45491886a5f01a190e8e8e04f24898a7`

## Status

This DEV iteration is terminal with **no promoted representation**.

The held-out confirmation surface remains **sealed, ungenerated, and unscored**.
Because none of the candidate conditions satisfies every preregistered DEV guardrail,
opening confirmation would only spend held-out evidence on a candidate that is already
ineligible for promotion.

Canonical artifact:

- artifact: `intent-manual-dev-36547832179`
- artifact id: `11023311599`
- artifact digest:
  `sha256:04719f39ab2e9198da8ead2ae276090c072df339854d19d5d4d5300bd604df40`
- full result JSON SHA-256:
  `bb05aa1f53c084a45500fd3437dcd420dc204a8c82c8e84501b8655f52bd4e82`

The compact machine-readable record is
`benchmarks/results/agent-utility-v2-intent-manual-dev-summary.json`.

## Frozen intent-manual generator

The generator was frozen before intent-manual DEV scoring:

- revision: `deterministic-capability-intent-manual-v1`;
- no LLM or hosted API;
- source: authoritative registered capability metadata only;
- forbidden inputs: evaluation queries, gold routes, B1 rows/errors, confirmation rows,
  retrieval ranks/results, and post-scoring manual edits;
- exact route, tool fingerprint, endpoint fingerprint, source-catalog SHA and generator
  revision retained for provenance;
- exact duplicate/empty removal only.

The generator amendment SHA-256 is
`c199bb6f027e394e9e23e34e77b2ec424b57f8eb93e11953f7d617853da444c7`.

## DEV surface

- 60 semantic tasks;
- 12 equal strata;
- 6 language renderings per semantic task;
- 360 rows;
- nested 100 / 250 / 500 / 1000 endpoint catalogs;
- same BM25 backbone within each representation comparison;
- repeated latency protocol: 3 warmups + 31 measurements per row, row median,
  then p95 of row medians.

## Promotion gate result

All deltas are relative to RAW-SPEC under the same BM25 implementation.

| Candidate | Recall@5 Δ | FullCoverage@5 Δ | Recall@10 Δ | Max p95 ratio | Max index ratio | DEV promotion |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| TYPED-MULTIFIELD | +1.538pp | **+2.000pp** | 0.000pp | 1.873× | 1.469× | No |
| INTENT-MANUAL | +1.154pp | +1.500pp | -1.538pp | 1.707× | 1.328× | No |
| TYPED+INTENT | +1.154pp | +1.500pp | -0.769pp | 5.887× | 2.787× | No |

Frozen requirements:

- Recall@5 **or** FullCoverage@5 improvement >= +2pp;
- Recall@10 delta >= -0.5pp;
- retrieval p95 <= 1.5× RAW-SPEC;
- index bytes <= 3× RAW-SPEC;
- deterministic provenance retained.

### TYPED-MULTIFIELD

This condition produced a real quality signal: FullCoverage@5 improved exactly
+2.0pp, and Recall@10 was unchanged. It nevertheless fails the unchanged
latency guardrail at 1.873× RAW-SPEC.

The gain is not uniform. Its largest DEV benefit is concentrated in
three-step composition, where mean FullCoverage@5 improves by about +35pp.
It loses about 10pp on destructive/non-destructive sibling tasks and about
5pp on read/write sibling tasks.

This is useful representation evidence, but not enough to promote the multi-field
RRF path as a default.

### INTENT-MANUAL

The deterministic capability-conditioned manual improves three-step composition
FullCoverage@5 by about +15pp, but the global gains are smaller than the
preregistered +2pp threshold.

It also lowers Recall@10 by about 1.54pp and exceeds the latency ratio gate.
Metadata-only deterministic intent expansion is not promoted.

At 1000 endpoints, the intent manual does show a scaling signal:

- RAW-SPEC Recall@5: 93.85%;
- INTENT-MANUAL Recall@5: 96.92%;
- RAW-SPEC FullCoverage@5: 92%;
- INTENT-MANUAL FullCoverage@5: 96%.

However, its Recall@10 is lower (96.92% vs 98.46%), so the global guardrail still
fails. This observation is hypothesis-generating only.

### TYPED+INTENT

Equal component-level RRF does not add complementary utility on this DEV surface.
It fails the quality threshold, misses the Recall@10 guardrail, and is substantially
slower because both retrieval paths must execute before fusion.

No combined-condition promotion claim is supported.

## Decision

Do **not** open the confirmation surface for these candidates.

Do **not** continue post-hoc weight, template, K, or query tuning on this DEV surface
to force a pass.

Retain:

1. RAW-SPEC as the simple controlled representation baseline;
2. the typed multi-field result as evidence that typed structure can improve
   multi-step coverage but currently carries a runtime/ambiguity cost;
3. the intent-manual result as a negative/partial-positive prior-art replication;
4. the exact generator and evaluation artifacts for a future independently
   preregistered successor, if one is warranted.

So the main 0.14 evidence sequence returns to:

- Issue #423 strong-agent B2 replication;
- Issue #432 large independent held-out generalization;
- Issue #424 final-answer factuality / units / provenance.

This result does not modify the released 0.11.0 product default and is not retrofitted
into B1.
