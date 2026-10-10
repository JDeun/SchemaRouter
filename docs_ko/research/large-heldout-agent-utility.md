# 0.14 대규모 held-out agent-utility 벤치마크

Tracking issue: #432

이 benchmark는 controlled B1/B2 experiment 이후의 generalization layer입니다. B1/B2의 row-level outcome을 사용하지 않고 동결합니다.

## 새로운 surface가 필요한 이유

B1/B2는 catalog-size repeat 전반에서 23개 semantic task를 재사용합니다. 이는 mechanism replication에는 적절하지만 catalog repeat는 동일 task의 repeated measure이므로 독립 sample로 계산할 수 없습니다.

따라서 held-out benchmark는 **780개의 독립 semantic task**를 사용합니다.

## 동결된 population 설계

780개 task는 다음과 같이 교차 균형화됩니다.

- 13개 task strata
- 6개 language strata
- 각 task-stratum × language cell당 10개의 독립 semantic task

따라서 다음과 같습니다.

- task stratum당 독립 task 60개
- language당 독립 task 130개
- 총 780개의 독립 semantic task

각 task는 정확히 하나의 language stratum에 속합니다. 하나의 semantic task를 6개 언어로 번역한 뒤 이를 6개의 독립 task로 계산하지 않습니다.

Task strata:

1. single-tool exact
2. two-step state-dependent
3. three-step state-dependent
4. sibling-operation ambiguity
5. typed numeric values and units
6. identifier/provenance propagation
7. read vs write siblings
8. destructive vs non-destructive siblings
9. insufficient information
10. recoverable execution failure
11. missing capability / unsupported
12. semantically adjacent distractors
13. genuine OOD

Languages:

- English
- Korean
- Spanish
- Japanese
- German
- 실제와 유사한 다국어 혼합 식별자·질의 텍스트

## Catalog scaling

Retrieval-only characterization에서는 다음 nested catalog를 사용합니다.

- 100
- 250
- 500
- 1000 endpoints

Downstream agent comparison에서는 다음을 사용합니다.

- 100
- 250
- 500 endpoints

1000-endpoint stratum은 retrieval scaling을 위해 유지하지만 많은 65k-class agent에서 FULL을 예측 가능한 infeasible context regime으로 강제하지는 않습니다.

Catalog repeat는 `semantic_task_id` 내부에 nested됩니다.

## Conditions

Held-out agent comparison은 다음을 동결합니다.

- FULL
- SR-5
- SR-10
- SR-PROGRESSIVE
- ORACLE

Adaptive #430 policy는 승격되지 않았습니다. 이후 별도로 preregister된 structural K3 candidate 역시 strong-agent K3-vs-K5 task-pass promotion gate에 실패했으므로 K3는 held-out condition manifest로 가져가지 않습니다. #431 state-aware corrective retrieval은 manifest가 동결되기 전까지 active optional condition gate로 남습니다.

SchemaRouter ranking score/position은 downstream agent에 노출하지 않습니다. Visible candidate는 registered route ID의 사전식 순서로 정렬합니다.

## Precision과 -2pp margin

실용적인 engineering margin은 FULL 대비 **-2 percentage points**를 유지합니다.

Sample size는 관측된 B1/B2 effect에서 선택하지 않습니다.

[-1, 1] 범위의 paired task-level difference에 대해 보수적인 worst-case normal-approximate 95% half-width는 다음과 같습니다.

```text
1.96 / sqrt(n)
```

`n = 780`에서 worst-case half-width는 약 7.02pp입니다.

2pp half-width를 보장하는 worst-case design은 약 **9,604개의 독립 semantic task**가 필요하며, 계획된 catalog/condition matrix의 downstream-agent benchmark로는 실용적이지 않습니다.

따라서:

- -2pp는 engineering threshold로 유지
- preregistered task-cluster CI는 재해석 없이 보고
- 실제 frozen paired 95% CI lower bound가 -2pp를 넘는 경우에만 statistical non-inferiority statement 허용
- 그렇지 않으면 held-out generalization과 uncertainty reporting을 지지할 수는 있지만 statistical non-inferiority claim은 할 수 없음

Preregistration의 illustrative precision 값은 design tradeoff를 문서화하기 위한 것이며 B1/B2에서 fitting한 값이 아닙니다.

## Primary inference

Primary interval은 **stratified task-cluster bootstrap**을 사용합니다.

- unit: `semantic_task_id`
- strata: task type × language
- 78 cells
- 각 cell에서 task ID 10개 resample
- 각 sampled task 내부의 catalog repeat 유지
- 10,000 iterations
- seed 20260929
- 95% interval

이를 통해 catalog-size pseudoreplication을 방지하면서 benchmark의 균형 잡힌 task/language population을 유지합니다.

## Claim gate

광범위한 SchemaRouter agent-utility claim을 하려면 다음을 모두 만족해야 합니다.

1. B2 strong-agent replication이 존재
2. 동일한 deployable SR condition이 held-out product gate 통과
3. required-tool-set retrieval이 최소 97%
4. tool-schema token이 FULL의 최대 40%
5. total input token이 FULL보다 적음
6. unauthorized destructive execution이 0
7. FULL 대비 held-out paired 95% CI lower bound가 최소 -2pp
8. context-reduction 방향이 Phase A, B1, B2와 일치

CI가 -2pp를 넘지 못하면 paper/README는 uncertainty를 그대로 보고해야 하며 engineering threshold를 statistical theorem으로 승격해서는 안 됩니다.

## B2 terminal 이전 authoring scaffold

B2가 terminal이 되기 전 deterministic scaffold를 준비할 수 있지만 **authoring slot**으로 제한합니다. 다음만 동결합니다.

- 780개의 unique `semantic_task_id`
- ID당 하나의 preregistered task stratum
- ID당 하나의 preregistered language stratum
- 78개 task-stratum × language cell 각각에 10개의 독립 slot

Scaffold는 다음을 생성하거나 포함하지 않습니다.

- task/query wording
- required/gold route
- expected answer
- executor state 또는 deterministic tool output
- catalog 또는 candidate set
- score 또는 label

Generator는 `scripts/generate_agent_utility_v3_heldout_authoring_plan.py`입니다. B2는 현재 terminal이지만 실제 held-out content/inference는 #500 conveyor가 계속 통제합니다. Manifest는 preregistered structural-K gate와 #431 corrective gate가 terminal이 된 뒤에만 동결됩니다. Structural K3 gate는 이미 terminal negative이며 #431은 active 상태입니다.

## Corpus identity validation

생성된 corpus를 freeze하거나 score하기 전에 authored row에 대해 `scripts/validate_agent_utility_corpus_identity.py`를 실행합니다.

Validator는 이후 semantic scorer보다 좁은 범위만 검사합니다. Benchmark outcome에 의존해서는 안 되는 pre-scoring integrity만 강제합니다.

- 모든 preregistered authoring slot이 정확히 한 번 존재
- semantic task ID가 frozen slot plan과 일치
- task/answer stratum 및 language assignment drift 금지
- query text는 비어 있지 않아야 함
- normalized query text는 semantic task 사이에서 unique해야 함
- freeze manifest를 위한 stable identity/query-content SHA-256 출력

Validator는 content를 생성하거나 content quality를 승인하거나 inference를 허가하거나 model outcome을 검사하지 않습니다.

## Independence rules

최종 780개 task는 다음을 사용할 수 없습니다.

- B1 task wording 또는 paraphrase
- B1 row-level failure
- B2 task outcome 또는 failure
- 이슈 #434 DEV query
- scoring 이후 task 삭제
- scoring 이후 prompt/K/representation tuning

모든 task text, executor state transition, deterministic output, catalog, candidate set, hash는 held-out inference 전에 동결합니다.

## #424와의 경계

이 benchmark는 retrieval, tool use, execution state, efficiency, safety를 측정합니다. 그 자체로 final-answer factuality, unit correctness 또는 provenance quality를 입증하지 않습니다. 해당 주장은 계속 #424 범위에 속합니다.
