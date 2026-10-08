# 0.14 intent-manual DEV 결과

추적 이슈: #434  
Canonical DEV workflow: 36547832179  
Canonical source: `9cf85e3c45491886a5f01a190e8e8e04f24898a7`

## 상태

이 DEV iteration은 **promoted representation 없이 terminal**입니다.

Held-out confirmation surface는 계속 **sealed, ungenerated, unscored** 상태입니다. Candidate condition 중 preregistered DEV guardrail을 모두 만족하는 것이 없으므로 confirmation을 여는 것은 이미 promotion 자격이 없는 candidate에 held-out evidence를 소모할 뿐입니다.

Canonical artifact:

- artifact: `intent-manual-dev-36547832179`
- artifact id: `11023311599`
- artifact digest: `sha256:04719f39ab2e9198da8ead2ae276090c072df339854d19d5d4d5300bd604df40`
- full result JSON SHA-256: `bb05aa1f53c084a45500fd3437dcd420dc204a8c82c8e84501b8655f52bd4e82`

Compact machine-readable record는 `benchmarks/results/agent-utility-v2-intent-manual-dev-summary.json`입니다.

## 고정 intent-manual generator

Generator는 intent-manual DEV scoring 전에 freeze했습니다.

- revision: `deterministic-capability-intent-manual-v1`
- LLM 또는 hosted API 없음
- source: authoritative registered capability metadata만 사용
- forbidden inputs: evaluation query, gold route, B1 row/error, confirmation row, retrieval rank/result, post-scoring manual edit
- provenance를 위해 exact route, tool fingerprint, endpoint fingerprint, source-catalog SHA, generator revision 유지
- exact duplicate/empty removal만 수행

Generator amendment SHA-256: `c199bb6f027e394e9e23e34e77b2ec424b57f8eb93e11953f7d617853da444c7`.

## DEV surface

- 60 semantic tasks
- 12 equal strata
- semantic task당 6 language rendering
- 360 rows
- nested 100 / 250 / 500 / 1000 endpoint catalog
- representation 비교마다 동일 BM25 backbone
- repeated latency protocol: row당 3 warmup + 31 measurement, row median, 이후 row median의 p95

## Promotion gate 결과

모든 delta는 동일 BM25 구현의 RAW-SPEC 대비 값입니다.

| Candidate | Recall@5 Δ | FullCoverage@5 Δ | Recall@10 Δ | Max p95 ratio | Max index ratio | DEV promotion |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| TYPED-MULTIFIELD | +1.538pp | **+2.000pp** | 0.000pp | 1.873× | 1.469× | No |
| INTENT-MANUAL | +1.154pp | +1.500pp | -1.538pp | 1.707× | 1.328× | No |
| TYPED+INTENT | +1.154pp | +1.500pp | -0.769pp | 5.887× | 2.787× | No |

고정 requirement:

- Recall@5 **또는** FullCoverage@5 improvement >= +2pp
- Recall@10 delta >= -0.5pp
- retrieval p95 <= 1.5× RAW-SPEC
- index bytes <= 3× RAW-SPEC
- deterministic provenance 유지

### TYPED-MULTIFIELD

실제 quality signal이 있었습니다. FullCoverage@5가 정확히 +2.0pp 개선됐고 Recall@10은 변하지 않았습니다. 하지만 latency guardrail 1.5×를 넘는 1.873× RAW-SPEC이므로 실패합니다.

Gain은 균일하지 않습니다. 가장 큰 DEV benefit은 three-step composition에 집중되어 mean FullCoverage@5가 약 +35pp 개선됩니다. 반면 destructive/non-destructive sibling task에서 약 10pp, read/write sibling task에서 약 5pp 손실됩니다.

이는 유용한 representation evidence지만 multi-field RRF path를 default로 promotion하기에는 부족합니다.

### INTENT-MANUAL

Deterministic capability-conditioned manual은 three-step composition FullCoverage@5를 약 +15pp 개선하지만 global gain은 preregistered +2pp threshold보다 작습니다.

Recall@10도 약 1.54pp 낮아지고 latency ratio gate를 초과합니다. Metadata-only deterministic intent expansion은 promotion하지 않습니다.

1000 endpoint에서는 scaling signal이 있습니다.

- RAW-SPEC Recall@5: 93.85%
- INTENT-MANUAL Recall@5: 96.92%
- RAW-SPEC FullCoverage@5: 92%
- INTENT-MANUAL FullCoverage@5: 96%

그러나 Recall@10은 96.92%로 RAW-SPEC 98.46%보다 낮으므로 global guardrail은 여전히 실패합니다. 이 관찰은 hypothesis-generating 용도로만 사용합니다.

### TYPED+INTENT

Equal component-level RRF는 이 DEV surface에서 complementary utility를 추가하지 못합니다. Quality threshold를 충족하지 못하고 Recall@10 guardrail도 놓치며, fusion 전에 두 retrieval path를 모두 실행해야 하므로 훨씬 느립니다.

Combined-condition promotion claim은 지지되지 않습니다.

## 결정

이 candidate들에 대해 confirmation surface를 **열지 않습니다**.

Pass를 강제로 만들기 위해 이 DEV surface에서 post-hoc weight, template, K 또는 query tuning을 계속하지 않습니다.

유지할 항목:

1. 단순 controlled representation baseline인 RAW-SPEC
2. typed structure가 multi-step coverage를 개선할 수 있지만 현재 runtime/ambiguity cost가 있다는 evidence로서 typed multi-field 결과
3. negative/partial-positive prior-art replication으로서 intent-manual 결과
4. 향후 independently preregistered successor가 필요할 경우를 위한 정확한 generator/evaluation artifact

따라서 주요 0.14 evidence sequence는 다음으로 돌아갑니다.

- #423 strong-agent B2 replication
- #432 large independent held-out generalization
- #424 final-answer factuality / units / provenance

이 결과는 released 0.11.0 product default를 변경하지 않으며 B1에 소급 적용하지 않습니다.
