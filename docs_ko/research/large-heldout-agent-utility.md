# 0.14 대규모 held-out agent-utility benchmark

추적 이슈: #432

이 benchmark는 controlled B1/B2 experiment 이후의 generalization layer입니다. B1/B2 row-level outcome을 사용하지 않고 freeze합니다.

## 새로운 surface가 필요한 이유

B1/B2는 catalog-size repeat 전체에서 23개 semantic task를 재사용합니다. Mechanism replication에는 적절하지만 catalog repeat는 동일 task의 repeated measure이므로 independent sample로 계산할 수 없습니다.

따라서 held-out benchmark는 **780개의 독립 semantic task**를 사용합니다.

## 고정 population design

780 task는 다음과 같이 cross-balance합니다.

- 13 task strata
- 6 language strata
- task-stratum × language cell당 10개의 독립 semantic task

따라서:

- task stratum당 독립 task 60개
- language당 독립 task 130개
- 총 780개의 독립 semantic task

각 task는 정확히 하나의 language stratum에만 속합니다. 하나의 semantic task를 6개 언어로 번역하고 이를 독립 task로 계산하지 않습니다.

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
- realistic mixed-language identifiers/query text

## Catalog scaling

Retrieval-only characterization은 nested catalog 100/250/500/1000 endpoint를 사용합니다.

Downstream agent comparison은 100/250/500 endpoint를 사용합니다.

1000-endpoint stratum은 retrieval scaling을 위해 유지하지만 많은 65k-class agent에서 FULL을 예측 가능하게 infeasible한 context regime에 강제로 넣지는 않습니다.

Catalog repeat는 `semantic_task_id` 내부에 nested됩니다.

## 조건

Held-out agent comparison의 고정 조건:

- FULL
- SR-5
- SR-10
- SR-PROGRESSIVE
- ORACLE

Adaptive #430 policy는 promotion되지 않았습니다. 별도로 preregister된 structural K3 candidate도 strong-agent K3-vs-K5 task-pass promotion gate를 실패했으므로 held-out condition manifest에 포함하지 않습니다. #431 state-aware corrective retrieval은 manifest freeze 전의 active optional condition gate로 유지됩니다.

SchemaRouter ranking score/position은 downstream agent에게 숨깁니다. Visible candidate는 registered route ID의 lexicographic 순서로 정렬합니다.

## Precision과 -2pp margin

Practical engineering margin은 FULL 대비 **-2 percentage points**를 유지합니다.

Sample size는 관측된 B1/B2 effect로 선택하지 않습니다.

[-1, 1] 범위의 paired task-level difference에 대한 conservative worst-case normal-approximate 95% half-width:

```text
1.96 / sqrt(n)
```

`n = 780`이면 worst-case half-width는 약 7.02pp입니다.

2pp half-width를 보장하는 worst-case design에는 약 **9,604개의 독립 semantic task**가 필요하며, 계획된 catalog/condition matrix의 downstream-agent benchmark로는 실용적이지 않습니다.

따라서:

- -2pp는 engineering threshold로 유지
- preregistered task-cluster CI를 재해석 없이 보고
- 실제 frozen paired 95% CI lower bound가 -2pp를 넘을 때만 statistical non-inferiority statement 허용
- 그렇지 않으면 held-out generalization과 uncertainty reporting은 가능하지만 statistical non-inferiority claim은 불가

Preregistration의 illustrative precision 값은 design tradeoff를 기록하기 위한 것이며 B1/B2에서 fitting한 값이 아닙니다.

## Primary inference

Primary interval은 **stratified task-cluster bootstrap**을 사용합니다.

- unit: `semantic_task_id`
- strata: task type × language
- 78 cells
- 각 cell에서 task ID 10개 resample
- sampled task 내부 catalog repeat 유지
- 10,000 iterations
- seed 20260929
- 95% interval

이 방식은 benchmark의 balanced task/language population을 유지하면서 catalog-size pseudoreplication을 방지합니다.

## Claim gate

광범위한 SchemaRouter agent-utility claim에는 다음이 모두 필요합니다.

1. B2 strong-agent replication 확보
2. 동일 deployable SR condition이 held-out product gate 통과
3. required-tool-set retrieval >= 97%
4. tool-schema tokens <= FULL의 40%
5. total input tokens < FULL
6. unauthorized destructive execution = 0
7. FULL 대비 held-out paired 95% CI lower bound >= -2pp
8. context-reduction 방향이 Phase A, B1, B2와 일관됨

CI가 -2pp를 넘지 못하면 paper/README는 uncertainty를 보고해야 하며 engineering threshold를 statistical theorem으로 승격해서는 안 됩니다.

## B2-terminal 이전 authoring scaffold

B2가 terminal이 되기 전 deterministic scaffold를 준비할 수 있지만 **authoring slot**으로 제한합니다. 다음만 freeze합니다.

- 780 unique `semantic_task_id`
- ID당 하나의 preregistered task stratum
- ID당 하나의 preregistered language stratum
- 78 task-stratum × language cell 각각 독립 slot 10개

Scaffold에는 다음을 생성하거나 포함하지 않습니다.

- task/query wording
- required/gold route
- expected answer
- executor state 또는 deterministic tool output
- catalog 또는 candidate set
- score 또는 label

Generator는 `scripts/generate_agent_utility_v3_heldout_authoring_plan.py`입니다. B2는 현재 terminal이지만 실제 held-out content/inference는 #500 conveyor가 제어합니다. Manifest는 preregistered structural-K gate와 #431 corrective gate가 terminal이 된 뒤에만 freeze합니다. Structural K3 gate는 이미 terminal negative이고 #431은 active입니다.

## Corpus identity validation

생성된 corpus를 freeze/scoring하기 전에 authored row에 `scripts/validate_agent_utility_corpus_identity.py`를 실행합니다.

Validator는 이후 semantic scorer보다 범위가 좁으며 benchmark outcome에 의존해서는 안 되는 pre-scoring integrity만 강제합니다.

- 모든 preregistered authoring slot이 정확히 한 번 존재
- semantic task ID가 frozen slot plan과 일치
- task/answer stratum과 language assignment drift 금지
- query text non-empty
- normalized query text가 semantic task 간 unique
- freeze manifest용 stable identity/query-content SHA-256 출력

Validator는 content 생성/품질 승인/inference authorization/model outcome 검사를 하지 않습니다.

## 독립성 규칙

최종 780 task에서 금지:

- B1 task wording 또는 paraphrase
- B1 row-level failure
- B2 task outcome 또는 failure
- #434 DEV query
- post-scoring task deletion
- post-scoring prompt/K/representation tuning

모든 task text, executor state transition, deterministic output, catalog, candidate set, hash는 held-out inference 전에 freeze합니다.

## #424와의 경계

이 benchmark는 retrieval, tool use, execution state, efficiency, safety를 측정합니다. Final-answer factuality, unit correctness, provenance quality 자체를 확립하지는 않습니다. 해당 claim은 #424 범위입니다.
