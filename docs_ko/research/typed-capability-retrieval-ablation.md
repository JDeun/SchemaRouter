# 0.14 typed capability retrieval representation ablation

추적 issue: #434

이 successor experiment는 현재 B1 agent-utility run이 답하지 않는 질문을 분리해 검증합니다:

> SchemaRouter의 structured capability metadata가 flattened tool specification보다 retrieval을 개선하는가? 그리고 offline intent-side expansion이 complementary value를 추가하는가?

## B1과 분리하는 이유

B1 (#420)은 이미 freeze되었습니다. 목적은 하나의 실제 tool-calling agent에서 FULL catalog exposure와 fixed SchemaRouter Top-K candidate exposure를 비교하는 것입니다.

이 experiment는 B1을 수정하거나 재해석해서는 안 됩니다. Fresh disjoint retrieval surface를 사용하여 **downstream agent selection 이전의 representation quality**를 평가합니다.

## Frozen comparison

Preregistration은 다음 위치에 저장됩니다:

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

## Fresh surface

이 experiment는 #418/#420 row 대신 새로운 task surface를 사용합니다:

- DEV: 60 unique semantic tasks × 6 language renderings = 360 rows.
- Confirmation: 120 unique semantic tasks × 6 language renderings = 720 rows.
- Languages: English, Korean, Spanish, Japanese, German, and mixed identifiers/text.
- Catalog sizes: 100 / 250 / 500 / 1000 endpoints.
- Statistical unit: semantic task. Language and catalog repeats are repeated measures, not independent samples.

The required strata include multi-step composition, sibling-operation ambiguity, semantic-ID collisions, unit compatibility, read/write and destructive siblings, implicit arguments, near-domain unsupported requests, and OOD.

## Primary evidence

Primary metric:

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
