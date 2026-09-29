# 0.14 final-answer quality benchmark

Tracking issue: **#424**

This benchmark is intentionally separate from deterministic task completion.

B1/B2 answer the question:

> Can the agent select and execute the required tools?

#424 asks:

> After using those tools, does reducing the visible capability catalog preserve the
> factual quality, units and provenance of the final answer?

## Run gate

The protocol may be frozen now, but answer inference is **not authorized** until #423
B2 is terminal.

The benchmark uses the same frozen strong-agent model family/runtime as B2 unless B2
terminates before benchmark inference for model-feasibility reasons. A replacement may
never be selected from #424 task outcomes.

## Pre-B2-terminal authoring scaffold

Before B2 is terminal, the benchmark may freeze only deterministic **authoring slots**.
The scaffold fixes:

- 144 unique `semantic_task_id` values;
- one preregistered answer-task stratum per ID;
- one preregistered language stratum per ID;
- four independent slots in each of the 36 stratum × language cells.

It does **not** generate or contain:

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
Both `content_generation_authorized` and `answer_inference_authorized` remain false
until #423 is terminal. This allows balance/identity bookkeeping to be validated without
using B2 outcomes or opening the answer benchmark early.

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

The validator is deliberately narrower than the later semantic scorer. It enforces only
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

## Corpus freeze validation

After #423 is terminal and the 144 answer-bearing tasks are authored, the corpus must pass
`scripts/validate_agent_utility_v4_final_answer_corpus.py` **before answer inference**.

The validator requires:

- exact equality with the frozen 144 authoring-slot IDs and stratum/language assignments;
- 144 unique normalized queries;
- frozen evidence payloads and allowed provenance/source IDs;
- non-empty required reference facts with unique keys;
- numeric tolerances for every numeric required fact;
- accepted-unit sets for every unit-bearing fact, including the canonical unit;
- provenance IDs that resolve to frozen evidence;
- explicit corrective-expansion contracts where the preregistered stratum requires them;
- exact 100/250 catalog hashes, candidate-set manifest hash and task-content hash.

A malformed or drifting corpus is rejected before inference rather than repaired after answers
are observed.

## Claim boundary

If #424 passes, the permitted claim is scoped to the frozen answer-bearing benchmark:

> Bounded SchemaRouter capability context preserved final-answer factual quality while
> reducing capability context on the evaluated strong-agent surface.

#424 alone does not establish broad population generalization. That requires #432.
