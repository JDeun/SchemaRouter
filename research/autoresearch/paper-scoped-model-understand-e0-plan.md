# Paper scoped model Understand E0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use RED/GREEN TDD.

**Goal:** Feed one actual source-scoped model callback's bounded structured JSON output into the current Algorithm 1 direct-plan selector without adding an agent loop, privilege or global no-fit claim.

**Architecture:** A standalone opt-in research adapter invokes a sync/async model with the existing policy-projected source catalog index and approved bounded concept/intent allowlist. It performs strict response validation and immutable post-call source checks. Existing `AuthorizedPaperUnderstoodDirectFixed5Selector` and `run_generated_episode` own source tool exposure and the host no-tool terminal.

**Tech Stack:** Python 3.10+, `ModelAnalysisError`, Pydantic v2, `AuthorizedAgentToolSurface`, `PaperUnderstanding`, pytest/ruff/pyright.

**Spec:** `research/autoresearch/paper-scoped-model-understand-e0-design.md`

## Global Constraints

- Research E0, default-off; existing `ModelQueryAnalyzer`, public router, agent evaluator and executor behavior unchanged.
- Model sees only principal-visible source `catalog_index()` and explicitly host-approved intent/concept identifiers. K5 and all source safety checks stay in the existing direct selector.
- Unknown tool suggestions cannot bypass source checks; model parameters never become invocation arguments. No semantic no-fit or independent EN/KO/JA/E2 performance claims.
- Do not merge stacked Draft, promote v0.18 #1356 or alter frozen #432. Update canonical handoff after verification.

## Review Focus

1. Output `None` and **zero model calls** on empty authorized source (Task 1).
2. Input source descriptions must exclude hidden fields/routes and reject catalog budget overflow before model access (Task 1).
3. Source/policy/principal/owner catalog mutation while model is running must fail closed even after syntactically valid output (Task 1).
4. Duplicate/malformed JSON or model-proposed undeclared intents/concepts cannot become authoritative (Task 1).
5. A hallucinated or unauthorized named tool must reach the existing guarded no-proven-hit path and yield zero downstream agent/tool calls (Task 1).

---

### Task 1 — Bounded scoped model `Understand(q)` boundary

**Files:** new `scripts/research_paper_scoped_understand_e0.py`; new `tests/test_research_paper_scoped_understand_e0.py`.

**Interfaces:** Consume `AuthorizedAgentToolSurface.catalog_index()`, `PaperIntentRegistry`, `NativeConceptCatalog`, `PaperUnderstanding`; produce async `analyze_paper_understanding_scoped(model, *, view, intent_registry, catalog, model_visible_intent_ids, model_visible_concept_ids, max_model_input_bytes=32768, max_model_output_bytes=4096) -> PaperUnderstanding | None`.

- [ ] RED: tests for one model callback with only authorized entries/allowed IDs; actual dict and text JSON; real direct selector + existing scripted agent; unknown model named tool ending in host terminal; no routes/no model; malformed, duplicate, oversized, forbidden IDs, owner/source mutation; KO/JA query untouched.
- [ ] Run `.venv/bin/python -m pytest -q tests/test_research_paper_scoped_understand_e0.py` and observe missing module/API failure.
- [ ] GREEN: strict bounded JSON parser, declared-intent/concept visibility validation, source-view index capture, detached model payload, optional await and post-callback immutable source/owner checks. Errors generic, no prompt or model text in messages.
- [ ] Run `.venv/bin/python -m pytest -q tests/test_research_paper_scoped_understand_e0.py tests/test_research_paper_understood_agent_refusal_e0.py tests/test_paper_understood_direct_plan.py` → all pass.
- [ ] Commit code and tests.

### Task 2 — Handoff, evidence and stacked Draft

**Files:** canonical `research/autoresearch/paper-toolcall-implementation-e0.md`, this plan.

- [ ] Record API usage, local test counts, whole repo Ruff, targeted Pyright, full test/CI failures honestly; verify no hidden data, model hints or default changes.
- [ ] Extend canonical handoff and PR #1755 (or new *related* stacked Draft if exact branch advanced elsewhere) by exact Git tree and expected head, without merge.
- [ ] Keep #1291/#1346/#1477 and #1356 HOLD unchanged; no false fit/no-fit quality claims.

**Execution:** Previously user-approved native sequential implementation with no routine additional approvals. No subagents authorized in this environment.

## 2026-10-25 checkpoint

- Task 1 RED observed: isolated collection failed with missing
  `scripts.research_paper_scoped_understand_e0` module. GREEN: new 16 tests
  pass, and the combined actual model/previous direct agent/P2 unit group
  reports **36 passed**. One test initially expected OpenAI-nested tool
  definitions; investigation found the real `AuthorizedAgentToolSurface`
  deliberately emits a flat `{name, description, parameters}` structure.
  Corrected that **test fixture assumption**; no production workaround.
- `dd75cfb` implements one provider-neutral sync/async scoped model
  callback, bounded input/output JSON, host-disclosed approved IDs, exact
  original authorized native route descriptions, no-authorized-route
  short-circuit, duplicate/nonfinite/undeclared response rejection, and
  principal/source/owner post-callback integrity checks. An unoffered exact
  tool suggestion continues to the existing host no-menu terminal.
- `.venv/bin/ruff check` on changed module+tests **passed** and targeted
  `.venv/bin/pyright scripts/research_paper_scoped_understand_e0.py`
  **0 errors**; repository-wide verification is recorded in the handoff
  after the running commands finish. No model accuracy or E2 claim.
- Whole combined paper+existing-agent+native index regression: **226 passed**
  in 10.23 seconds. New 16 tests also passed under
  `--import-mode=importlib`. Full repository Ruff: **pass**; target Pyright:
  **0 errors**. The `timeout 75s` whole-repository local pytest run exited
  **124** after ~12%, matching the prior local stall; no full-suite claim.
- Self-review (no subagents authorized): no default changes, model only sees
  existing captured `catalog_index()` and explicitly host-approved IDs,
  current source/owner checked after its output, no model-generated data ever
  passed to source invocation. **Deferred E0 limitation:** the supplied model
  callback itself lacks an in-function deadline/cancellation, so hosts must
  guard generation separately. This is not a production-safe model endpoint
  or independent model quality evidence.
