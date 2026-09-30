# 0.14 adaptive capability shortlist depth

## Terminal research status — 2026-09-30

The original **score-gap adaptive-depth** hypothesis is closed without a selected adaptive policy.
The current evidence supports a different conclusion: first repair large-catalog structural retrieval,
then use a small **fixed** shortlist.

### Evidence sequence

1. On the fresh 240-task adaptive DEV surface, the baseline fixed Top-10 retriever degraded as the
   registry grew. Required-route Recall@10 was **97.62% / 96.67% / 87.14%** at
   100 / 250 / 500 endpoints.
2. Miss diagnosis localized the 500-endpoint failures to both equal-score collisions and true
   below-cutoff ranking errors. This motivated a structural retrieval successor rather than
   post-hoc adaptive-K threshold changes.
3. The fixed structural candidate `STRUCT-4.5-1.5` was frozen before confirmation and passed an
   independent 240-task surface with **100% Recall@10 and 100% FullCoverage@10** at
   100 / 250 / 500 endpoints, including every supported stratum/language and typed-unit queries.
4. The unchanged preregistered score-gap adaptive family was then rerun over that confirmed
   retriever. **No adaptive policy met the frozen efficiency gates**, so adaptive v3 was closed
   without threshold retuning.
5. Fixed K=3, which had been a control rather than an adaptive candidate, motivated a separate
   preregistered successor. On a second fresh 240-task confirmation surface, `STRUCT-FIXED-3`
   achieved:
   - required-route Recall: **100.00% / 99.05% / 99.05%**;
   - all-required FullCoverage: **100.00% / 98.89% / 98.89%**;
   - typed numeric/unit Recall: **100%**;
   - mean exact SmolLM3 tool-schema tokens: **364.27**, versus **563.08** for fixed K=5;
   - mean schema-token reduction versus fixed K=5: **35.31%**.
6. The remaining gate is downstream agent utility. The paired
   `STRUCT-FIXED-3` vs `STRUCT-FIXED-5` SmolLM3 experiment is already preregistered on the exact
   canonical B2 surface and may launch only after canonical B2 run `36642658406` completes
   **successfully**.

Product defaults remain unchanged. `structural_retrieval` is opt-in, fixed K=3 is not a product
default, and broad #432 held-out/final-answer claims remain separate gates.

Canonical result files:

- `benchmarks/agent-utility-v5-structural-confirmation-result.json`
- `benchmarks/agent-utility-v5-structural-adaptive-v3-result.json`
- `benchmarks/agent-utility-v5-structural-fixed3-v4-result.json`
- `benchmarks/agent-utility-v5-structural-fixed3-agent-preregistration.json`

## Historical protocol

The sections below preserve the original adaptive-depth preregistration rationale and selection
rules. They should be read as the protocol that produced the terminal negative adaptive result,
not as the current recommended candidate.

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

The only adaptive signal is an adjacent gap normalized by the score range of the already ranked
Top-10 list:

```text
gap_i = (score_i - score_{i+1}) /
        max(score_1 - score_10, 1e-9)
```

This quantity is invariant to any positive affine score transform
`score' = a * score + b` where `a > 0`. That matters because a ranking backend may preserve the
same ordering while changing score scale or offset. If the Top-10 score range is effectively zero,
the rule fails closed to `max_k`.

Evaluated cut positions are ranks 3 through 9.

## Prior-art boundary

Repantis et al., *How Many Tools Should an LLM Agent See? A Chance-Corrected Answer*
(arXiv:2605.24660), treats shortlist depth itself as an evaluation target and introduces
Bits-over-Random (BoR) to correct success for the random chance introduced by larger K.

This cycle reports fixed-K BoR as a diagnostic, but **does not** use BoR as an inference signal,
selection criterion, or learned depth-policy reward. The frozen adaptive candidates remain
deterministic score-geometry rules. This keeps the current experiment training-free while making
the fixed-depth comparison easier to interpret.

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

Language rendering policy:

- each semantic task appears in exactly one language cell;
- surrounding request grammar is written in the assigned language;
- canonical scientific/tooling terms such as `Raman peak`, units, and registered
  operation nouns may remain in English where that is normal technical usage;
- this surface therefore tests adaptive shortlist depth under multilingual request
  framing, not standalone translation quality;
- no cross-language translations of the same DEV task are used as repeated rows.

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

- required-tool-set Recall >= 97% at each of 100/250/500 endpoints;
- all-required FullCoverage >= 97% at each of 100/250/500 endpoints;
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
FullCoverage independently at each catalog size, average no more than 4.5 candidates,
reduce tool-schema tokens relative to fixed K=5,
and — after B2 is terminal — preserve downstream task pass within 2 percentage points of fixed K=5
with zero unauthorized destructive execution.

An adaptive condition may enter #432 only if this confirmation gate passes **before any #432 task
content is generated**. It may never be added after held-out content or scores are opened.

## Boundary

Adaptive depth changes candidate exposure only. It never changes execution authority, validation,
approval, policy, or tool bindings.
