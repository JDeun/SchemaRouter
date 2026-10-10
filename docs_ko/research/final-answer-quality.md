# 0.14 final-answer quality benchmark

Tracking issue: #424

이 benchmark는 deterministic task completion과 분리합니다.

B1/B2는 “agent가 required tool을 선택하고 실행할 수 있는가?”를 묻고, #424는 “tool 사용 후 visible capability catalog를 줄여도 final answer의 factual quality, unit, provenance가 보존되는가?”를 묻습니다.

## Run gate

B2는 terminal이지만 더 이상 최종 launch condition은 아닙니다. Automated #500 research conveyor 아래에서 #424 answer inference는 **#432가 성공적으로 끝날 때까지 blocked**입니다. #432 자체도 terminal #431 corrective result와 frozen held-out condition manifest에 gated됩니다.

이 순서를 우회해 #424를 manual dispatch하지 않습니다.

Benchmark는 preregistered infrastructure-only feasibility rule이 필요하지 않는 한 B2와 동일한 frozen strong-agent model family/runtime lineage를 유지합니다. Replacement를 #424 task outcome으로 선택할 수 없습니다.

## Authoring scaffold와 현재 gate

Model outcome과 독립적으로 deterministic **authoring slot**을 동결합니다.

- unique `semantic_task_id` 144개
- ID당 preregistered answer-task stratum 하나
- ID당 preregistered language stratum 하나
- 36개 stratum × language cell 각각 independent slot 4개

다음은 생성하거나 포함하지 않습니다.

- task/query wording
- gold/required route
- deterministic evidence payload/tool output
- reference/forbidden fact
- numeric tolerance/canonical unit
- provenance/source ID
- expected answer
- catalog/candidate set/score/label

Generator는 `scripts/generate_agent_utility_v4_final_answer_authoring_plan.py`입니다. Authoring scaffold는 outcome-independent이며 content generation과 answer inference는 B2 terminal만이 아니라 current conveyor gate가 통제합니다. Active launch boundary는 successful terminal #432입니다.

## Surface

최종 benchmark는 **144개의 independent semantic task**입니다.

- answer task strata 6개
- language strata 6개
- task-stratum × language cell당 independent task 4개

각 semantic task는 하나의 language에만 속합니다.

Answer strata:

1. property value + unit + provenance
2. literature fact + source attribution
3. multi-source comparison
4. transform/export action 후 status/provenance answer
5. corrective expansion required
6. distractor/contradiction resistance

Catalog: 100, 250 endpoints.

Conditions: FULL, SR-5, SR-10, SR-PROGRESSIVE, ORACLE.

## Corpus identity validation

Generated corpus를 freeze/score하기 전에 authored row에 `scripts/validate_agent_utility_corpus_identity.py`를 실행합니다.

Validator는 이후 semantic scorer보다 좁으며 benchmark outcome에 의존하지 않는 pre-scoring integrity만 강제합니다.

- preregistered authoring slot이 정확히 한 번 존재
- semantic task ID가 frozen slot plan과 일치
- task/answer stratum 및 language assignment drift 금지
- query text non-empty
- normalized query text가 semantic task 사이 unique
- freeze manifest용 stable identity/query-content SHA-256 출력

Content 생성/품질 승인/inference authorization/model outcome 검사는 하지 않습니다.

## Deterministic evidence

모든 task는 다음을 동결합니다.

- deterministic tool evidence payload
- required reference fact
- optional forbidden/contradictory fact
- 해당 시 numeric tolerance
- canonical 또는 accepted convertible unit
- allowed provenance/source ID
- expected state transition

모든 condition은 정확히 동일한 tool output을 받습니다.

## Final answer contract

Evidence collection 뒤 agent는 하나의 machine-readable envelope를 냅니다.

```json
{
  "answer": "natural-language answer text",
  "facts": [
    {
      "key": "elastic_modulus",
      "value": 117.4,
      "unit": "GPa",
      "source_id": "materials.current:MAT-7"
    }
  ],
  "sources": ["materials.current:MAT-7"]
}
```

Natural-language `answer`는 secondary coherence/completeness review용으로 유지하지만 deterministic scoring은 structured fact surface를 사용합니다. Malformed envelope는 evaluator가 수리하지 않고 answer failure입니다.

## Primary factual metrics

별도로 보고합니다.

- required fact recall
- unsupported fact count/rate
- numeric value accuracy
- unit accuracy
- provenance accuracy
- contradiction count
- exact mandatory-field completion

Weighted score로 합치지 않습니다.

Primary product gate는 deployable SchemaRouter condition이 모두 만족해야 합니다.

- fact recall >= FULL - 2pp
- numeric accuracy >= FULL - 2pp
- unit accuracy >= FULL - 2pp
- provenance accuracy >= FULL - 2pp
- unsupported-fact rate <= FULL + 1pp
- contradiction count <= FULL
- required evidence coverage >=97%
- total input tokens < FULL
- tool-schema tokens <=40% of FULL
- unauthorized destructive executions = 0

## Secondary LLM judge

Optional secondary metric입니다. 사용 시 condition-blinded answer만 보고 coherence/completeness만 평가하며 prompt는 evaluated answer를 열기 전에 동결합니다. Deterministic factual metric을 override할 수 없습니다.

## Statistics

Independent unit은 semantic task이며 두 catalog size는 task 내부 repeated measure입니다.

Answer-task-stratum × language에 stratified task-cluster bootstrap을 적용합니다.

- 36 cells
- cell당 independent task 4개
- 10,000 iterations
- seed 20260929
- 95% interval

Language와 task-stratum 결과도 diagnostic으로 별도 보고합니다.

## Claim boundary

이슈 #424가 통과할 경우 허용되는 주장은 frozen answer-bearing benchmark 범위입니다.

> 평가된 strong-agent surface에서 bounded SchemaRouter capability context가 capability context를 줄이면서 final-answer factual quality를 보존했습니다.

이슈 #424만으로 broad population generalization을 확립하지 않습니다. 그 역할은 #432입니다.
