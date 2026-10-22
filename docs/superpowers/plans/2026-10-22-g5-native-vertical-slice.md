# G5 Source-Native Vertical Slice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Connect existing host-declared concept and typed G5 retrieval to one authorized fixed-K agent-visible route set, then measure real source-native task outcomes with the existing evaluator.

**Architecture:** Compose `resolve_native_concepts`, current principal-scoped direct FieldGroup retrieval and the pinned `NativeSchemaGraphIndex.lookup`; do not create a second graph, a new agent loop or executor. Add a strictly opt-in adapter for the already existing fixed5 scoped evaluator and one bounded Open-Meteo E1 comparison arm. Treat live-source or local-model unavailability as explicit blocked evidence, never success.

**Tech Stack:** Python >=3.10, Pydantic v2, pytest, Ruff, Pyright, existing SchemaRouter registry/policy and native OpenAPI/MCP adapters, existing Open-Meteo `httpx` and local Qwen E1 facilities.

**Spec:** `docs/superpowers/specs/2026-10-22-g5-native-vertical-slice-design.md`

## Global Constraints

- Keep stable `SchemaRouter.retrieve_authorized` and all frozen #432/FULL/SR-5 model paths behavior-identical. No product default, release/tag/PR #1356 change.
- Require explicit `PrincipalContext`, owner-reviewed `NativeConceptCatalog`, native source/endpoint fingerprints and same-version `NativeSchemaGraphIndex`; **strict K=5 distinct exposed routes**.
- No inferred aliases, output fields, join parameters, input values, permissions or execution authority. Registered source and local host remain authoritative.
- A direct complete single-endpoint option may precede a complete one-hop path; do not silently show partial field groups or arbitrarily truncate over-K alternatives.
- Recheck current policy/data-scope/availability/source identity before and after candidate selection and before agent disclosure. Never disclose hidden route/field names or counts.
- Keep original source-native execution and strict final-grounding score separate from E0 fixture replay. Exposed developer-authored E1 is not independently authored E2; #1346 remains `BLOCKED_EXTERNAL`.
- **Source-intake precondition:** the existing live Open-Meteo E1 `ToolSpec`s currently lack `license`, declared typed output `semantic_id` mappings and a proven latitude/longitude identifier-to-parameter G5 edge; the current live builder also does not supply the explicit retrieval `AuthorizationPolicy` required by G5. `NativeSchemaGraphIndex` deliberately refuses these contracts. Do not alter source models or assert graph routing merely to score an E1 arm; require source-reviewed, exact-version metadata, an actual scoped policy and current source permission first, otherwise record `BLOCKED_SOURCE_SEMANTICS`.
- Avoid adding new agent executors, new routing databases, new independent micro-benchmark scripts or new model prompts; existing read-only utilities should be reused.
- One feature branch/PR for the whole vertical slice; finish user-visible functionality and a paired outcome record before unrelated optimization work.

## Review Focus

The five inputs most likely to hide a significant product regression, each pinned to a specific task test below:

1. **Partially complete one-hop join with two typed inputs** must not expose a source path as executable (Task 1: `test_reject_partial_native_join`).
2. **Nested/ref hidden output label echoed through a tool schema** must never reach the model even though route IDs are allowed (Task 2: `test_graph_view_redacts_nested_hidden_metadata`).
3. **Previously captured view plus in-place policy mutation** must fail before the next model turn (Task 2: `test_graph_selector_rejects_policy_content_drift`).
4. **Live source changes between paired FULL and G5 arms** must be recorded as incomparable/blocked rather than success improvement (Task 3: `test_paired_native_graph_source_drift_is_not_scored`).
5. **The old one-time milestone initialization SHA changes** must not be silently repinned or cause any new automatic Issues-write activity (Task 4: `test_live_assignment_addendum_preserves_initialization_blob_guard`).

---

## File and interface map

| Responsibility | File | Kind |
| --- | --- | --- |
| Scoped, nonexecuting concept→direct/one-hop composer | `src/schemarouter/concept_graph_retrieval.py` | Create; orchestration only, canonical graph logic untouched |
| Public explicit opt-in imports | `src/schemarouter/__init__.py` | Modify only to export new result/composer |
| Native composer behavior and authority edge tests | `tests/test_native_concept_graph_vertical_slice.py` | Create |
| Existing evaluator adapter | `scripts/research_authorized_concept_fixed5_agent_bridge.py` | Extend; preserve previous selector/arm |
| Existing fixed5 adapter tests | `tests/test_research_authorized_concept_graph_fixed5_bridge.py` | Create |
| Original Open-Meteo actual provider E1 | `scripts/research_real_qwen_open_meteo_two_hop_e1.py` | Add named `concept_graph_optin` mode; preserve defaults |
| E1 comparison tests and safe output | `tests/test_research_real_qwen_concept_graph_e1.py` | Create |
| User documentation and milestone live state | `docs/research/research-program-2026.md`, `.github/RESEARCH_MILESTONES.md`, `tests/test_research_milestones.py` | Document implemented boundary, source/holdout status and live assignments without repinning historical initialization manifest |

### Task 1: Explicit source-pinned direct / one-hop concept graph result

**Files:**
- Create: `src/schemarouter/concept_graph_retrieval.py`
- Modify: `src/schemarouter/__init__.py`
- Create: `tests/test_native_concept_graph_vertical_slice.py`

**Interfaces:**
- Consumes: `resolve_native_concepts(query, catalog=...)`, `retrieve_authorized_field_group(router, query, principal=..., group=..., k=5)`, `NativeSchemaGraphIndex.lookup(router, query, principal=..., group=..., k=5)` and their existing source/authority witness validations.
- Produces:
  - `NativeConceptRouteSet(route_ids: tuple[str, ...], route_fingerprints: tuple[tuple[str, str, str], ...], required_semantic_ids: tuple[str, ...], parameter_bindings: tuple[tuple[str, str], ...] = ())` immutable dataclass; fingerprint triples are `(route_id, tool_fp, endpoint_fp)`.
  - `NativeConceptGraphSelection(status: Literal["complete", "no_proven_hit", "over_k_unranked", "budget_unsatisfied"], snapshot_id: str, registry_version: int, requested_k: int, route_sets: tuple[NativeConceptRouteSet, ...], route_ids: tuple[str, ...], independent_quality_evidence: bool = False, calibrated_no_fit: bool = False, executable_authority: bool = False)` immutable dataclass.
  - `retrieve_authorized_concept_graph(router: SchemaRouter, query: str, *, principal: PrincipalContext, catalog: NativeConceptCatalog, index: NativeSchemaGraphIndex, k: int = 5) -> NativeConceptGraphSelection`.

- [ ] **Step 1: Write RED tests for direct completeness and one-hop required bindings.** In the new file use the native tool fixture patterns from `tests/test_native_field_group_retrieval.py` and `tests/test_native_graph_multi_input.py`; names `test_direct_complete_fieldgroup_precedes_partial_siblings`, `test_authorized_one_hop_preserves_route_ids_and_join_bindings`, `test_reject_partial_native_join`. Assert `route_ids == ("complete.read",)` for a direct complete case; for a typed root+consumer case assert both original routes, every required source binding and `executable_authority is False`. A-only/B-only siblings, incompatible unit/type/source/license and incomplete second input cannot satisfy the demand.
- [ ] **Step 2: Run the RED cases.** `python -m pytest tests/test_native_concept_graph_vertical_slice.py -k 'direct_complete or authorized_one_hop or reject_partial' -q` — Expected: failures from the absent composer, not fixture import or environment errors.
- [ ] **Step 3: Implement the immutable result and composer.** Resolve current concepts only from host catalog; call both existing complete direct and indexed one-hop paths under the same current principal/policy/registry snapshot. Never independently traverse raw unscoped tool metadata or invent joins. Prefer source-attested complete direct routes; consider one-hop when direct is absent. Emit `complete` only for fully verified, total-visible-route-count ≤5; if valid alternatives exceed K without a separately verified ranker, return `over_k_unranked` with no routes and no private path/count data. Return `no_proven_hit` with no routes on an absent authorized hit. Reserve `budget_unsatisfied` for trusted model-disclosure byte budget rejection in the downstream adapter, not a fabricated token score at the composer stage. Recheck input catalog version, registry index source and router's authority witness after both lookups.
- [ ] **Step 4: Verify GREEN.** Same command as Step 2 — Expected: all selected tests pass.
- [ ] **Step 5: Write additional negative tests.** Names: `test_graph_over_k_shared_root_is_not_arbitrary_top5`, `test_graph_denied_and_hidden_routes_leave_no_public_metadata`, `test_graph_changed_registry_or_policy_fails_closed`, `test_graph_owner_catalog_mutation_refused`, `test_graph_ko_ja_en_aliases_produce_same_typed_paths`, `test_graph_k_must_equal_five`.
- [ ] **Step 6: Observe RED.** `python -m pytest tests/test_native_concept_graph_vertical_slice.py -q` — Expected: the newly written negative cases fail for missing guarded behavior; the direct/one-hop positives still pass.
- [ ] **Step 7: Add the minimum guard logic.** In the Task 1 composer, preserve current P0-visible tool and field projections before choosing paths, check strict K and current source/authority before returning, and never serialize hidden metadata or an unverified ranked choice.
- [ ] **Step 8: Run related regressions.** `python -m pytest tests/test_native_field_group_retrieval.py tests/test_native_graph_index.py tests/test_native_graph_multi_input.py tests/test_native_concept_graph_vertical_slice.py -q` — Expected: 0 failed.
- [ ] **Step 9: Commit.** `git add src/schemarouter/concept_graph_retrieval.py src/schemarouter/__init__.py tests/test_native_concept_graph_vertical_slice.py` then `git commit -m "feat: compose authorized native concepts with G5 routes"`.

### Task 2: Connect product candidates to existing principal-scoped agent disclosure

**Files:**
- Modify: `scripts/research_authorized_concept_fixed5_agent_bridge.py`
- Create: `tests/test_research_authorized_concept_graph_fixed5_bridge.py`

**Interfaces:**
- Consumes: Task 1's `retrieve_authorized_concept_graph` result; `AuthorizedAgentToolSurface`, `_visible_fingerprints`, `EXPERIMENTAL_FIXED5_CONDITION` and existing callback signature `(query: str, visible_route_ids: tuple[str, ...]) -> list[str]`.
- Produces: `AuthorizedConceptGraphFixed5Selector(view: AuthorizedAgentToolSurface, catalog: NativeConceptCatalog, index: NativeSchemaGraphIndex)` implementing the existing callback, with `last_status: str | None` and the three quality/authority flags all `False`.

- [ ] **Step 1: Write RED integration tests.** `test_graph_selector_passes_two_routes_to_existing_agent`, `test_graph_view_redacts_nested_hidden_metadata`, `test_graph_selector_rejects_policy_content_drift`, `test_graph_selector_rejects_schema_fingerprint_drift`, `test_graph_selector_rejects_over_k_or_byte_budget`, `test_graph_selector_no_gold_or_execution_access`. Use existing snapshot and `run_generated_episode` testing idioms in `tests/test_research_authorized_concept_fixed5_agent_bridge.py` and `tests/test_research_authorized_agent_tool_surface.py`. Assert model-visible tools are only declared/source-visible routes, denied nested names absent from serialized model definitions, no host execution from selection, and `[]`/safe disposition for unsupported or over-K.
- [ ] **Step 2: Run RED.** `python -m pytest tests/test_research_authorized_concept_graph_fixed5_bridge.py -q` — Expected: new selector not importable, after fixture setup completes.
- [ ] **Step 3: Implement selector only.** Keep old `AuthorizedConceptFixed5Selector` untouched and historical test behaviors unchanged. Reuse its catalog digest, query/view equality, HMAC-scoped receipt, route-fingerprint equality and candidate restriction. Validate Task 1's complete two-route result, all selected route IDs in `view.visible_route_ids`, no disclosure beyond 5, plus `view.tool_definitions(route_ids)` schema/byte budget. On a trusted byte budget rejection, record `budget_unsatisfied` and return `[]`; on policy, fingerprint or view changes, raise `PolicyViolationError`. Never pass source gold, fixture, model generated text or invoker to the selector.
- [ ] **Step 4: Verify GREEN and regressions.** `python -m pytest tests/test_research_authorized_concept_graph_fixed5_bridge.py tests/test_research_authorized_concept_fixed5_agent_bridge.py tests/test_integrated_fixed5_agent_selector.py tests/test_research_authorized_agent_tool_surface.py -q` — Expected: 0 failed; historical fixed5 conditions unchanged.
- [ ] **Step 5: Commit.** `git add scripts/research_authorized_concept_fixed5_agent_bridge.py tests/test_research_authorized_concept_graph_fixed5_bridge.py` then `git commit -m "feat: expose source-checked G5 route sets to existing fixed5 agent"`.

### Task 3: One measured native-source agent experiment, with explicit negative outcomes

**Files:**
- Modify: `scripts/research_real_qwen_open_meteo_two_hop_e1.py`
- Create: `tests/test_research_real_qwen_concept_graph_e1.py`

**Interfaces:**
- Consumes: Task 2's scoped graph selection; existing `evaluate_one(agent, client, *, language, city, country, menu_mode="all_visible", transport_retry_budget=0, evidence_reprompt_budget=0)`; original Open-Meteo host, strict two-call argument binding and `_matches_weather_final`.
- Produces: opt-in `menu_mode="concept_graph_optin"` on `evaluate_one`, plus a named paired comparison in the same module (`compare_graph_native_e1(agent: Any, client: httpx.AsyncClient) -> dict[str, Any]`) with arms `all_visible` (original full native menu), `lexical_k5` (existing `router.retrieve_authorized` restricted to the same native source) and `concept_graph_optin` (Task 2 selector). Preserve old `evaluate`/`real_cpu_run` defaults and output shape. The two-route Open-Meteo source cannot by itself demonstrate context-cost reduction against FULL under K5; this E1 cohort tests native two-step **correctness and failure attribution** only, not a large-catalog cost claim.

- [ ] **Step 1: Write RED controlled-host tests.** Names: `test_graph_e1_requires_verified_geocoding_before_weather`, `test_graph_e1_scoped_selection_never_calls_host`, `test_paired_native_graph_source_drift_is_not_scored`, `test_graph_e1_false_final_not_scored_as_pass`, `test_graph_e1_en_ko_ja_same_source_and_k`, `test_legacy_e1_output_unchanged`, `test_unattested_live_open_meteo_g5_never_fabricates_join`. Reuse existing fake `httpx` transport and mock agent from `tests/test_research_real_qwen_open_meteo_two_hop_e1.py` or the nearest existing tests; no unbounded real network or model download in unit tests. The last test asserts current `build_live_router` cannot pass G5 selection without the missing license, typed field contracts, explicit principal policy and approved root; record `BLOCKED_SOURCE_SEMANTICS` instead of falling back to a gold-picked two-route menu. Reject source/policy drift between arms, count attempted and validated provider calls separately, and award pass only after both source calls and strict final fields.
- [ ] **Step 2: Run RED.** `python -m pytest tests/test_research_real_qwen_concept_graph_e1.py -q` — Expected: missing named arm/comparison tests fail while baseline tests import correctly.
- [ ] **Step 3: Implement minimum opt-in E1 arm with a source-semantic gate.** The current Open-Meteo E1 builder has `source_type="public_rest"` but **no license**, scalar semantic-ID/identifier contracts, explicit G5 authorization policy or G5-approved parameterized geocoding root; this is a known `BLOCKED_SOURCE_SEMANTICS` precondition, not a model result. Verify permitted use against the original [Open-Meteo terms](https://open-meteo.com/en/terms) and the actual upstream field schema; do not infer commercial permission from a public endpoint. Any host-reviewed enrichment must retain exact native field names/values, use the existing `HostSemanticAttestation`/source fingerprint controls where applicable, and be reviewed separately from task gold. Only if that qualified source intake is actually available may the source-approved geocoding root consume host-provided city/country/language and feed verified latitude/longitude to the weather operation. Compute graph selection from that current same-version source and intersect its route IDs with existing state-ready visibility at each model turn. Otherwise return an explicit blocked comparison with **no** G5 task-success percentage. Keep host invocation, data-scope projection, model-output parsing, retry policy and strict source final scorer unchanged. Alternate arm order, reject source identity changes as incomparable, never adapt to ground truth or dynamically raise K. Public telemetry only: language, condition, source revision, validated call count, task pass, safe failure-stage enum, tokens, CPU/wall where measured; never dump queries, tool responses, hidden fields or secrets.
- [ ] **Step 4: Verify GREEN.** `python -m pytest tests/test_research_real_qwen_concept_graph_e1.py tests/test_research_real_qwen_open_meteo_two_hop_e1.py tests/test_research_paired_agent_fixed5_e0.py -q` — Expected: 0 failed with existing historical tests preserved.
- [ ] **Step 5: Execute E1 *only if the pinned model, independently approved source-semantic contract and permitted original source are all available*.** `python -m scripts.research_real_qwen_open_meteo_two_hop_e1 --out /tmp/schemarouter-native-g5-e1.json` in a task-specific temporary path, with an opt-in flag added for the new named comparison; archive source/model SHA, exact original tasks and sanitized paired results. Expected: either real per-arm task/safety/cost records **or** an explicit `BLOCKED_SOURCE_SEMANTICS`/`BLOCKED_MODEL_RUNTIME`/`SOURCE_FAILURE` explanation. Never call an E0 fixture run E1, fabricate 0 tokens, or interpret a blocked run as 0% task success.
- [ ] **Step 6: Commit.** `git add scripts/research_real_qwen_open_meteo_two_hop_e1.py tests/test_research_real_qwen_concept_graph_e1.py` then `git commit -m "test: measure opt-in G5 against real native agent task completion"`.

### Task 4: Product documentation, live milestone addendum and qualification decision

**Files:**
- Modify: `docs/research/research-program-2026.md`
- Modify: `.github/RESEARCH_MILESTONES.md`
- Test: `tests/test_research_milestones.py` (existing historical initializer invariant)

**Interfaces:**
- Consumes: Tasks 1–3's public opt-in import, actual E1 outcome (or explicit blocked state), and the live GitHub-verified #1700→M1/#1711→M5 assignments.
- Produces: accurate usage and negative-result note; no new release-gate or GitHub workflow behavior.

- [ ] **Step 1: Write a RED documentation/milestone safety test.** Add `test_live_assignment_addendum_preserves_initialization_blob_guard` asserting the narrative documents new live assignments and explicitly identifies the old 30-item manifest as a **historical one-time initialization snapshot**, while the invariant `test_exact_source_blob_gates_one_time_main_push_initialization` still pins the original blob and no auto Issues-write permission changes.
- [ ] **Step 2: Run RED.** `python -m pytest tests/test_research_milestones.py -k 'live_assignment_addendum' -q` — Expected: failure because the live addendum text is absent.
- [ ] **Step 3: Document the real opt-in API and measured outcome.** Put one read-only EN/KO/JA concept→FieldGroup→fixed5 example, the direct vs one-hop distinction, denied/over-K behavior, source and host responsibilities, exact E1 metrics or blockers, and links to existing parent issues in `docs/research/research-program-2026.md`. Update `.github/RESEARCH_MILESTONES.md` with #1700/#1711 live addendum. **Do not edit** `.github/research-milestones.json`, its `3df25049...` pinned initializer workflow or the auto-sync policy in this product PR: changing the protected initializer blob would break a separate safety gate. Propose a separately reviewed versioned migration only if a future maintainer explicitly requests machine-readable reinitialization.
- [ ] **Step 4: Verify.** `python -m pytest tests/test_research_milestones.py -q` and `python .github/scripts/sync_research_milestones.py` (read-only preview) — Expected: 0 failures; no network or GitHub Issues writes in preview.
- [ ] **Step 5: Repo verification.** `python -m pytest tests/test_native_concept_graph_vertical_slice.py tests/test_research_authorized_concept_graph_fixed5_bridge.py tests/test_research_real_qwen_concept_graph_e1.py tests/test_research_milestones.py -q`, `ruff check src/schemarouter/concept_graph_retrieval.py scripts/research_authorized_concept_fixed5_agent_bridge.py scripts/research_real_qwen_open_meteo_two_hop_e1.py tests/test_native_concept_graph_vertical_slice.py tests/test_research_authorized_concept_graph_fixed5_bridge.py tests/test_research_real_qwen_concept_graph_e1.py`, `pyright`, and `git diff --check` — Expected: 0 failed/errors, noting any environment-only unavailable checks instead of claiming success.
- [ ] **Step 6: Commit.** `git add docs/research/research-program-2026.md .github/RESEARCH_MILESTONES.md tests/test_research_milestones.py` then `git commit -m "docs: record G5 end-to-end evidence and live milestone state"`.

## Final decision and branch handoff

1. Review the **full branch** against the spec's safety, native source identity, complete-field-set and task-final metrics; use the selected implementation workflow's reviewer stage before a PR.
2. A completed code PR must include the exact command/output evidence for all relevant tests, task-level native E1 passes/failures (or the precise run blocker), no-fit/hidden scope negatives and model CPU cost when measured. Do **not** declare E2, product-default readiness or close #1535/#1560/#1477 merely because E0 green.
3. If execution is blocked, preserve the substantive new opt-in functionality with correctly qualified negative/blocked evidence; do not start another unapproved E0 optimization loop.
4. **E2 status:** #1346's publisher-disjoint E2 remains independently blocked; #1356 remains a release HARD HOLD; CodeGraph #1711 remains M5. No release, tag, issue-closing or protected-CI override is part of this plan.
