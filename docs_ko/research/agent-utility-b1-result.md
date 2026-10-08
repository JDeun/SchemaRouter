# 0.14 B1 canonical local-agent result

추적 issue: #420  
Parent research cycle: #417  
Canonical workflow: 36529108855  
Canonical source: `b9eadefd3cd076f026a54bbc55a949f0424f5dab`

## 상태

B1은 terminal 상태입니다.

Canonical run은 frozen micro-shard 30개를 모두 완료했고 정확히 552개의 unique `(catalog_size, task_id, condition)` episode를 aggregate했습니다.

Canonical aggregate의 식별 정보는 다음과 같습니다:

- artifact: `agent-utility-b1-canonical-36529108855`
- artifact id: `11021506964`
- artifact digest:
  `sha256:2e101d62dbe7f3202a24f0f40c49000064991b1521c4154c8feeb587de510271`
- aggregate JSON SHA-256:
  `33678700298a47b451ea1f03377cd874a1a1e373597cf961d207e07ae39f568d`
- corrected task SHA-256:
  `bc0b78ff2be11b89e6ac54ea0ee336f944f04b3c203fc61da70a46ff48b4e03c`

Compact machine-readable record는 다음 위치에 저장됩니다:
`benchmarks/results/agent-utility-b1-canonical-summary.json`.

## Frozen runtime

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

B1은 **sanity and reproducibility baseline**으로 유지됩니다. 23개 semantic task가 4개 catalog repeat에 걸쳐 clustered되어 있으므로 광범위한 population-level non-inferiority claim을 뒷받침하지 않습니다.

## 주요 결과

| Condition | Task pass | Required-route retrieval recall | Mean tool-schema tokens | Schema tokens vs FULL | Gate |
| --- | ---: | ---: | ---: | ---: | --- |
| FULL | 68.48% | 100.00% | 24,269.6 | 100.00% | reference |
| SR-3 | 82.61% | 96.55% | 800.6 | 3.30% | fails retrieval gate |
| **SR-5** | **91.30%** | **100.00%** | **1,315.9** | **5.42%** | **pass** |
| SR-10 | 81.52% | 100.00% | 2,476.8 | 10.21% | pass |
| SR-PROGRESSIVE | 82.61% | 100.00% final | 2,986.9 | 12.31% | pass |
| ORACLE | 86.96% | 100.00% | 441.3 | 1.82% | diagnostic |

고정된 small Qwen agent에서 SR-5는 FULL tool-schema token의 5.42%만 노출하면서 FULL 대비 deterministic task pass를 **+22.83 percentage point** 개선했습니다.

The task-clustered paired bootstrap interval for the SR-5 minus FULL task-pass
delta was **+9.78pp to +36.96pp** on this frozen 23-task surface. This interval is
descriptive for B1; it is not a population-level non-inferiority or general-agent
claim.

## Why the result matters

B1 directly tests the 0.14 product thesis rather than treating Top-1 routing as the
primary objective.

The same tool-using model received either the full catalog or a bounded
SchemaRouter candidate set. SR-5 retained every required route across the
20/50/100/250 endpoint catalog strata and materially reduced schema context.
On this controlled small-agent surface, exposing fewer relevant tools also produced
higher task completion than exposing the full catalog.

This supports the mechanism-level hypothesis:

> SchemaRouter can function as a compact typed capability-retrieval substrate in
> front of an agent, rather than needing to be the autonomous final tool selector.

It does **not** establish that SR-5 is universally optimal or that every stronger
agent will show the same benefit.

## Additional observations

- SR-3 missed the preregistered retrieval eligibility threshold:
  required-route recall was 96.55%, below 97%.
- SR-5 and SR-10 had 100% required-route recall and 100% all-required task
  coverage on the frozen surface.
- unauthorized destructive executions were 0 in every condition.
- SR-PROGRESSIVE reached 100% final retrieval coverage, but its four initial
  required-set misses yielded **0 recovered completed tasks**. The current
  progressive interaction policy therefore receives no superiority claim from B1.
- FULL becomes extremely expensive for the 0.6B CPU agent as catalog size grows.
  The latency observations are operational evidence for this exact runtime, not a
  provider-independent latency forecast.
- ORACLE did not dominate SR-5 in task pass. That is a useful reminder that an
  extremely minimal tool surface is not automatically the easiest interaction
  surface for a small generative agent.

## Claim boundary

B1 supports:

- the controlled Qwen3-0.6B mechanism/sanity claim;
- exact retrieval/context/task-pass measurements for this frozen benchmark;
- promotion to a materially stronger B2 replication.

B1 alone does not support:

- general statistical non-inferiority;
- claims about all LLM agents;
- claims about final-answer factuality, unit correctness or provenance;
- production-grade generalization.

Those require #423, #432, and #424 respectively.
