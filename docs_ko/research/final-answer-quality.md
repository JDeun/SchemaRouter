# 0.14 final-answer quality benchmark

추적 이슈: #424

이 benchmark는 deterministic task completion과 분리합니다.

B1/B2의 질문:

> Agent가 필요한 tool을 선택하고 실행할 수 있는가?

#424의 질문:

> 해당 tool을 사용한 뒤 visible capability catalog를 줄여도 final answer의 factual quality, unit, provenance가 유지되는가?

## Run gate

B2는 terminal이지만 더 이상 그것만으로 최종 launch condition이 되지는 않습니다. 자동화된 #500 research conveyor에서 #424 answer inference는 **#432가 성공적으로 완료될 때까지 blocked**입니다. #432 자체도 terminal #431 corrective result와 frozen held-out condition manifest에 의해 gate됩니다.

이 순서를 우회해 #424를 수동 dispatch하지 않습니다.

Benchmark는 preregistered infrastructure-only feasibility rule이 달리 요구하지 않는 한 B2와 동일한 frozen strong-agent model family/runtime lineage를 유지합니다. Replacement는 #424 task outcome을 보고 선택할 수 없습니다.

## Authoring scaffold와 현재 gate

Benchmark는 model outcome과 독립적으로 deterministic **authoring slot**을 freeze합니다.

Scaffold가 고정하는 것:

- 144 unique `semantic_task_id`
- ID당 하나의 preregistered answer-task stratum
- ID당 하나의 preregistered language stratum
- 36 stratum × language cell 각각 독립 slot 4개

생성하거나 포함하지 않는 것:

- task/query wording
- gold/required route
- deterministic evidence payload 또는 tool output
- reference/forbidden fact
- numeric tolerance 또는 canonical unit
- provenance/source ID
- expected answer
- catalog, candidate set, score 또는 label

Generator는 `scripts/generate_agent_utility_v4_final_answer_authoring_plan.py`입니다. Authoring scaffold는 outcome-independent 상태를 유지합니다. Content generation과 answer inference는 B2 terminal state만이 아니라 현재 conveyor gate의 제어를 받으며 active launch boundary는 성공적인 terminal #432입니다.

## Surface

최종 benchmark는 **144개의 독립 semantic task**를 포함합니다.

- 6 answer task strata
- 6 language strata
- task-stratum × language cell당 독립 task 4개

각 semantic task는 하나의 language에만 속합니다.

Answer strata:

1. property value + unit + provenance
2. literature fact + source attribution
3. multi-source comparison
4. transform/export action 이후 status/provenance answer
5. corrective expansion required
6. distractor/contradiction resistance

Catalog size: 100, 250 endpoints.

Conditions: FULL, SR-5, SR-10, SR-PROGRESSIVE, ORACLE.

## Corpus identity validation

생성 corpus를 freeze/scoring하기 전에 authored row에 `scripts/validate_agent_utility_corpus_identity.py`를 실행합니다.

Validator는 이후 semantic scorer보다 좁은 범위에서 outcome-independent pre-scoring integrity만 강제합니다.

- preregistered authoring slot이 정확히 한 번씩 존재
- semantic task ID가 frozen slot plan과 일치
- task/answer stratum과 language assignment drift 금지
- query text non-empty
- normalized query text가 semantic task 간 unique
- freeze manifest용 stable identity/query-content SHA-256 출력

Content 생성/품질 승인/inference authorization/model outcome 검사는 하지 않습니다.

## Deterministic evidence

각 task에서 freeze하는 항목:

- deterministic tool evidence payload
- required reference fact
- 선택적 forbidden/contradictory fact
- 해당하는 경우 numeric tolerance
- canonical 또는 accepted convertible unit
- allowed provenance/source ID
- expected state transition

모든 condition은 정확히 동일한 tool output을 받습니다.

## Final answer contract

Evidence collection 뒤 agent는 하나의 machine-readable final envelope를 출력합니다.

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

Natural-language `answer`는 secondary coherence/completeness review용으로 보존하지만 deterministic scoring은 structured fact surface를 사용합니다.

Malformed final envelope는 evaluator가 repair하지 않고 answer failure로 처리합니다.

## Primary factual metrics

각각 별도로 보고합니다.

- required fact recall
- unsupported fact count/rate
- numeric value accuracy
- unit accuracy
- provenance accuracy
- contradiction count
- exact mandatory-field completion

Weighted score 하나로 합치지 않습니다.

Primary product gate의 deployable SchemaRouter condition은 모두 만족해야 합니다.

- fact recall >= FULL - 2pp
- numeric accuracy >= FULL - 2pp
- unit accuracy >= FULL - 2pp
- provenance accuracy >= FULL - 2pp
- unsupported-fact rate <= FULL + 1pp
- contradiction count <= FULL
- required evidence coverage >=97%
- total input tokens < FULL
- tool-schema tokens <= FULL의 40%
- unauthorized destructive executions = 0

## Secondary LLM judge

LLM judge는 선택적이며 secondary입니다.

사용한다면:

- condition-blinded answer를 봄
- coherence/completeness만 scoring
- evaluated answer를 열기 전에 prompt freeze
- deterministic factual metric을 override할 수 없음

## Statistics

Independent unit은 semantic task입니다. 두 catalog size는 task 내부의 repeated measure입니다.

Answer-task-stratum × language 기준 stratified task-cluster bootstrap:

- 36 cells
- cell당 독립 task 4개
- 10,000 iterations
- seed 20260929
- 95% interval

Language와 task-stratum 결과는 diagnostic으로 별도 보고합니다.

## Claim 경계

#424가 통과하면 frozen answer-bearing benchmark 범위에서 다음 claim만 허용합니다.

> 평가된 strong-agent surface에서 bounded SchemaRouter capability context는 capability context를 줄이면서 final-answer factual quality를 유지했습니다.

#424만으로 broad population generalization을 확립하지 않습니다. 그것은 #432가 필요합니다.
