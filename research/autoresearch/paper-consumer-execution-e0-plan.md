# Original Paper Bounded Consumer Execution E0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Execute actual original-paper P2 consumer tools, each through current independent executor authorization and a one-call/one-attempt budget, after a separately observed real producer.

**Architecture:** A new *explicitly opt-in* async entry point owns the complete `observe_and_bind_paper_plan` transaction internally. It never accepts a caller-crafted binding/`ToolResult` or promotes a deferred plan into execution authority. Sequentially execute at most `K-1` source-proven read-only consumers, re-proving the unchanged original P2 shape and all current scopes before each call and after each result. Return a bounded run receipt only after every original call succeeds; no default executor or planner change.

**Tech Stack:** Python 3.10+, Pydantic, existing SchemaRouter executor, pytest, Ruff; no runtime dependencies.

**Spec:** `research/autoresearch/paper-toolcall-implementation-e0.md`; original paper §4 Algorithm 1; issue #1560 and Draft #1748.

## Design decisions and alternatives

- **Chosen: sequential one-call consumer execution with fresh proof per step.** Easy to audit/abort on revocation, 1-call budgets, no hidden retries, no consumer execution before a real producer ID.
- **Not chosen: batch every consumer in one `ExecutionPlan`.** A single authorization snapshot could become stale across leaves; one consumer could mutate availability/policy before another begins.
- **Not chosen: accept externally provided `PaperObservedBinding`.** Dataclass receipts are constructible by callers and do not confer execution authority; this would make fabricated observations a possible entry point.
- Source-owner-attested ID binding only; no query-parsed values, joins, ranking, unrelated one-hops, writes, tool retries or automatic production integration. Current executor can reauthorize at actual entry, but provider I/O is not atomic with metadata revocations. Independent E2 remains blocked.

## Global constraints

- Exactly `k=5` and a P1-selected complete original route set; root once, at most four consumers, each read-only and scope-visible.
- Consumer calls are derived solely from the internal actual `ToolResult` and source typed bindings; no arbitrary receipt input.
- One root execution budget and a **separate** one-call/one-attempt budget for each selected consumer; no cross-branch retry/fallback, no parallel calls.
- Recompile original plan and match original call shapes/route order/bindings/snapshot before and after each consumer; recheck all current argument scopes. Executor still independently authorizes each call.
- Fail closed on any changed policy/health/registry/field/projection/identifier, and never return partial consumer results.
- Do not claim independent publisher provenance, E2 accuracy or release readiness. Draft PR #1748 and #1356 HOLD remain.

## Review focus

- After the root, a consumer is revoked or lacks binding: **no unauthorized consumer invocation**.
- Leaf 1 changes authorization/availability for leaf 2: leaf 2 must not run, and no partial receipt is published.
- A consumer returns a result for an unrelated tool/endpoint: refuse to publish a misleading combined receipt.
- A consumer's required input becomes more restrictive: fail before passing a stale bound scalar to the invoker.
- A transient consumer fails: do not retry, execute another leaf, or pretend a complete result.

---

### Task 1: Actual bounded consumer execution behind an opt-in entry point

**Files:**
- Create: `src/schemarouter/paper_consumer_execution.py`
- Create: `tests/test_paper_consumer_execution.py`
- Modify: `src/schemarouter/__init__.py`, `tests/test_public_api.py`

**Interfaces:**
- Consumes: `observe_and_bind_paper_plan`, `compile_paper_typed_tool_plan`, `_check_current_call_scopes`, `SchemaRouter.execute`, `RunConfig` and `ExecutionBudget`.
- Produces: `async observe_and_execute_paper_plan(router, query, *, principal, catalog, index, host_source_arguments=None, alternative_index=0, k=5) -> PaperExecutedToolSequence`; `PaperExecutedToolSequence(producer: ToolResult, consumers: tuple[ToolResult, ...], plan: PaperTypedToolPlan, executable_authority=False, independent_e2=False, provider_provenance_verified=False)`.

- [x] **Step 1 (RED):** Test real registered root + two consumers: root exactly once, each leaf once with observed ID, expected data; same EN/KO/JA and original metadata. Public API missing => observed RED.
- [x] **Step 2 (GREEN):** Implement minimal opt-in 1+N serial executor with per-consumer one-call budget and original P2 equality check (restore deferred consumer args in a comparison copy). Scope and source proof rechecked before/after each call. Verified GREEN.
- [x] **Step 3 (RED→GREEN):** Add revocation after root, revocation after leaf1, wrong returned identity, transient consumer failure and host-1:1 tests; absent output field RED→GREEN; verify no partial result.
- [x] **Step 4:** Focused P1/P2/G5/real-adapter/public-API **172 passed**, Ruff green. Full repo pytest with 240 s cap timed out at ~12%; no full pass assertion.
- [x] **Step 5:** Code/test and documentation commits `ee25f98`, `6c11bba`; independent whole-slice review completed, two Important issues fixed with separately reproduced RED→GREEN, no unaddressed Important findings.

### Task 2: Research handoff, regression workflow and GitHub Draft continuation

**Files:**
- Modify: `research/autoresearch/paper-toolcall-implementation-e0.md`, `.github/workflows/original-paper-toolcall-plan-e0.yml`.

**Interfaces:**
- Consumes: Task 1 public opt-in function and verified tests.
- Produces: canonical restart instructions and exact CI gate, no release promotion.

- [x] **Step 1:** Add consumer execution regression to paper focused workflow, record E0 vs independent E2 boundary and security guardrails in handoff.
- [ ] **Step 2:** Verify targeted CI-parity commands; commit and publish via exact-tree GitHub PR #1748 CAS update, issue #1560 status and current SHA actions.

## Rulings

- **Location:** Plans live in `research/autoresearch/` rather than `docs/superpowers/plans/` because the latter has a whole-corpus human-reviewed bilingual provenance gate; do not invent editorial review to satisfy CI.
- **Approval:** The project continuation uses the user's previously approved A-option direct sequential execution of original Algorithm 1; no branch merge/release authority implied.
- **Review Important 1 — fixed:** A mutable host principal could switch tenants between source/leaf calls while preserving the same selected route shape. RED→GREEN tested mutation after producer and first leaf. Use an original-claims snapshot + deep pinned executor principal and reject either identity change at every await boundary (also in stand-alone observed binding). Cost if wrong: cross-tenant use of a real source ID.
- **Review Important 2 — fixed:** Checking literal top-level field names rejected valid nested/wildcard `result_path` projections. RED→GREEN tested nested `details.state` / `metadata.owner`. Check the normal executor's actual `ToolResult.field_contracts` presence instead; empty batch is a legitimate no-match response. Cost if wrong: false negative on source-attested paths or acceptance of absent projected data.
- **Review Minor — deferred:** `has_observed_value=False` for an explicitly present `null` means no factual value although field contract is present. E0 accepts it as an invocation with an explicitly null field, **not** factual evidence or E2 correctness. Future answer-quality evaluation must treat these separately.
