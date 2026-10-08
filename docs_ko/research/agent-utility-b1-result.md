# 0.14 B1 canonical local-agent 결과

추적 이슈: #420  
상위 연구 cycle: #417  
Canonical workflow: 36529108855  
Canonical source: `b9eadefd3cd076f026a54bbc55a949f0424f5dab`

## 상태

B1은 terminal입니다.

Canonical run은 고정된 30개 micro-shard를 모두 완료했고 정확히 552개의 unique `(catalog_size, task_id, condition)` episode를 집계했습니다.

Canonical aggregate 식별자:

- artifact: `agent-utility-b1-canonical-36529108855`
- artifact id: `11021506964`
- artifact digest: `sha256:2e101d62dbe7f3202a24f0f40c49000064991b1521c4154c8feeb587de510271`
- aggregate JSON SHA-256: `33678700298a47b451ea1f03377cd874a1a1e373597cf961d207e07ae39f568d`
- corrected task SHA-256: `bc0b78ff2be11b89e6ac54ea0ee336f944f04b3c203fc61da70a46ff48b4e03c`

Compact machine-readable record는 `benchmarks/results/agent-utility-b1-canonical-summary.json`에 저장합니다.

## 고정 runtime

- model: `Qwen/Qwen3-0.6B`
- revision: `c1899de289a04d12100db370d81485cdf75e47ca`
- CPU float32
- Python 3.12.14
- torch 2.14.0+cpu
- transformers 4.57.6
- tokenizers 0.22.2
- safetensors 0.8.0
- greedy decoding
- thinking disabled
- maximum 6 agent turns
- seed 20260929

B1은 **sanity 및 reproducibility baseline**입니다. 23개 semantic task가 네 catalog repeat에 걸쳐 clustered되어 있으므로 광범위한 population-level non-inferiority 주장을 뒷받침하지 않습니다.

## 주요 결과

| Condition | Task pass | Required-route retrieval recall | Mean tool-schema tokens | Schema tokens vs FULL | Gate |
| --- | ---: | ---: | ---: | ---: | --- |
| FULL | 68.48% | 100.00% | 24,269.6 | 100.00% | reference |
| SR-3 | 82.61% | 96.55% | 800.6 | 3.30% | fails retrieval gate |
| **SR-5** | **91.30%** | **100.00%** | **1,315.9** | **5.42%** | **pass** |
| SR-10 | 81.52% | 100.00% | 2,476.8 | 10.21% | pass |
| SR-PROGRESSIVE | 82.61% | 100.00% final | 2,986.9 | 12.31% | pass |
| ORACLE | 86.96% | 100.00% | 441.3 | 1.82% | diagnostic |

고정된 소형 Qwen agent에서 SR-5는 FULL 대비 deterministic task pass를 **+22.83 percentage points** 개선하면서 FULL tool-schema token의 5.42%만 노출했습니다.

SR-5 minus FULL task-pass delta에 대한 task-clustered paired bootstrap interval은 고정된 23-task surface에서 **+9.78pp ~ +36.96pp**였습니다. 이 interval은 B1에 대한 descriptive 결과이며 population-level non-inferiority 또는 general-agent 주장이 아닙니다.

## 결과의 의미

B1은 Top-1 routing을 primary objective로 취급하지 않고 0.14 product thesis를 직접 검증합니다.

동일한 tool-using model에 full catalog 또는 bounded SchemaRouter candidate set을 제공했습니다. SR-5는 20/50/100/250 endpoint catalog strata 전체에서 필요한 route를 모두 유지하면서 schema context를 크게 줄였습니다. 이 controlled small-agent surface에서는 관련 tool을 더 적게 노출했을 때 full catalog보다 task completion도 높았습니다.

이는 다음 mechanism-level hypothesis를 지지합니다.

> SchemaRouter는 autonomous final tool selector가 될 필요 없이 agent 앞단의 compact typed capability-retrieval substrate로 기능할 수 있습니다.

SR-5가 보편적으로 최적이거나 모든 stronger agent에서 같은 이득이 나타난다는 뜻은 아닙니다.

## 추가 관찰

- SR-3의 required-route recall은 96.55%로 preregistered retrieval eligibility threshold 97%를 충족하지 못했습니다.
- SR-5와 SR-10은 고정 surface에서 required-route recall과 all-required task coverage 모두 100%였습니다.
- 모든 condition에서 unauthorized destructive execution은 0이었습니다.
- SR-PROGRESSIVE는 최종 retrieval coverage 100%에 도달했지만 초기 required-set miss 4건에서 **복구된 completed task는 0건**이었습니다. 따라서 현재 progressive interaction policy에 대해 B1은 superiority claim을 제공하지 않습니다.
- Catalog size가 커질수록 FULL은 0.6B CPU agent에 매우 비쌉니다. Latency 관찰은 이 정확한 runtime에 대한 operational evidence이며 provider-independent forecast가 아닙니다.
- ORACLE은 task pass에서 SR-5를 능가하지 못했습니다. 극도로 작은 tool surface가 소형 generative agent에 자동으로 가장 쉬운 interaction surface가 되는 것은 아니라는 점을 보여줍니다.

## Claim 경계

B1이 지지하는 것:

- controlled Qwen3-0.6B mechanism/sanity claim
- 이 frozen benchmark의 정확한 retrieval/context/task-pass measurement
- 훨씬 강한 B2 replication으로의 promotion

B1만으로 지지하지 않는 것:

- general statistical non-inferiority
- 모든 LLM agent에 대한 주장
- final-answer factuality, unit correctness 또는 provenance 주장
- production-grade generalization

각각 #423, #432, #424가 필요합니다.
