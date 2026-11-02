# Native indexed FieldGroup → fixed-K agent bridge (E0) implementation plan

> **For agentic workers:** Follow red/green TDD, preserve historical agent conditions, and verify the full suite before review.

**Context:** Issue #1560 and #1477; stacked development base PR #1753 (`59ae023`). The approved original-paper direction is source-authored concepts → complete typed FieldGroup → live principal-visible native routes → external agent. This is a research-only callback, not product-default retrieval or execution authority.

**Approaches:** (1) Rebuild an agent/evaluator (rejected: duplicate and gold-leak risk); (2) put indexed ranking in the default router (rejected: E2 and no-fit blockers); **(3) bridge the existing posting index to the already isolated `EVAL-FIXED5-OPTIN` selector and authorized model view (chosen)**. This intentionally cannot rescue routes missing from the independently captured authorized model view; that separate source-view limitation is explicit and fail-closed.

**Scope:**
- Preserve P1/P2 existing typed/source/authority proofs and the default `retrieve_authorized` path; only opt-in research selector changes.
- Direct indexed candidates must have no mandatory input envelope; joined producer→consumer routes remain handled only by the existing G5 graph selector.
- Reject stale index/policy/availability, hidden fields, mismatched fingerprints, duplicate/non-view routes, unsafe backend selection or oversized model-visible schema. Unknown declared concepts abstain without pretending calibrated no-fit.
- No new agent loop, task-gold access, synthetic E2 claims or release/merge promotion.

## Task 1 — Source-safe direct indexed concept selection

**Files:** `src/schemarouter/native_semantic_index.py`, `tests/test_native_semantic_index.py`

1. Add a failing test showing `lookup_concepts(..., input_free_only=True)` excludes a source endpoint with required typed input, while the ordinary query-concept lookup remains unchanged.
2. Run that specific test, observe the expected failure.
3. Forward the opt-in input-free flag to the proven native `lookup` filter; do not duplicate filtering.
4. Rerun targeted and existing native-index tests.

## Task 2 — Existing evaluator adapter

**Files:** `scripts/research_authorized_concept_fixed5_agent_bridge.py`, `tests/test_research_authorized_indexed_fixed5_bridge.py`

1. Add failing tests for: direct complete field set, unsupported bound endpoint, source/view mismatch, policy/scope drift, over-K abstention, bounded verified ranking, typed status, and a scripted E0 `run_generated_episode` using its original executor.
2. Run failures against the absent adapter.
3. Implement a focused `AuthorizedIndexedFieldFixed5Selector(view, catalog, index, research_ranker=...)` reusing the existing view integrity and source-fingerprint checks. Selector receives only query and captured visible source IDs.
4. Verify no default behavior change and no new model/backend access beyond detached authorized candidate names.

## Task 3 — Reproducibility and handoff

**Files:** short research implementation note and existing plan.

1. Run focused pytest, Ruff, Pyright and repository-wide pytest; report *all* failures.
2. Commit on an isolated stacked Draft branch; publish only if permitted credentials are available. Do not merge.
3. Record explicit status `E0_ONLY / BLOCKED_EXTERNAL` for independent author #1346, paired agent #1477 E2, calibrated no-fit and release #1356.

**Review focus:** accidentally disclosing a lexical-invisible route as a model tool, a required-input endpoint as direct-ready, hidden fields under partial scope, mutable principal/policy/index between selection and exposure, label leakage, and research ranking claiming execution/no-fit authority.
