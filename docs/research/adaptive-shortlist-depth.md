# 0.14 adaptive capability shortlist depth

Tracking issue: **#430**

This experiment asks whether SchemaRouter can expose fewer than five candidate capabilities on
average without sacrificing the retrieval coverage and downstream utility established by the
fixed-K baselines.

## Why this is separate from B1/B2

B1/B2 evaluate fixed shortlist depths. They are not tuning data for adaptive depth.

No B1/B2 task rows, failures, scores, or per-task outcomes may be used to select an adaptive rule.

The adaptive experiment therefore uses its own development and confirmation surfaces.

## Score semantics

`CapabilityCandidate.score` is a deterministic ranking score, not a calibrated probability that is
guaranteed to have the same scale across backends or catalogs.

For that reason this protocol forbids absolute score thresholds.

The only adaptive signal is a scale-invariant adjacent relative gap within the already ranked
Top-10 list:

```text
gap_i = (score_i - score_{i+1}) /
        max(abs(score_i), abs(score_{i+1}), 1e-9)
```

Evaluated cut positions are ranks 3 through 9.

## Frozen candidate policies

Controls:

- fixed K=3;
- fixed K=5;
- fixed K=10.

Adaptive candidates:

- REL-GAP-005;
- REL-GAP-010;
- REL-GAP-020;
- MAX-GAP-010.

No learned depth policy is allowed in this cycle.

## Development surface

The tuning-eligible development surface contains **240 independent semantic tasks**:

- 8 task strata;
- 6 languages;
- 5 tasks per stratum × language cell.

Task strata cover:

1. clear single-tool requests;
2. sibling-operation ambiguity;
3. semantically adjacent distractors;
4. multi-step first-hop selection;
5. typed numeric/unit queries;
6. read/write siblings;
7. near-domain unsupported requests;
8. genuine OOD requests.

A separate **240-task confirmation surface** has the same balance but remains sealed until exactly one
adaptive policy is selected.

## Development selection

An adaptive policy is eligible only if it satisfies all of:

- required-tool-set Recall >= 97%;
- all-required FullCoverage >= 97%;
- mean exposed candidate count < 5;
- p95 exposed candidate count <= 10;
- mean tool-schema tokens < fixed K=5.

Among eligible policies, select exactly one by the frozen lexicographic rule:

1. lowest mean candidate count;
2. highest required-tool-set Recall;
3. highest FullCoverage;
4. lowest tool-schema tokens;
5. lowest p95 retrieval latency;
6. lexicographically smallest policy ID.

There is no post-selection threshold retuning.

## Confirmation and held-out promotion

The confirmation surface is not tuning eligible.

For promotion, the selected adaptive policy must retain >=97% required-tool coverage and
FullCoverage, average no more than 4.5 candidates, reduce tool-schema tokens relative to fixed K=5,
and — after B2 is terminal — preserve downstream task pass within 2 percentage points of fixed K=5
with zero unauthorized destructive execution.

An adaptive condition may enter #432 only if this confirmation gate passes **before any #432 task
content is generated**. It may never be added after held-out content or scores are opened.

## Boundary

Adaptive depth changes candidate exposure only. It never changes execution authority, validation,
approval, policy, or tool bindings.
