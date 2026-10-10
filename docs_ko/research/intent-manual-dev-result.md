# 0.14 intent-manual DEV 결과

Tracking issue: #434  
Canonical DEV workflow: 36547832179  
Canonical source: `9cf85e3c45491886a5f01a190e8e8e04f24898a7`

## 상태

이 DEV iteration은 **승격된 representation 없이** terminal입니다. 어떤 candidate도 preregistered DEV guardrail을 모두 만족하지 못했으므로 held-out confirmation surface는 **sealed, ungenerated, unscored** 상태를 유지합니다.

Canonical artifact:

- 산출물: `intent-manual-dev-36547832179`
- 산출물 ID: `11023311599`
- 산출물 다이제스트: `sha256:04719f39ab2e9198da8ead2ae276090c072df339854d19d5d4d5300bd604df40`
- 전체 결과 JSON SHA-256: `bb05aa1f53c084a45500fd3437dcd420dc204a8c82c8e84501b8655f52bd4e82`

Compact record는 `benchmarks/results/agent-utility-v2-intent-manual-dev-summary.json`입니다.

## Frozen intent-manual generator

DEV scoring 전에 generator를 동결했습니다.

- revision: `deterministic-capability-intent-manual-v1`
- LLM/hosted API 없음
- authoritative registered capability metadata만 source로 사용
- evaluation query, gold route, B1 row/error, confirmation row, retrieval rank/result, post-scoring manual edit 금지
- provenance용 exact route/tool fingerprint/endpoint fingerprint/source-catalog SHA/generator revision 보존
- exact duplicate/empty removal만 수행

Generator amendment SHA-256: `c199bb6f027e394e9e23e34e77b2ec424b57f8eb93e11953f7d617853da444c7`.

## DEV surface

- semantic task 60개
- 균등 stratum 12개
- task당 language rendering 6개
- 360 rows
- nested 100/250/500/1000 endpoint catalog
- representation 비교마다 동일 BM25 backbone
- latency: 3 warmups + row당 31 measurements, row median 후 row-median p95

## Promotion gate 결과

모든 delta는 동일 BM25의 RAW-SPEC 대비입니다.

| Candidate | Recall@5 Δ | FullCoverage@5 Δ | Recall@10 Δ | Max p95 ratio | Max index ratio | DEV promotion |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| TYPED-MULTIFIELD | +1.538pp | **+2.000pp** | 0.000pp | 1.873× | 1.469× | No |
| INTENT-MANUAL | +1.154pp | +1.500pp | -1.538pp | 1.707× | 1.328× | No |
| TYPED+INTENT | +1.154pp | +1.500pp | -0.769pp | 5.887× | 2.787× | No |

Frozen requirements:

- Recall@5 **또는** FullCoverage@5 improvement >= +2pp
- Recall@10 delta >= -0.5pp
- retrieval p95 <= 1.5× RAW-SPEC
- index bytes <= 3× RAW-SPEC
- deterministic provenance 유지

### TYPED-MULTIFIELD

FullCoverage@5는 정확히 +2.0pp 개선되고 Recall@10은 유지되어 실제 quality signal이 있었지만 latency가 1.873× RAW-SPEC으로 guardrail을 실패했습니다.

Gain은 균일하지 않습니다. three-step composition에서 FullCoverage@5가 약 +35pp인 반면 destructive/non-destructive sibling에서 약 10pp, read/write sibling에서 약 5pp 손실됩니다. Typed structure의 유용한 representation evidence이지만 multi-field RRF를 default로 승격하기에는 부족합니다.

### INTENT-MANUAL

Deterministic capability-conditioned manual은 three-step composition FullCoverage@5를 약 +15pp 개선하지만 global gain은 preregistered +2pp보다 작습니다. Recall@10도 약 1.54pp 낮아지고 latency ratio gate도 초과하므로 승격하지 않습니다.

1000 endpoint에서는 scaling signal이 있습니다.

- RAW-SPEC Recall@5: 93.85%
- INTENT-MANUAL Recall@5: 96.92%
- RAW-SPEC FullCoverage@5: 92%
- INTENT-MANUAL FullCoverage@5: 96%

그러나 Recall@10은 96.92% 대 98.46%로 더 낮아 global guardrail은 실패합니다. 이는 hypothesis-generating observation일 뿐입니다.

### TYPED+INTENT

Equal component-level RRF는 이 DEV surface에서 complementary utility를 추가하지 못했습니다. Quality threshold와 Recall@10 guardrail을 실패하고 두 retrieval path를 모두 실행해야 해 크게 느립니다. Combined-condition promotion claim은 지원되지 않습니다.

## 결정

Candidate에 대해 confirmation surface를 열지 않습니다. Pass를 강제하기 위한 post-hoc weight/template/K/query tuning도 하지 않습니다.

유지할 항목:

1. simple controlled representation baseline인 RAW-SPEC
2. typed structure가 multi-step coverage를 개선할 수 있으나 runtime/ambiguity cost가 있다는 multi-field 결과
3. negative/partial-positive prior-art replication인 intent-manual 결과
4. 향후 독립 preregistered successor용 exact generator/evaluation artifact

따라서 0.14 main evidence sequence는 #423 strong-agent B2 replication, #432 large independent held-out generalization, #424 final-answer factuality/units/provenance로 돌아갑니다.

이 결과는 released 0.11.0 product default를 변경하지 않으며 B1에 retrofit하지 않습니다.
