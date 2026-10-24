# Original Paper Observed Binding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (or subagent-driven-development) to implement this plan task-by-task. Steps use checklist (`- [ ]`) syntax.

**Goal:** Turn the original-paper P2 typed *deferred* consumer calls into non-executing, explicitly observed argument receipts by executing the **single approved producer** through the existing SchemaRouter executor exactly once.

**Architecture:** Reuse `compile_paper_typed_tool_plan` and native G5 `materialize_native_observed_arguments`. Execute a fingerprint-pinned original producer only via `router.execute` with principal and one-call budget; validate each consumer against a newly refreshed exact native one-hop proof under a per-consumer owner-declared FieldGroup. Return a new bounded non-executable receipt of calls and a real executor `ToolResult`, never execute leaves automatically or treat provider origin as independently authenticated.

**Tech Stack:** Python 3.10+, Pydantic, pytest/pytest-asyncio, Ruff. No new runtime dependencies.

**Spec:** `research/autoresearch/paper-toolcall-implementation-e0.md`; original paper §4 Algorithm 1, issue #1560, Draft #1748.

## Global Constraints

- All APIs opt-in and exactly K=5; default plan/retrieve/execute unchanged.
- Need owner-reviewed `NativeConceptCatalog`, explicit principal, current original source graph index and authorization.
- Do not infer arguments from text, fabricate `ToolResult`, join unrelated providers or add an independent ranker/agent.
- Source is executed at most once; consumer calls remain unexecuted and carry no execution authorization.
- Callback/private source errors are not incorporated into public route receipts; final data-scope, policy and schema checks remain active.
- Independent actual-data E2 and measured agent answer quality remain separate gates; #1356 release HOLD.

## Review Focus

- Malformed or absent root identifier: no consumer argument disclosure or execution.
- Root requires host input but none given: reject before invoking anything.
- Source/policy/field visibility revocation after observed producer: reject without leaf execution.
- Multiple consumers require the *same original* root and typed scalar edge; no arbitrary graph joining.
- Provider output is an executor observation, not independent provider identity or E2 evidence.

---

### Task 1: Actual producer observation → typed deferred consumer binding

**Files:**
- Create: `src/schemarouter/paper_observed_binding.py`
- Test: `tests/test_paper_observed_binding.py`
- Modify: `src/schemarouter/__init__.py`, `tests/test_public_api.py`

**Interfaces:**
- Consumes: `compile_paper_typed_tool_plan`, `retrieve_paper_field_coverage`, `resolve_native_concepts`, `index.lookup`, `materialize_native_observed_arguments`, `SchemaRouter.execute(ExecutionPlan, RunConfig)`.
- Produces: `async observe_and_bind_paper_plan(router, query, *, principal, catalog, index, host_source_arguments=None, alternative_index=0, k=5) -> PaperObservedBinding` with `.producer: ToolResult`, `.plan: PaperTypedToolPlan`, `.executable_authority=False`, `.independent_e2=False`.

- [x] **Step 1:** Add test: one registered read-only root with two typed consumers and actual invokers. Assert root executes **once**, zero leaves, generated bound `ToolCall.arguments` equal literal ID and original bindings unchanged. Must fail with missing API.
- [x] **Step 2:** Run new test; observe RED from missing feature.
- [x] **Step 3:** Implement minimal opt-in source execute + per-edge current G5 observation validation + recompile/revalidate + receipt.
- [x] **Step 4:** Focused test GREEN, then existing P1/P2/host-root and public API tests.
- [x] **Step 5:** Add negative tests for missing approved root inputs, invalid/absent producer ID, wrong source contract and source revocation; confirm no leaves invoked. Resolve regressions RED→GREEN.
- [ ] **Step 6:** Commit isolated, update PR #1748 and implementation handoff with exact evidence; full CI/code scan remains an independent gate.

### Task 2: Source-identity and review gates

**Files:**
- Modify: `research/autoresearch/paper-toolcall-implementation-e0.md`
- Modify: `.github/workflows/original-paper-toolcall-plan-e0.yml`

**Interfaces:**
- Consumes: Task 1's bounded observed binding API and negative tests.
- Produces: E0 source-authored acceptance and cross-session continuation; no release/default promotion.

- [x] **Step 1:** Extend targeted workflow to run observed producer binding regression.
- [x] **Step 2:** Update handoff to distinguish actual executor observation from independent provider authentication/E2.
- [ ] **Step 3:** Run full Ruff and focused + full repository pytest (record incomplete/blocking tests honestly).
- [ ] **Step 4:** One whole-branch code review and fix Important/Critical findings RED→GREEN; publish GitHub Draft via exact tree hash and compare head-specific CI.

## Review finding and ruling (2026-10-24)

Independent whole-slice review found a real completeness error: the first observed binding did a **public unfiltered G5 subset lookup** even after P1 source-attested a same-root fork. Six unrelated status-typed one-hop routes triggered `over_k_unranked` while the correct P1 fork stayed complete. A new test reproduced RED then GREEN. **Ruling:** use G5's *existing private source/target bounded fork-arm proof*, but exclusively for the **already P1-selected exact original pair**, before producer execution and before/after its scalar validation; retain public K5 and all original authorization, scope, fingerprint and health checks. Refactored the existing G5 observation scalar checker as a private reusable helper instead of writing a second permissive validator. **Cost if wrong:** could reject valid proven forks or expose unrelated private route counts; the regression asserts only the same three original routes and one root invocation with zero leaves.

Local focused suite covering native observation, P1/P2/public API and new executed-root binding: **159 passed**, Ruff repository-wide green. Full-suite and new SHA-specific CI still to be recorded; independent E2 remains blocked.

## Documentation audit routing ruling (2026-10-24)

The project's whole-corpus Korean editorial audit **requires every new `docs/**/*.md` page to have independently reviewed source/translation pairs recorded by exact blob in `audits/ko-direct-semantic-spotcheck-2026-10-12.json`**. Putting this implementation-internal plan under `docs/superpowers/plans` caused an observed CI failure; artificially extending the reviewed ledger would falsely certify human work. **Ruling:** keep this new E0 internal plan in `research/autoresearch/` alongside the canonical handoff, outside the bilingual public-documentation corpus. This preserves the real audit gate without suppressing it. Cost if wrong: future tooling expecting plans under `docs/superpowers/plans` must use this explicit handoff link; cross-session entry remains recorded in the canonical research handoff and PR.
