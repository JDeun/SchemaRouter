# #1473 — Bounded authorized semantic retrieval diagnostic (E0/E1 only)

## Why this exists

Public `SchemaRouter.retrieve()` and `aretrieve()` intentionally produce a
deterministic lexical/typed source-visible catalog and do **not** call the
optional model candidate-recall backend. That is a tested stability contract,
not a model installation bug. The product still lacks demonstrated KO/JA
transfer for English-only tool descriptions. Historical frozen #432 initial
KO/JA 0/160 and poor full agent task-success remain unmodified.

An actual pinned `intfloat/multilingual-e5-small` on 12 original ServiceNow
readonly MCP tools (20 supported + 4 unsupported old English DEV queries) gave
strict K5 lexical 17/20, E5 15/20, and 4/4 negative tasks with nonempty
lists. Retrospective union reached 19/20 only at **variable** width 5–9,
mean 7.17 tools and 36% more source canonical schema bytes. That is a
post-hoc non-equivalent diagnostic, **not** a validated new routing method.

## Opt-in prototype, not a product feature

`scripts/research_bounded_authorized_semantic_diagnostic.py` defines one
explicit host-requested, read-only `propose_bounded_semantic_shortlist`.
Nothing automatically attaches to the default public API, planner, agent
or executor. Callers must supply a host-trusted `PrincipalContext`, an
already registered `SchemaRouter` and a decision backend explicitly.

Sequence:
1. Check the request's fixed `k` (1–16), physical source cap (at most 500)
   and explicit serialized model-input cap (at most 1 MiB).
2. Record live registry identity/version, authorization policy identity and
   local availability predicate identity; use `retrieve_authorized` with
   an upper bound equal to all registered source routes. Require the returned
   positively scored source catalog to be complete and route IDs unique.
3. Form a bounded `DecisionRequest` of **only the already returned,
   principal-visible source route IDs**, tool/operation labels and data-scoped
   **visible** output-field names. Under any configured data-scope policy,
   **exclude unstructured tool/endpoint descriptions entirely**, as publisher
   free text may itself contain hidden field names; the semantic quality
   tradeoff is not quantified. Do not serialize hidden output schemas or
   registered secrets to the model. The raw query stays unchanged for EN,
   KO, JA or other languages.
4. Pass the fixed-K choice to `choose_sync`, which independently validates
   option IDs, maximum selections and malformed model output. Recheck the
   original authority witness **after** model inference. Source changes fail.
5. Return only `DiagnosticSemanticShortlist`, carrying source IDs and
   original tool/endpoint fingerprints and ALWAYS
   `independent_quality_evidence=False`, `calibrated_no_fit=False`,
   `executable_authority=False`. A backend abstention is explicitly
   *not* evidence the task is unsupported. Fewer than K choices is a
   partial-unverified result, not a full-K result.

This is NOT globally atomic under ABA same-object swaps or internal mutable
policy edits. A maximum physical publisher catalog size is deliberately
conservative and may decline safe huge installations, rather than compute
an index-free unrestricted dense input. No user query, backend choice,
description, relevance score or model confidence establishes permission to
execute anything. The function cannot issue `ToolCall` or invoke a provider.

## Qualification and research limitation

Offline tests use synthetic English, Korean and Japanese strings solely to
check unchanged query passing, visible-only candidate options, no-action,
fixed-K, external/duplicate IDs, backend abstention, resource caps, and
authority revocation during model inference. **They do not test whether a real
model understands these languages or makes correct native choices.**

This prototype requires independent publisher-approved *fresh task and gold*
source intake, prospective fixed-K/serialized bytes and CPU p95 budgets,
unsupported/no-fit false accepts, field/operation validity, and paired
agent downstream completion before considering a separate reviewed opt-in
product API. A backend cannot be promoted based on these synthetic controls
or the already-consumed ServiceNow/Open-Meteo DEV sets.

#1473 is separate from #1471 safety closure, #1339 multilingual coverage,
#1346 independent external agent E2 and #1450 atomic source authority design.
Release PR #1356 remains HOLD; frozen #432 science unchanged.
