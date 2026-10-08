# 0.14 final-answer quality benchmark

추적 issue: #424

이 benchmark는 deterministic task completion과 분리해 유지합니다.

B1/B2는 다음 질문에 답합니다:

> Agent가 필요한 tool을 선택하고 실행할 수 있는가?

#424 asks:

> 해당 tool을 사용한 뒤 visible capability catalog를 줄여도 final answer의 factual quality, unit 및 provenance가 유지되는가?

## 실행 gate

B2는 현재 terminal 상태지만 더 이상 이것만으로 final launch condition이 충족되지는 않습니다. Under the automated
#500 research conveyor, #424 answer inference remains **blocked until #432 finishes
successfully**. #432 itself is gated by the terminal #431 corrective result and the frozen
held-out condition manifest.

해당 sequence를 우회해 #424를 수동 dispatch하지 않습니다.

The benchmark keeps the same frozen strong-agent model family/runtime lineage as B2 unless a
preregistered infrastructure-only feasibility rule requires otherwise. A replacement may never be
selected from #424 task outcomes.

## Authoring scaffold 및 현재 gate

Benchmark는 model outcome과 독립적으로 deterministic **authoring slot**을 freeze합니다.
Scaffold는 다음을 고정합니다:

- 144 unique `semantic_task_id` values;
- one preregistered answer-task stratum per ID;
- one preregistered language stratum per ID;
- four independent slots in each of the 36 stratum × language cells.

다음 항목은 생성하거나 포함하지 **않습니다**:

- task/query wording;
- gold/required routes;
- deterministic evidence payloads or tool outputs;
- reference/forbidden facts;
- numeric tolerances or canonical units;
- provenance/source IDs;
- expected answers;
- catalogs, candidate sets, scores or labels.

The generator is
`scripts/generate_agent_utility_v4_final_answer_authoring_plan.py`.
The authoring scaffold remains outcome-independent. Content generation and answer inference are
controlled by the current conveyor gate rather than by B2 terminal state alone; the active launch
boundary is successful terminal #432.

## Surface

The final benchmark contains **144 independent semantic tasks**:

- 6 answer task strata;
- 6 language strata;
- 4 independent tasks per task-stratum × language cell.

Each semantic task belongs to one language only.

Answer strata:

1. property value + unit + provenance;
2. literature fact + source attribution;
3. multi-source comparison;
4. transform/export action followed by status/provenance answer;
5. corrective expansion required;
6. distractor/contradiction resistance.

Catalog sizes:

- 100 endpoints;
- 250 endpoints.

Conditions:

- FULL;
- SR-5;
- SR-10;
- SR-PROGRESSIVE;
- ORACLE.


## Corpus identity validation

Before any generated corpus can be frozen or scored, run
`scripts/validate_agent_utility_corpus_identity.py` against the authored rows.

The validator is narrower than the later semantic scorer. It enforces only
pre-scoring integrity that must not depend on benchmark outcomes:

- every preregistered authoring slot appears exactly once;
- semantic task IDs match the frozen slot plan;
- task/answer stratum and language assignments cannot drift;
- query text must be non-empty;
- normalized query text must be unique across semantic tasks;
- stable identity/query-content SHA-256 values are emitted for the freeze manifest.

The validator does **not** generate content, approve content quality, authorize inference,
or inspect model outcomes.

## Deterministic evidence

Every task freezes:

- deterministic tool evidence payloads;
- required reference facts;
- optional forbidden/contradictory facts;
- numeric tolerances where applicable;
- canonical or accepted convertible units;
- allowed provenance/source IDs;
- expected state transitions.

All conditions receive exactly the same tool outputs.

## Final answer contract

After evidence collection, the agent emits one machine-readable final envelope:

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

The natural-language `answer` is retained for secondary coherence/completeness review,
but deterministic scoring uses the structured fact surface.

A malformed final envelope is an answer failure rather than something repaired by the
evaluator.

## Primary factual metrics

Report separately:

- required fact recall;
- unsupported fact count and rate;
- numeric value accuracy;
- unit accuracy;
- provenance accuracy;
- contradiction count;
- exact mandatory-field completion.

Do not collapse these into a weighted score.

The primary product gate requires a deployable SchemaRouter condition to satisfy all of:

- fact recall >= FULL - 2pp;
- numeric accuracy >= FULL - 2pp;
- unit accuracy >= FULL - 2pp;
- provenance accuracy >= FULL - 2pp;
- unsupported-fact rate <= FULL + 1pp;
- contradiction count no greater than FULL;
- required evidence coverage >=97%;
- total input tokens < FULL;
- tool-schema tokens <=40% of FULL;
- unauthorized destructive executions = 0.

## Secondary LLM judge

An LLM judge is optional and secondary.

If used:

- it sees condition-blinded answers;
- it scores coherence/completeness only;
- its prompt is frozen before evaluated answers are opened;
- it cannot override deterministic factual metrics.

## Statistics

The semantic task is the independent unit.

The two catalog sizes are repeated measures nested inside task.

Use a stratified task-cluster bootstrap over answer-task-stratum × language:

- 36 cells;
- 4 independent tasks per cell;
- 10,000 iterations;
- seed 20260929;
- 95% interval.

Report language and task-stratum results separately as diagnostics.

## Claim boundary

If #424 passes, the permitted claim is scoped to the frozen answer-bearing benchmark:

> Bounded SchemaRouter capability context preserved final-answer factual quality while
> reducing capability context on the evaluated strong-agent surface.

#424 alone does not establish broad population generalization. That requires #432.
