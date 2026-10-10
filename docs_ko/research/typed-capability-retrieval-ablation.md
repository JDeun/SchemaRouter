# 0.14 typed capability retrieval representation ablation

Tracking issue: #434

이 successor experiment는 현재 B1 agent-utility run이 답하지 않는 다음 질문을 분리합니다.

> SchemaRouter의 structured capability metadata가 flattened tool specification보다 retrieval을 개선하는가? Offline intent-side expansion이 보완적 가치를 추가하는가?

## B1과 분리하는 이유

B1 (#420)은 이미 frozen 상태입니다. 목적은 실제 tool-calling agent 하나에서 FULL catalog exposure와 fixed SchemaRouter Top-K candidate exposure를 비교하는 것입니다.

이 실험은 B1을 수리하거나 재해석해서는 안 됩니다. Fresh disjoint retrieval surface를 사용하며 **downstream agent selection 이전의 representation quality**를 평가합니다.

## Frozen comparison

Preregistration:

`benchmarks/agent-utility-v2-representation-preregistration.json`

| Condition | 목적 |
| --- | --- |
| DESCRIPTION-ONLY | lower-bound diagnostic |
| RAW-SPEC | ordinary flattened specification baseline |
| TYPED-MULTIFIELD | SchemaRouter resource/action/input/output/semantic/unit/policy field를 분리 유지 |
| INTENT-MANUAL | capability-conditioned offline user-intent expansion |
| TYPED+INTENT | typed field + intent-side evidence |

TYPED-MULTIFIELD에서는 independent field ranking을 frozen `k=60` reciprocal-rank fusion으로 결합합니다.

## Fresh surfaces

#418/#420 row 대신 새로운 task surface를 사용합니다.

- DEV: unique semantic task 60개 × 6 language rendering = 360 rows
- Confirmation: unique semantic task 120개 × 6 language rendering = 720 rows
- 언어: 영어, 한국어, 스페인어, 일본어, 독일어, 식별자와 자연어가 혼합된 입력
- Catalog sizes: 100 / 250 / 500 / 1000 endpoints
- Statistical unit: semantic task. Language/catalog repeat는 repeated measure이며 독립 sample이 아님

Required strata에는 multi-step composition, sibling-operation ambiguity, semantic-ID collision, unit compatibility, read/write 및 destructive sibling, implicit argument, near-domain unsupported request, OOD가 포함됩니다.

## Primary evidence

Primary metrics:

- Recall@1/@3/@5/@10
- required-tool-set FullCoverage@K
- MRR / nDCG@K
- catalog-size scaling
- retrieval p50/p95
- index build cost와 size

Diagnostic은 다음도 분리합니다.

- semantic-ID contribution
- unit/dimension disambiguation
- read/write 및 destructive sibling confusion
- field-level ablation
- Top-K schema context size

Frozen Qwen3-0.6B tokenizer revision은 B1과 context measurement를 비교할 수 있도록 schema-token cost를 추정하는 데만 사용합니다. Retrieval model이 아닙니다.

## Research governance

- B1 row-level failure는 tuning data가 아님
- #432 held-out row는 tuning data가 아님
- Confirmation row로 field weight, fusion rule, K, condition을 변경할 수 없음
- Intent generation은 authoritative capability specification과 typed metadata만 사용 가능
- Generated intent는 source-capability provenance를 유지해야 함
- Final agent는 authoritative schema를 받으며 generated manual text를 execution authority로 받지 않음
- 이 실험만으로 end-to-end agent-utility claim을 할 수 없음

## Prior-art mapping

네 개의 보완적인 연구 흐름에서 동기를 얻습니다.

- **Toollery (2026)** — capability candidate compression과 offline intent-manual construction
- **Multi-Field Tool Retrieval (2026)** — raw document flattening 대신 structured field-level representation
- **ToolSense (2026)** — 모호성 등급과 자연스러운 질의에 따른 검색 성능 진단
- **ToolSearcher (NeurIPS 2026)** — iterative large-scale tool search. Static ablation에 가져오지 않고 이후 dynamic-retrieval 연구용으로 유지

결과는 SchemaRouter typed schema graph가 downstream execution을 위한 metadata에 불과한지, 아니면 측정 가능한 retrieval advantage도 제공하는지를 답해야 합니다.
