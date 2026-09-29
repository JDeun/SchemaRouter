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
