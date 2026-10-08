# 0.14 B1 canonical local-agent 결과

Tracking issue: #420  
Parent research cycle: #417  
Canonical workflow: 36529108855  
Canonical source: `b9eadefd3cd076f026a54bbc55a949f0424f5dab`

## 상태

B1은 terminal입니다.

Canonical run은 frozen micro-shard 30개를 모두 완료했고 정확히 552개의 unique `(catalog_size, task_id, condition)` episode를 aggregate했습니다.

Canonical aggregate:

- 산출물: `agent-utility-b1-canonical-36529108855`
- 산출물 ID: `11021506964`
- 산출물 다이제스트: `sha256:2e101d62dbe7f3202a24f0f40c49000064991b1521c4154c8feeb587de510271`
- 집계 JSON SHA-256: `33678700298a47b451ea1f03377cd874a1a1e373597cf961d207e07ae39f568d`
- 수정된 작업 SHA-256: `bc0b78ff2be11b89e6ac54ea0ee336f944f04b3c203fc61da70a46ff48b4e03c`

Compact machine-readable record는 `benchmarks/results/agent-utility-b1-canonical-summary.json`에 저장됩니다.

## Frozen runtime

- 모델: `Qwen/Qwen3-0.6B`
- 리비전: `c1899de289a04d12100db370d81485cdf75e47ca`
- CPU float32
- Python 3.12.14
- torch 2.14.0+cpu
- transformers 4.57.6
- tokenizers 0.22.2
- safetensors 0.8.0
- 탐욕적 디코딩
- 추론 시 사고 모드 비활성화
- 에이전트 최대 6턴
- 시드 20260929

B1은 **sanity and reproducibility baseline**입니다. 23개 semantic task는 네 catalog repeat에 걸쳐 cluster되어 있으며 broad population-level non-inferiority claim을 지원하지 않습니다.

## Main result

| Condition | Task pass | Required-route retrieval recall | Mean tool-schema tokens | Schema tokens vs FULL | Gate |
| --- | ---: | ---: | ---: | ---: | --- |
| FULL | 68.48% | 100.00% | 24,269.6 | 100.00% | reference |
| SR-3 | 82.61% | 96.55% | 800.6 | 3.30% | fails retrieval gate |
| **SR-5** | **91.30%** | **100.00%** | **1,315.9** | **5.42%** | **pass** |
| SR-10 | 81.52% | 100.00% | 2,476.8 | 10.21% | pass |
| SR-PROGRESSIVE | 82.61% | 100.00% final | 2,986.9 | 12.31% | pass |
| ORACLE | 86.96% | 100.00% | 441.3 | 1.82% | diagnostic |

Fixed small Qwen agent에서 SR-5는 FULL 대비 deterministic task pass를 **+22.83 percentage points** 개선하면서 FULL tool-schema token의 5.42%만 노출했습니다.

SR-5 minus FULL task-pass delta의 task-clustered paired bootstrap interval은 frozen 23-task surface에서 **+9.78pp ~ +36.96pp**였습니다. 이 interval은 B1에 대한 descriptive 값이며 population-level non-inferiority 또는 general-agent claim이 아닙니다.

## 결과의 의미

B1은 Top-1 routing을 primary objective로 보는 대신 0.14 product thesis를 직접 시험합니다.

동일한 tool-using model이 full catalog 또는 bounded SchemaRouter candidate set을 받았습니다. SR-5는 20/50/100/250 endpoint catalog strata 전부에서 모든 required route를 유지하면서 schema context를 크게 줄였습니다. 이 controlled small-agent surface에서는 더 적고 관련성 높은 tool을 노출하는 것이 full catalog 노출보다 task completion도 높였습니다.

이는 mechanism-level hypothesis를 지지합니다.

> SchemaRouter는 autonomous final tool selector가 되어야 하는 대신 agent 앞의 compact typed capability-retrieval substrate로 기능할 수 있습니다.

SR-5가 보편적으로 최적이거나 모든 stronger agent가 동일한 benefit을 보인다는 뜻은 아닙니다.

## 추가 관측

- SR-3 required-route recall은 96.55%로 preregistered 97% retrieval eligibility threshold를 실패했습니다.
- SR-5와 SR-10은 frozen surface에서 required-route recall과 all-required task coverage가 모두 100%였습니다.
- 모든 condition에서 unauthorized destructive execution은 0이었습니다.
- SR-PROGRESSIVE는 final retrieval coverage 100%에 도달했지만 initial required-set miss 4건에서 **recovered completed task가 0건**이었습니다. 현재 progressive interaction policy에 B1 superiority claim은 없습니다.
- Catalog size가 커질수록 FULL은 0.6B CPU agent에 매우 비싸집니다. Latency 관측은 이 exact runtime의 operational evidence이지 provider-independent latency forecast가 아닙니다.
- ORACLE은 task pass에서 SR-5를 지배하지 못했습니다. 극단적으로 minimal한 tool surface가 small generative agent에 자동으로 가장 쉬운 interaction surface가 되는 것은 아닙니다.

## Claim boundary

B1이 지원하는 것:

- controlled Qwen3-0.6B mechanism/sanity claim
- 이 frozen benchmark의 exact retrieval/context/task-pass measurement
- materially stronger B2 replication으로의 promotion

B1만으로 지원하지 않는 것:

- general statistical non-inferiority
- 모든 LLM agent에 대한 claim
- final-answer factuality, unit correctness 또는 provenance claim
- production-grade generalization

각각 #423, #432, #424가 필요합니다.
