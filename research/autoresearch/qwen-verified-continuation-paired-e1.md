# Preregistered paired Qwen continuation pilot — source-native E1 DEV only

## Motivation and hypothesis (before executing this new paired study)

Original pinned Qwen3-0.6B + actual Open-Meteo E1 was observed to issue
premature finals after a validated geocoding call on disclosed EN/KO/JA tasks.
Merged #1647 demonstrated only scripted-model/no-provider E0 feasibility:
a single host-owned reminder can ask the model to select weather itself.
That E0 test did not establish Qwen recovery or independent E2 quality.

**Hypothesis:** after exactly one host-verified geocoding observation and an
early final, one bounded model continuation can improve strict actual-source
end-task pass without automatically dispatching a native weather tool.
The null is no such benefit. This is exploratory because the cases and
failure mode have already been seen by the author; never present as heldout
or causal, generalizable model improvement.

## Locked pilot protocol

- Same source tasks: existing original 3-case EN/KO/JA Open-Meteo E1 set,
  no generated rephrasings, no case exclusion, no gold-aware prompts.
- Same Qwen3-0.6B revision c1899de289a04d12100db370d81485cdf75e47ca,
  greedy inference and existing 4-turn cap.
- Same existing evaluate_one, native source invocation, principal, strict
  source result/final JSON/value/unit/time match oracle and router.
- Fixed **state_ready** native menu for both arms: **original** reminder budget
  0 vs **one_verified_reminder** budget 1. Original remains the current
  product/research default; this script is strictly opt-in and separate.
- Exactly one transport retry allowance per native GET for both arms;
  at most 2 native routes × (initial + retry) × 6 episodes = **24 provider
  HTTPS attempts** total; no extra search, provider, mutation or secrets.
- EN baseline first, KO opt-in first, JA baseline first. Each arm independently
  reobserves live public weather, so timestamps/provider failures are
  not matched snapshots and may confound apparent differences.
- Primary descriptive outcome: **strict source-grounded complete tasks / 3**
  per arm; keep wrong calls, missed weather, provider failures and bad finals
  as failures. Include actual native HTTPS attempts, model turn counts, actual
  returned input/tool/output token counts, observed generation ms, episode wall
  time and peak process RSS. No invented metrics, zero-filled missing usage,
  fabricated provider observation or forbidden early host weather call.
- No post-hoc confidence claim or significance test with n=3. Preserve all
  individual language failures and their privacy-safe stop categories. Any
  source outage stays observed and must not be relabeled as routing uplift.
- CI runs the no-provider bookkeeping/fail-closed guard first, then a separate
  real pinned CPU Qwen/public-provider E1 with exact code+model provenance.
  Green CI is not a positive study result: inspect published artifact rows.

## Required limitations

This pilot has no independent task author, source snapshot, provider/permission
gold, source-native EN/KO/JA heldout, OOD/unsafe cases, release gate, calibrated
no-fit or independent full-pipeline #1477 E2. No change to the frozen negative
#432 comparison (SR-5 29.19%, FULL 49.62%, ORACLE 70.98%). The #1346 external
intake gate, #1339 multilingual generalization and #1356 v0.18 **HARD HOLD**
remain OPEN. Even an apparent 3/3 improvement on disclosed cases is not
commercially validated routing or autonomously correct multi-hop execution.
