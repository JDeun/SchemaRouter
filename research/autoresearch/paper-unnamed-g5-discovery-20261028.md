# Host-opt-in unnamed native G5 graph discovery (Algorithm 1 E0)

Date: 2026-10-28. Issue #1801, stacked after Draft #1800.

## Gap and chosen scope

The source-native G5 index proves authorized typed one-/two-hop routes and the owner-pinned Rank can deterministically choose complete DAGs, but the public `compile_understood` and `acompile_query` pathways only search dependencies when an untrusted model returns an explicit `named_tools` value. Direct `requires_arguments` receipts therefore hide an available owner-approved typed dependency path whenever the model doesn't know the destination tool name.

## Design

Expose host-only `allow_unnamed_graph_discovery: bool = False` through `SchemaFieldRoutingSession.compile_understood`, async `acompile_query`, `compile_model_query` and the underlying graph compiler. Opt-in **requires** a current source-snapshot-pinned `PaperNativeRankPolicy`. It is NEVER copied to model prompts/outputs; the model still selects only reviewed intent/concept IDs.

When no named tools were selected, and direct completion is `requires_arguments` or `no_proven_hit`, **only if the host opted in**:
1. Get eligible target route IDs from the intersection of existing indexed semantic postings for all owner-reviewed required fields, intersected with the canonical native G5 consumer routes. Do not traverse the entire tool catalog.
2. Project current principal authorization, read-only/non-destructive, source type and licence, availability and visible typed required-field constraints **before** the 5,000-target bound. Never publish hidden targets or private counts.
3. Delegate actual path existence, typed join and full route authorization to the existing `NativeSchemaGraphIndex.lookup` and `lookup_two_hop` with the owner Rank policy. Do not invent bindings, call providers or grant execution.
4. Return exactly one ranked and fully materialized non-executable DAG, with prior current-source/policy/mutation reattestation. If no graph is proven, return the original safe incomplete direct receipt. On overflow return empty `budget_unsatisfied` (never partial paths).

Existing model-named routes and all default invocations remain behavior-identical. Same-source original rank policy, G5 K5 cap and security checks are reused.

## TDD and verification

RED tests assert opt-in unnamed 1-/2-hop success, deterministic 33-route selection despite the five-name LLM cap, lack of model prompt tool ID disclosure, no-policy rejection before model callback, and hidden/denied-root refusal. Run targeted GitHub CI to witness initial failures. GREEN implementation follows, plus Ruff/Pyright, graph/async tests, entire Python 3.12 suite, and existing source graph/scope regression checks.

## Gates

Only source-owned E0 structure is established; no E2 correctness, provider integration quality, default promotion or release gate change. #1356 remains hard hold.
