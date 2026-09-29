# 0.14 adaptive shortlist depth

Tracking issue: **#430**

This experiment asks whether SchemaRouter can expose **fewer than five capabilities on average**
without materially reducing required-route coverage or downstream task success.

The adaptive policy is frozen before B2 outcomes are used.

## Why not use an absolute score threshold?

SchemaRouter's deterministic retrieval score is additive and component-driven. Preferred endpoint/tool
signals carry much larger weights than ordinary lexical/field matches, so one absolute cutoff is not
assumed to be calibrated across unrelated queries.

The first adaptive policy therefore uses only the **shape of the ranked Top-10 score sequence**.

## Frozen policy: largest-adjacent-gap-v1

For each query:

1. retrieve the internal ranked Top-10 candidate pool;
2. require finite, non-increasing scores;
3. compute every adjacent score drop;
4. if every drop is zero, keep the full available Top-10;
5. otherwise cut at the largest adjacent drop;
6. if several gaps tie for largest, use the **later** cut to favor recall;
7. clamp the final depth to **K=3..10**.

There is:

- no learned depth model;
- no absolute score threshold;
- no threshold sweep;
- no tuning from B1/B2 failed rows.

The downstream agent still does **not** see retrieval scores or rank positions. After the prefix is
selected, visible capabilities follow the same lexicographic route-ID ordering as the fixed B2
conditions.

Adaptive K changes candidate exposure only. It cannot grant execution authority.

## Execution gate

Downstream adaptive scoring is blocked until #423 is terminal.

When authorized, use:

- the same 23 canonical B2 semantic tasks;
- catalogs 20 / 50 / 100 / 250;
- the same frozen strong-agent model/runtime;
- the same task executor and safety policy.

Compare:

- FULL;
- fixed SR-3;
- fixed SR-5;
- fixed SR-10;
- SR-ADAPTIVE-ELBOW;
- ORACLE.

This is an engineering promotion experiment on the controlled B2 surface, not a broad population
claim.

## Promotion into #432

SR-ADAPTIVE-ELBOW may be added to the large held-out benchmark only if **all** frozen gates pass:

- required-tool-set recall >= 97%;
- task-pass delta versus SR-5 >= -2pp;
- mean exposed candidate count < 5;
- mean tool-schema tokens < SR-5;
- total input tokens <= SR-5;
- unauthorized destructive executions = 0;
- execution-policy integrity = 100%.

If any gate fails, #432 keeps its already-preregistered fixed conditions and the adaptive result is
retained as negative/neutral evidence.

No policy edit is allowed after B2/adaptive results are opened.
