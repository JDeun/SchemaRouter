# 0.14 large held-out agent-utility benchmark

Tracking issue: **#432**

This benchmark is the generalization layer after the controlled B1/B2 experiments.
It is intentionally frozen without using B1/B2 row-level outcomes.

## Why a new surface is required

B1/B2 reuse 23 semantic tasks across catalog-size repeats. That is appropriate for
mechanism replication, but the catalog repeats are repeated measures of the same task
and cannot be counted as independent samples.

The held-out benchmark therefore uses **780 independent semantic tasks**.

## Frozen population design

The 780 tasks are cross-balanced as:

- 13 task strata;
- 6 language strata;
- 10 independent semantic tasks per task-stratum × language cell.

This gives:

- 60 independent tasks per task stratum;
- 130 independent tasks per language;
- 780 total independent semantic tasks.

A task belongs to exactly one language stratum. The benchmark does **not** create six
translations of one semantic task and count those translations as independent tasks.

Task strata:

1. single-tool exact;
2. two-step state-dependent;
3. three-step state-dependent;
4. sibling-operation ambiguity;
5. typed numeric values and units;
6. identifier/provenance propagation;
7. read vs write siblings;
8. destructive vs non-destructive siblings;
9. insufficient information;
10. recoverable execution failure;
11. missing capability / unsupported;
12. semantically adjacent distractors;
13. genuine OOD.

Languages:

- English;
- Korean;
- Spanish;
- Japanese;
- German;
- realistic mixed-language identifiers/query text.

## Catalog scaling

Retrieval-only characterization uses nested catalogs of:

- 100;
- 250;
- 500;
- 1000 endpoints.

Downstream agent comparisons use:

- 100;
- 250;
- 500 endpoints.

The 1000-endpoint stratum is retained for retrieval scaling without forcing FULL into
a predictably infeasible context regime for many 65k-class agents.

Catalog repeats are nested inside `semantic_task_id`.

## Conditions

The held-out agent comparison freezes:

- FULL;
- SR-5;
- SR-10;
- SR-PROGRESSIVE;
- ORACLE.

No adaptive #430 policy was promoted. A later separately preregistered structural K3
candidate also failed its strong-agent K3-vs-K5 task-pass promotion gate, so K3 is not carried into
the held-out condition manifest. #431 state-aware corrective retrieval remains the active optional
condition gate before the manifest is frozen.

SchemaRouter ranking scores/positions remain hidden from the downstream agent.
Visible candidates are sorted lexicographically by registered route ID.

## Precision and the -2pp margin

The practical engineering margin remains **-2 percentage points** versus FULL.

The sample size is **not** chosen from observed B1 or B2 effects.

For a paired task-level difference bounded in [-1, 1], a conservative worst-case
normal-approximate 95% half-width is:

```text
1.96 / sqrt(n)
```

At `n = 780`, that worst-case half-width is about **7.02pp**.

A worst-case design guaranteed to have a 2pp half-width would require about
**9,604 independent semantic tasks**, which is not a practical downstream-agent
benchmark at the planned catalog/condition matrix.

Therefore:

- -2pp remains an engineering threshold;
- the preregistered task-cluster CI is reported without reinterpretation;
- a statistical non-inferiority statement is allowed only if the actual frozen
  paired 95% CI lower bound clears -2pp;
- otherwise the result may support held-out generalization and uncertainty reporting,
  but not a statistical non-inferiority claim.

Illustrative precision values are included in the preregistration only to document the
design tradeoff; they are not fitted from B1/B2.

## Primary inference

The primary interval uses a **stratified task-cluster bootstrap**:

- unit: `semantic_task_id`;
- strata: task type × language;
- 78 cells;
- resample 10 task IDs within each cell;
- preserve catalog repeats inside each sampled task;
- 10,000 iterations;
- seed 20260929;
- 95% interval.

This prevents catalog-size pseudoreplication while preserving the benchmark's balanced
task/language population.

## Claim gate

A broad SchemaRouter agent-utility claim requires all of the following:

1. B2 strong-agent replication is available;
2. the same deployable SR condition passes the held-out product gate;
3. required-tool-set retrieval remains at least 97%;
4. tool-schema tokens are at most 40% of FULL;
5. total input tokens are lower than FULL;
6. unauthorized destructive executions remain zero;
7. the held-out paired 95% CI lower bound versus FULL is at least -2pp;
8. context-reduction direction is consistent with Phase A, B1 and B2.

If the CI does not clear -2pp, the paper/README must report the uncertainty rather than
promote the engineering threshold into a statistical theorem.

## Pre-B2-terminal authoring scaffold

A deterministic scaffold may be prepared before B2 is terminal, but it is deliberately limited to
**authoring slots**. It freezes only:

- 780 unique `semantic_task_id` values;
- one preregistered task stratum per ID;
- one preregistered language stratum per ID;
- ten independent slots in each of the 78 task-stratum × language cells.

The scaffold does **not** generate or contain:

- task/query wording;
- required/gold routes;
- expected answers;
- executor states or deterministic tool outputs;
- catalogs or candidate sets;
- scores or labels.

The generator is `scripts/generate_agent_utility_v3_heldout_authoring_plan.py`. B2 is
now terminal; however actual held-out content/inference remains controlled by the #500 conveyor.
The manifest is frozen only after the preregistered structural-K gate and #431 corrective gate are
terminal. The structural K3 gate is already terminal negative; #431 remains active.


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

## Independence rules

The final 780 tasks may not use:

- B1 task wording or paraphrases;
- B1 row-level failures;
- B2 task outcomes or failures;
- #434 DEV queries;
- post-scoring task deletion;
- post-scoring prompt/K/representation tuning.

All task text, executor state transitions, deterministic outputs, catalogs, candidate
sets, and hashes are frozen before held-out inference.

## Boundary with #424

This benchmark measures retrieval, tool use, execution state, efficiency and safety.
It does not by itself establish final-answer factuality, unit correctness or provenance
quality. Those claims remain scoped to **#424**.
