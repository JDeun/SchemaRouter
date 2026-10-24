# Native Direct Indexed K5 — DecisionBackend and Paired E0

Date: 2026-10-25. Paper Algorithm 1 issue #1560. This is stacked research
on #1749 (source-index K5 callback) → #1748 (typed original-paper plans)
→ #1746 (required-field union).

## Goal

Close the gap between the source-authorized NativeSchemaPostingIndex research
callback and the EXISTING model-neutral schemarouter.decisions.DecisionBackend.
Avoid creating a second inference API, route classifier, executor, auth bypass
or relevance ground truth.

## Implemented integration

- scripts/research_native_posting_decision_ranker_e0.py converts a bounded
  6–32 original source-attested direct candidate receipt into a DecisionRequest.
  The model sees the original query, opaque decision IDs, currently
  principal-visible route labels and required output field names.
  Identical field descriptions may be omitted to reduce input bytes.
- The request declares fixed K5, no execution authority, no calibrated no-fit,
  no independent quality evidence. The serialized prompt has a hard **16 KiB**
  cap. Existing choose_sync validates typed results; exactly 5 choices map
  back to offsets of the original candidate snapshot or the backend explicitly
  abstains. Forged, partial, duplicate and over-K results fail closed.
  No lexical fill or fallback on a failed/partial model.
- NativeSchemaPostingIndex.lookup still owns pre- and post-callback original
  registered fingerprints, policy, principal, live availability, hidden field
  scope, typed completeness and source witness. Default >K5 behavior is
  unchanged; >32 never invokes a model.
- This adapter is NOT a fitted ranking policy. A genuine pretrained backend
  and independently scored tasks are needed to determine quality.

## Paired E0 smoke experiment

scripts/benchmark_native_posting_ranked_k5_e0.py REUSES the existing
500/5000 source-native catalogue fixture, source oracle, EN/KO/JA concept
aliases, and wall/CPU percentile helper from
scripts/benchmark_indexed_concept_direct_parity_e0.py.

The predefined 18 synthetic test queries = 3 languages × 6 target routes.
**Every query includes the exact expected route name**, for example:
"case status direct_case_5". An intentionally simple CallableDecisionBackend
matches the literal query label among six already authorized source routes,
then emits four remaining choices. It does not read scorer gold or registry,
but the task is inherently co-designed with the answer. This checks the
connection of the backend to source-safe K5, not semantic retrieval quality.

For each query, use identical index, registry, principal and policy:
1. Native-index default: over_k_unranked, with no candidates.
2. Scorer-only fixed-first-five source ordering: 15/18 artificial exposure.
3. Source-scoped DecisionBackend K5: 18/18 artificial name-match exposure.

Paired timed baseline/ranker calls report process CPU and wall p50/p95/p99
by arm, model input byte ceiling, source count and explicit safety scenarios
(one authorized, zero authorized, field hidden, restricted availability).
**18/18 is NOT an independently validated Recall@5**: no actual model,
OPTIMADE provider, token-metered inference, authored holdout, final answer
or tool execution takes place. Do not promote measured paired microbenchmarks
to a product-wide latency or model-quality claim.

## Reproduction

- Focused: python -m pytest -q tests/test_research_native_posting_decision_ranker_e0.py tests/test_benchmark_native_posting_ranked_k5_e0.py
- 500 routes: python -m scripts.benchmark_native_posting_ranked_k5_e0 --registered-routes 500 --iterations 3
- 5000 routes (manual and potentially slow): python -m scripts.benchmark_native_posting_ranked_k5_e0 --registered-routes 5000 --iterations 3
- CI: .github/workflows/native-direct-index-decision-k5-e0.yml (exact PR HEAD).

## Next high-value investigation

1. Connect a PINNED actual pretrained multilingual embedding backend already
   used in G5 E5 probes to the same source-proven direct K5 callback.
   Preregister model revision, hardware, input byte/tokens and compare
   default, lexical, E5, hybrid RRF and typed model under identical scopes.
   Explicit backend failures must never silently fall back to lexical.
2. Independently authored hidden EN/KO/JA + OOD route, argument and field
   gold (#1346), paired external agent executor (#1477) and genuine Recall@5,
   MRR, NDCG, agent completion, provenance and cost evidence.
   Legacy AutoRAG definitions are related-work hints (#1750), NOT gold.
3. Linux p50/p95/p99 end-to-end resource/performance and a method for
   >32 complete and permitted candidates, where current E0 abstains.

Release #1356 remains HARD HOLD. Do not merge or change default based on
this E0 synthetic fixture or call literal-name matching model generalization.
