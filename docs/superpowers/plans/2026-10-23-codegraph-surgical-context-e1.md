# CodeGraph-Style Surgical G5 E1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the source-attested, reference-only G5 E0 result into an explicitly opted-in, source-revalidated, model-driven E1 schema-request and read-only execution path; measure its actual task outcome and total model cost against FULL, lexical SR-5 and typed G5.

**Architecture:** Keep `retrieve_authorized_concept_graph` as the selector, `capture_authorized_agent_tool_surface` as the principal-scoped disclosure authority, and `execute_scoped_host_call` as the sole native executor. Add research-only lazy original-schema materialization and an agent protocol adapter; compare four actual-model arms in separately identified original Open-Meteo and ≥10-route local-source cohorts. Never introduce a competing registry, authorization grant or product default.

**Tech Stack:** Python >=3.10; current `schemarouter` Pydantic v2 registry, policy, native G5 graph index and `RegistryExecutor`; existing Qwen agent, `httpx` Open-Meteo E1 harness, pytest, Ruff, Pyright, bilingual MkDocs documentation.

**Spec:** `docs/superpowers/specs/2026-10-23-codegraph-surgical-context-e1-design.md`

**Tracking:** [#1711](https://github.com/JDeun/SchemaRouter/issues/1711), M5; stacked after [#1714](https://github.com/JDeun/SchemaRouter/pull/1714) and [#1715](https://github.com/JDeun/SchemaRouter/pull/1715). The design is reviewed separately from this implementation plan. Execute tasks **sequentially under option A** after plan review; do not delegate.

## Global Constraints

- Research-only explicit opt-in: no modifications to `SchemaRouter.retrieve_authorized`, the standard agent tool menu, product policy defaults or execution API. Do not change #432's frozen FULL/SR-5 results.
- Strict `k=5` distinct original routes, `complete` G5 path only; no silent truncation, widened selection, unproved typed join, schema synthesis or substitute execution path.
- A route reference, tool definition or materialization receipt is **not permission**. Revalidate original registry/source witness, current policy **content** digest, canonical principal, source/tool/endpoint fingerprints, all selected-route visibility and producer output→consumer input bindings at selection, disclosure, model-action processing and every native call. Treat failed checks as uniform fail-closed denials without leaking source inventory.
- Initial surgical model menu contains only a fixed `research__request_scoped_source_schema` host action; it exposes **no executable original provider schema** until a validated request. Map this reserved action in the research harness, never register it as a provider route or pass it to `execute_scoped_host_call`.
- The host supplies original source schemas via `AuthorizedAgentToolSurface.tool_definitions`; use its original scalar observation projector and `execute_scoped_host_call`. Never persist raw model messages, private arguments, credentials, original provider bodies, hidden policy rules or internal HMAC material.
- Equal tasks, same pinned model/revision, source contract, language, principal, K and retry/turn budgets across arms. Measure every model turn and materialization request; missing actual token receipts are `null`, not zero. Never infer dollar savings from E0 UTF-8 bytes.
- Open-Meteo original free API is non-commercial research only; do not imply an OSS downstream user has commercial rights. Cohort B is labeled `E1_LOCAL_SOURCE_CONTROL`, not original provider evidence or independent E2.
- When model runtime, source permissions, source semantics, or original HTTP connection are absent, preserve a specific blocked/incomparable result with a **null success denominator**. #1346 E2 remains blocked; #1356 release HARD HOLD. No automated merge, release, or issue close.

## Review Focus

The five likely-uncovered failure inputs and their explicit owning tests:

1. A **forged, duplicated, unselected or wildcard route ID** in the schema request must not reveal any original definition or let a route execute (Task 1: `test_materializer_rejects_unselected_duplicate_and_wildcard_ids`).
2. The policy's **nested rule content changes in place** after a valid selection while the registry version remains unchanged; disclosure and subsequent action must both fail (Task 1: `test_materializer_rejects_in_place_policy_drift`).
3. A **producer identifier becomes hidden** or a canonical principal claim changes before the second route; consumer schema and call must not proceed (Task 2: `test_agent_aborts_hidden_binding_or_principal_swap_before_consumer`).
4. An **invalid or partial meta-action JSON** or repeated schema request could otherwise be misparsed as a provider operation or yield unbounded disclosure (Task 2: `test_agent_rejects_malformed_or_repeated_schema_requests_without_source_call`).
5. **Live provider revision/transport changes between compared arms** could turn unavailable original data into a false task win or zero-cost statistic (Task 3: `test_four_arm_source_failure_has_null_denominator_and_tokens`).

---

## File and interface map

| Responsibility | Exact file | Scope |
| --- | --- | --- |
| Current source-attested selection fixture and E0 comparison | `scripts/research_codegraph_surgical_context_e0.py` | Reuse; no change to published E0 measurement |
| Research-only selected-schema materializer | `scripts/research_codegraph_scoped_materializer.py` | Create `capture_surgical_episode` and `request_scoped_source_schema` |
| Materializer security, drift and K5 tests | `tests/test_research_codegraph_scoped_materializer.py` | Create |
| Source-checked model/host protocol | `scripts/research_codegraph_surgical_agent_e1.py` | Create `run_surgical_model_episode`; reserved research meta-action only |
| Agent protocol tests and host callbacks | `tests/test_research_codegraph_surgical_agent_e1.py` | Create |
| Four-arm original native provider scorer | `scripts/research_real_qwen_open_meteo_two_hop_e1.py` | Add *named* surgical comparison, preserve existing `evaluate_one` defaults |
| Actual-model comparison tests | `tests/test_research_real_qwen_codegraph_surgical_e1.py` | Create |
| Source-registered deterministic ten-plus-route control | `scripts/research_codegraph_local_multiroute_e1.py` | Create source fixtures and paired runner |
| Local execution, route-parity and cost tests | `tests/test_research_codegraph_local_multiroute_e1.py` | Create |
| E1 verdict, provenance, commercial usage boundary | `docs/research/codegraph-surgical-context-e1.md`, `docs_ko/research/codegraph-surgical-context-e1.md` | Create after actual attempt, including explicit blocked outcome if needed |
| Bilingual docs index, metadata, semantic review | `mkdocs.yml`, `mkdocs.ko.yml`, `docs_ko/translation-manifest.json`, `audits/ko-direct-semantic-spotcheck-2026-10-12.json` | Update during final documentation task |

### Task 1: Fail-closed, selected-only original schema materializer

**Interfaces:** `capture_surgical_episode(router, query, *, principal: PrincipalContext, catalog: NativeConceptCatalog, index: NativeSchemaGraphIndex, k: int = 5) -> SurgicalEpisode` stores a host-private authority/policy/principal receipt and verified G5 selection; `request_scoped_source_schema(episode: SurgicalEpisode, selected_route_ids: list[str]) -> list[dict[str, Any]]` returns *current original* source definitions only for a nonempty unique subset of the positively selected routes. The public episode reference is sanitized and explicitly `tool_call_ready=False` until materialization; no stored schema or route receipt grants execution. The caller retains the newly checked scoped view for the existing invoker rather than trusting cached data.

- [ ] **Step 1 — RED:** Add `test_valid_two_route_subset_returns_only_current_original_definitions`, `test_materializer_rejects_unselected_duplicate_and_wildcard_ids`, `test_materializer_rejects_in_place_policy_drift`, `test_materializer_rejects_registry_source_and_principal_drift`, `test_no_fit_denied_and_six_route_over_k_have_no_schema_disclosure`, `test_hidden_required_producer_field_prevents_disclosure`. Reuse `tests/test_research_codegraph_surgical_context_e0.py` fixtures, including `AuthorizationPolicy`/`DataScopeRule` in-place mutation; assert exact original route IDs and `PolicyViolationError` for negative requests, no source callbacks.
- [ ] **Step 2 — RED command:** `python -m pytest tests/test_research_codegraph_scoped_materializer.py -q`; failures must be missing behavior, not broken imports/test environment.
- [ ] **Step 3 — GREEN:** Implement bounded immutable host-private episode identity; use `retrieve_authorized_concept_graph(..., k=5)`, capture a fresh `AuthorizedAgentToolSurface`, verify `_retrieval_authority_witness`, `_authorization_policy_receipt`, `_principal_claims_canonical`, selected path fingerprint/visible fields/bindings and `tool_definitions(subset, k=5)` both **before and after** disclosure. Uniformly reject stale, non-complete, over-K or unselected paths; do not leak unauthorized route inventory or HMAC internals.
- [ ] **Step 4 — GREEN command:** `python -m pytest tests/test_research_codegraph_scoped_materializer.py tests/test_research_codegraph_surgical_context_e0.py tests/test_research_authorized_agent_tool_surface.py -q` — all relevant tests pass with E0 output unchanged.
- [ ] **Step 5 — Commit:** Stage only the materializer and its tests; `git commit -m "feat(research): guard on-demand G5 original schema materialization"`.

### Task 2: Model-driven schema request to original scoped native call

**Interfaces:** `run_surgical_model_episode(agent, *, episode, host_context, max_turns=...) -> SanitizedEpisodeResult`. Keep `LocalQwenAgent.generate(messages, tools)` and `parse_one_model_action` output grammar; the research-only model-visible tool name is `research__request_scoped_source_schema`, mapping exclusively to the host `request_scoped_source_schema` operation. Native names stay `tool__endpoint`. Schema responses are inserted into the measured model transcript, never treated as implicit execution; trusted host inputs and validated prior public observations alone may satisfy typed subsequent route arguments.

- [ ] **Step 1 — RED:** Add `test_model_requests_schema_then_calls_two_registered_read_only_routes`, `test_initial_menu_has_only_schema_request_and_no_provider_tool`, `test_agent_aborts_hidden_binding_or_principal_swap_before_consumer`, `test_agent_rejects_malformed_or_repeated_schema_requests_without_source_call`, `test_unmaterialized_route_is_refused_without_original_invocation`, `test_premature_final_and_unbound_arguments_are_task_failures`, `test_schema_request_does_not_change_source_call_count`. Use scripted model envelopes, real registered local source handlers and existing `execute_scoped_host_call`; assert invocation order and no fallback source call on negative input.
- [ ] **Step 2 — RED command:** `python -m pytest tests/test_research_codegraph_surgical_agent_e1.py -q` — expected failing new protocol tests.
- [ ] **Step 3 — GREEN:** Implement a bounded meta-action→schema-disclosure→original-route agent loop by adapting the existing fixed-turn Qwen envelope/strict action parser (without weakening its JSON validation); explicitly reject duplicate or repeated disclosure requests, unknown/partial actions, multi-action output and unbound consumer arguments. Recheck the episode's host witness and freshly scoped authorization after every generation and before each `execute_scoped_host_call`; the model selects each real operation itself. Reuse authorized `project_observation` and native `RegistryExecutor`; do not create source responses or gold-derived arguments.
- [ ] **Step 4 — GREEN command:** `python -m pytest tests/test_research_codegraph_surgical_agent_e1.py tests/test_research_authorized_agent_tool_surface.py tests/test_research_real_qwen_bound_two_step_e0.py -q` — all pass, no baseline behavior change.
- [ ] **Step 5 — Commit:** Stage protocol and tests only; `git commit -m "feat(research): execute surgical G5 schema-request protocol through scoped host"`.

### Task 3: Compare four real-model arms on the original Open-Meteo source

**Interfaces:** Add `compare_codegraph_surgical_e1(agent, client, *, documented_noncommercial_e1: bool = False, ...) -> dict[str, Any]` alongside unchanged `compare_graph_native_e1`. Four distinct arms: `all_visible`, `lexical_k5`, `concept_graph_optin`, `surgical_g5_e1`. Reuse existing `USER_REQUESTS`, `CASES`, original geocoding→weather source evidence, `_matches_weather_final`, source-qualification gate and same model revision. Record one model token receipt per generated turn, including the generic schema action and its tool response, with original source HTTP attempts separately counted.

- [ ] **Step 1 — RED:** Add `test_four_arm_requires_same_tasks_principal_source_and_k`, `test_surgical_arm_never_preinvokes_provider_or_fabricates_geo_coordinates`, `test_four_arm_source_failure_has_null_denominator_and_tokens`, `test_model_runtime_unavailable_is_blocked_not_zero_success`, `test_each_meta_request_and_followup_turn_counts_actual_tool_tokens`, `test_original_three_arm_comparison_remains_unchanged`. Use deterministic `httpx.MockTransport` and scripted model responses, including a bad final answer that must count as an agent failure only when source was healthy.
- [ ] **Step 2 — RED command:** `python -m pytest tests/test_research_real_qwen_codegraph_surgical_e1.py -q` — expected missing named comparator tests fail.
- [ ] **Step 3 — GREEN:** Wire a research-only fourth scorer branch through the Task 2 protocol, keeping the existing model, provider client and trustworthy native source intake. Rotate arm order; abort an episode on source/policy/authorization drift. Preserve `INCOMPARABLE_SOURCE_FAILURE`, `INCOMPARABLE_SOURCE_DRIFT`, `BLOCKED_SOURCE_SEMANTICS`, `BLOCKED_MODEL_RUNTIME` and null aggregate denominator. Record exact per-turn input/tool-schema/output token counts and model/host turns; if a receipt is absent, set the aggregate to `null`, never `0` or guessed tokenizer bytes. Do not interpret Open-Meteo's two-route fixture as large-menu cost evidence.
- [ ] **Step 4 — GREEN command:** `python -m pytest tests/test_research_real_qwen_codegraph_surgical_e1.py tests/test_research_real_qwen_concept_graph_e1.py tests/test_research_real_qwen_open_meteo_two_hop_e1.py -q` — pass with original three-arm assertions unchanged.
- [ ] **Step 5 — Attempt genuine run only when permitted:** Invoke the existing pinned Qwen CPU harness with a new explicit surgical comparison flag and a task-specific `/tmp/schemarouter-codegraph-surgical-e1-open-meteo.json` output. Preserve model/source revision and failure stage; if unavailable, emit a truthful blocked artifact **without** fabricated actual-model rows or success percentages.
- [ ] **Step 6 — Commit:** Stage comparator, tests and sanitized, nonsecret experiment evidence when present; `git commit -m "test(research): compare surgical G5 with original four-arm task outcomes"`.

### Task 4: Actual executable local-source ≥10-route scaling control

**Interfaces:** `run_local_multiroute_codegraph_e1(agent, *, language, condition) -> dict[str, Any]` builds a deterministic, owner-reviewed `SchemaRouter` with **at least ten separately registered read-only endpoints**, actual original typed native schemas and callable host registrations. Frozen EN/KO/JA case data must include an authorized two-step path, denied/no-fit, and six-route over-K failure. Every compared arm consumes the same registered source and host answer oracle. Output tier is always `E1_LOCAL_SOURCE_CONTROL`.

- [ ] **Step 1 — RED:** Write `test_fixture_registers_at_least_ten_real_read_only_host_routes`, `test_en_ko_ja_two_step_calls_are_actual_registered_callbacks`, `test_local_full_lexical_g5_surgical_share_exact_source_witness`, `test_denied_no_fit_over_k_stop_before_source_access`, `test_fixture_cost_includes_schema_round_trip_and_all_model_turns`, `test_no_claim_of_independent_or_remote_provider_evidence`. Assert complete two-hop bindings, K5 strict refusal and exact source callback counters.
- [ ] **Step 2 — RED command:** `python -m pytest tests/test_research_codegraph_local_multiroute_e1.py -q` — expected missing fixture/runner behavior.
- [ ] **Step 3 — GREEN:** Build real registered deterministic host callbacks and reviewed typed route contracts; adapt the four-arm runner from Task 3 without reusing provider observations as fabricated external calls. Preserve all source authorization, visibility checks, fixed model/turn budgets and strict oracle. Score **actual model** requests where runtime exists, otherwise label `BLOCKED_MODEL_RUNTIME`; retain source-fixture-only tests as contract checks, not real-model outcomes.
- [ ] **Step 4 — GREEN command:** `python -m pytest tests/test_research_codegraph_local_multiroute_e1.py tests/test_research_codegraph_surgical_agent_e1.py tests/test_research_codegraph_scoped_materializer.py -q` — pass for positive and negative cases.
- [ ] **Step 5 — Attempt real Qwen E1 control:** Run the pinned model with `--cohort local-source` and bounded output to `/tmp/schemarouter-codegraph-surgical-e1-local.json`; never replace a missing model with mock scores. Publish separately from the original Open-Meteo outcome, with exact token receipts or `null`.
- [ ] **Step 6 — Commit:** Stage source-backed local runner and tests; `git commit -m "test(research): measure surgical G5 on source-registered multiroute control"`.

### Task 5: Bilingual E1 verdict and clean branch handoff

**Interfaces:** Publish `docs/research/codegraph-surgical-context-e1.md` and its direct Korean translation; link the plan/design, cohort-specific provenance and exact commands. Preserve document translation source blob audit integrity and both strict MkDocs navs.

- [ ] **Step 1 — RED:** Extend existing `tests/test_bilingual_docs_integrity.py`, `tests/test_translation_semantic_sections.py` or an appropriately scoped document-evidence test with assertions that both cohort labels, all four arms, hard source blockers, actual token attribution and null denominators appear in the bilingual report. Assert no E0 byte savings are reinterpreted as model savings and no independent E2 or release claim.
- [ ] **Step 2 — RED command:** `python -m pytest tests/test_bilingual_docs_integrity.py tests/test_translation_semantic_sections.py -q` — the new evidence-page assertions should initially fail.
- [ ] **Step 3 — GREEN:** Write the English/Korean experiment pages with source/provider qualification, cohort A and B data **only if actually produced**, separate blocked/negative outcomes otherwise, serialized-byte-vs-token distinction, model/code/source revision, CI/run ID, exact reproduction commands, security negatives and user-facing commercial-license boundary. Mirror MkDocs nav, translation manifest blob pin and AI-assisted EN/KO review audit. Keep #1711 open pending substantive E1 verdict and leave #1346/#1356 unchanged.
- [ ] **Step 4 — Targeted verify:** `python -m pytest tests/test_bilingual_docs_integrity.py tests/test_korean_translation_coverage.py tests/test_translation_review_units.py tests/test_translation_semantic_sections.py tests/test_bilingual_coverage_report.py -q`; `python scripts/prepare_korean_docs.py --output /tmp/schemarouter-codegraph-e1-site-docs`; both must pass with no untranslated fallback pages.
- [ ] **Step 5 — Full verification:** `python -m pytest -q` (or document exact environment-limited subsets), `ruff check src scripts tests`, `pyright`, `git diff --check`; verify updated GitHub Actions, provenance and that no private observations or credentials entered versioned artifacts. Do not claim tools passed if unavailable.
- [ ] **Step 6 — Commit and review:** `git commit -m "docs(research): publish bilingual surgical G5 E1 verdict and evidence"`; request review of the complete implementation branch and maintain the PR as a draft until checks and evidence are confirmed. Merging and release promotion remain separately approved actions.

## Final verification and handoff

1. The minimum success criterion is **working, security-verified model-driven on-demand schema disclosure and real scoped callback execution**, even if its token overhead makes it a net loss. Record that loss without another micro-optimization loop.
2. Distinguish source-available model failures from source transport failures, model runtime blockers and E0 synthetic controls. Report actual model input/tool-schema/output tokens per arm and all intermediate costs, or precisely why no valid comparable receipt exists.
3. Preserve branch/review evidence: source SHA, model revision, EN/KO plan and verdict, commands, CI IDs, local native-source evidence, optional original Open-Meteo evidence and exact unresolved release gates.
4. **Plan review checkpoint:** after this plan is reviewed, begin Task 1 under user-selected **A (direct sequential implementation)**; do not silently skip this approval checkpoint or substitute parallel agents.
