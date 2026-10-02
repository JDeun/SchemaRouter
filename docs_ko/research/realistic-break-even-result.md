# 현실적 라우팅 break-even 결과

이 문서는 #696의 retrieval hot-path 최적화 이후 #693에서 도입한 고정 합성 break-even matrix를 기록합니다. 이 결과는 routing benchmark이며 production adoption이나 최종 답변 품질의 증거가 아닙니다.

## 질문

핵심 질문은 SchemaRouter의 typed capability retrieval이 단순한 catalog 크기 때문에 필요한지, 아니면 catalog의 ambiguity와 schema heterogeneity 때문에 필요한지입니다.

고정 matrix는 **20 / 50 / 100 / 250 / 500**개 catalog와 **low / medium / high** ambiguity를 다룹니다. 강한 schema-aware lexical baseline, SchemaRouter exhaustive/full retrieval, SchemaRouter auto/indexed retrieval을 비교합니다.

## 라우팅 품질

모든 matrix cell에서 SchemaRouter auto와 exhaustive/full의 candidate selection이 일치했습니다.

- auto/full selection mismatch: **0**
- required-tool recall: **1.0**
- unsupported rejection: **1.0**
- false-route rate: **0.0**

강한 schema-aware lexical baseline 결과:

| Ambiguity | 20 | 50 | 100 | 250 | 500 | Unsupported rejection |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| low | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| medium | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| high | 0.583 | 0.667 | 0.583 | 0.583 | 0.583 | 1.000 |

따라서 low/medium fixture에서는 SchemaRouter의 정확도 우위를 입증하지 못했습니다. 반면 high ambiguity에서는 lexical baseline의 required-tool recall이 떨어졌고 SchemaRouter는 위의 고정 routing 품질을 유지했습니다.

## SchemaRouter auto latency

| Catalog size | Low p50 / p95 (ms) | Medium p50 / p95 (ms) | High p50 / p95 (ms) |
| ---: | ---: | ---: | ---: |
| 20 | 0.305 / 0.348 | 0.546 / 0.608 | 0.680 / 1.105 |
| 50 | 0.446 / 0.752 | 0.951 / 1.315 | 0.792 / 2.406 |
| 100 | 0.657 / 0.964 | 1.574 / 2.162 | 0.927 / 4.585 |
| 250 | 1.304 / 1.672 | 3.536 / 4.738 | 1.424 / 11.443 |
| 500 | 2.318 / 2.685 | 6.890 / 8.471 | 2.245 / 24.053 |

high ambiguity의 tail cost는 무시할 수 없습니다. p95는 250 tools에서 약 **11.44 ms**, 500 tools에서 약 **24.05 ms**입니다.

## Break-even 해석

고정된 분류는 다음과 같습니다.

- **low / medium ambiguity:** 이 fixture에서는 simple routing으로 충분
- **high ambiguity, 20 / 50 tools:** 낮은 overhead로 typed routing 이점
- **high ambiguity, 100 / 250 / 500 tools:** 측정 가능한 overhead를 동반한 typed routing 이점

즉 **catalog 크기 자체는 유용한 break-even 축이 아닙니다.** SchemaRouter의 근거는 heterogeneous provider/protocol, 겹치는 sibling operation, field semantics, datatype/unit/qualifier 요구사항, unsupported request rejection, policy-sensitive execution boundary에서 더 강합니다.

크지만 lexical하게 명확한 catalog는 SchemaRouter가 필요하지 않을 수 있습니다. 반대로 더 작은 catalog라도 semantic/schema 구분이 어렵다면 유용할 수 있습니다.

## Provenance

정정된 canonical 20-iteration workflow run: `37017834707`.

Artifact:
- name: `realistic-break-even`
- id: `11231726626`
- digest: `sha256:2a7323b1ab6c23519f139901e74bd49d999cb152f65a96a2213ac2f643f522ad`
- benchmark head: `4b26027601cf7ebedbc69fd46fc3fbedb9acf30e`
- benchmark implementation: `scripts/benchmark_realistic_break_even.py`
- workflow: `.github/workflows/realistic-break-even.yml`

초기 exploratory matrix는 unsupported field를 free-form concept로만 표현했습니다. 이 결과는 **evidence가 아니며**, semantic ID와 active field-evidence requirement 및 fail-closed unsupported request를 사용하는 위 정정 run으로 대체됐습니다.

## Claim boundary

이 결과는 결정론적 synthetic retrieval benchmark입니다. 통제된 routing break-even 결과만을 입증합니다. production adoption, independent reproduction, 실제 workload에서의 보편성, end-to-end agent answer quality를 입증하지 않습니다.
