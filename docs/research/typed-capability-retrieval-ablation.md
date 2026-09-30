# 0.14 typed capability retrieval representation ablation

Tracking issue: #434

This successor experiment isolates a question that the current B1 agent-utility run does not answer:

> Does SchemaRouter's structured capability metadata improve retrieval compared with flattened tool specifications, and does offline intent-side expansion add complementary value?

## Why this is separate from B1

B1 (#420) is already frozen. Its purpose is to compare FULL catalog exposure with fixed SchemaRouter Top-K candidate exposure under one actual tool-calling agent.

This experiment must not repair or reinterpret B1. It uses a fresh disjoint retrieval surface and evaluates **representation quality before downstream agent selection**.

## Frozen comparison

The preregistration is stored at:

`benchmarks/agent-utility-v2-representation-preregistration.json`

Conditions:

| Condition | Purpose |
| --- | --- |
| DESCRIPTION-ONLY | lower-bound diagnostic |
| RAW-SPEC | ordinary flattened specification baseline |
| TYPED-MULTIFIELD | SchemaRouter resource/action/input/output/semantic/unit/policy fields kept separate |
| INTENT-MANUAL | capability-conditioned offline user-intent expansion |
| TYPED+INTENT | typed fields plus intent-side evidence |

For TYPED-MULTIFIELD, independent field rankings are fused with reciprocal-rank fusion using frozen `k=60`.

## Fresh surfaces

The experiment uses a new task surface rather than #418/#420 rows:

- DEV: 60 unique semantic tasks × 6 language renderings = 360 rows.
- Confirmation: 120 unique semantic tasks × 6 language renderings = 720 rows.
- Languages: English, Korean, Spanish, Japanese, German, and mixed identifiers/text.
- Catalog sizes: 100 / 250 / 500 / 1000 endpoints.
- Statistical unit: semantic task. Language and catalog repeats are repeated measures, not independent samples.

The required strata include multi-step composition, sibling-operation ambiguity, semantic-ID collisions, unit compatibility, read/write and destructive siblings, implicit arguments, near-domain unsupported requests, and OOD.

## Primary evidence

Primary metrics:

- Recall@1/@3/@5/@10;
- required-tool-set FullCoverage@K;
- MRR / nDCG@K;
- catalog-size scaling;
- retrieval p50/p95;
- index build cost and size.

Diagnostics additionally isolate:

- semantic-ID contribution;
- unit/dimension disambiguation;
- read/write and destructive sibling confusion;
- field-level ablations;
- Top-K schema context size.

A frozen Qwen3-0.6B tokenizer revision is used only to project schema-token cost so context measurements remain comparable with B1. It is not the retrieval model.

## Research governance

- B1 row-level failures are not tuning data.
- #432 held-out rows are not tuning data.
- Confirmation rows cannot change field weights, fusion rules, K, or conditions.
- Intent generation may use authoritative capability specifications and typed metadata only.
- Generated intents must retain source-capability provenance.
- The final agent receives authoritative schemas, never generated manual text as execution authority.
- This experiment alone cannot support an end-to-end agent-utility claim.

## Prior-art mapping

The experiment is motivated by four complementary lines:

- **Toollery (2026)** — capability candidate compression and offline intent-manual construction;
- **Multi-Field Tool Retrieval (2026)** — structured field-level representation instead of raw document flattening;
- **ToolSense (2026)** — ambiguity-tiered/naturalistic retrieval diagnostics;
- **ToolSearcher (NeurIPS 2026)** — iterative large-scale tool search, retained for later dynamic-retrieval work rather than imported into this static ablation.

The result should answer whether SchemaRouter's typed schema graph is merely metadata for downstream execution, or also a measurable retrieval advantage.
