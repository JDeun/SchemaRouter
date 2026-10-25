# Original-paper Understood Direct Plan Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans for task-by-task native implementation. Steps use RED/GREEN TDD and verify both behavior and source safety.

**Goal:** Implement an opt-in, source-scoped Algorithm 1 `Understand`→host intent required fields→explicit named-tool direct typed plan, without changing defaults or execution authority.

**Architecture:** The source-owned `NativeConceptCatalog` supplies immutable field semantics; a bounded host intent map unions requirements with untrusted model concept hints. The existing semantic posting index filters named tools pre-K, and P2's existing tool-call materializer attaches exact original fields and metadata. All publication requires live source revalidation.

**Tech Stack:** Python 3.10+, Pydantic v2, `NativeSchemaPostingIndex`, `NativeSchemaGraphIndex`, existing `PaperTypedToolPlan`, pytest, Ruff.

**Spec:** `research/autoresearch/paper-understood-direct-e0-design.md`

## Global Constraints

- Research E0 opt-in, strict K=5; no default `retrieve[_authorized]`, agent/executor, release #1356, benchmark gold or protected branch modifications.
- No guessed source contracts, LLM-granted rights, silent top-five, hidden fields/names, new graph/tool catalog, or model parameter execution.
- Use current source policy and principal scope before K and again before publishing. E2 #1346/#1477 remains blocked.

## Review Focus

1. A sixth named eligible route must be selectable before K, without exposing siblings or changing default behavior (Task 1 and 2).
2. Unknown/hidden/denied tool names must never surface in a public receipt or count (Task 1 and 2).
3. Required intent field B cannot be discarded by model concept A (Task 2).
4. Mid-call policy/index/catalog/intent or availability mutation must not publish a stale plan (Task 2).
5. LLM parameter hints must never be bound or mistaken for execution authority (Task 2).

---

### Task 1 — Source-verified exact-tool posting filter

**Files:** `src/schemarouter/native_semantic_index.py`; `tests/test_native_semantic_index.py`.

**Interfaces:** Consume `NativeSchemaPostingIndex.lookup(router, query, group, principal, k=5)`; produce optional keyword `allowed_tool_keys: tuple[str, ...] | None = None` with same `IndexedNativeFieldResult` contract.

- [ ] RED: add `test_indexed_named_sixth_tool_is_filtered_before_k` using 7 source-valid equal candidates, literal expected sixth original route and no siblings; assert unfiltered `over_k_unranked`. Add malformed/unknown tool and policy-hidden negative cases.
- [ ] Run `.venv/bin/python -m pytest -q tests/test_native_semantic_index.py -k named_` and observe expected unsupported-parameter failure.
- [ ] GREEN: validate 1–5 unique bounded exact keys; apply set membership at original `tool_key` lookup before any candidate admission. Preserve all existing final checks.
- [ ] Run `.venv/bin/python -m pytest -q tests/test_native_semantic_index.py` and verify green.
- [ ] Commit the isolated Task 1 files.

### Task 2 — Host intent union and untrusted structured tool selection

**Files:** new `src/schemarouter/paper_understood_direct_plan.py`; new `tests/test_paper_understood_direct_plan.py`.

**Interfaces:** Consume `NativeConceptCatalog`, `NativeSchemaGraphIndex`, `PaperFieldRoute`, `_compile_one_route`, `_check_current_call_scopes`, and Task 1's filtered posting index; produce `PaperIntentDeclaration`, `PaperIntentRegistry`, `PaperUnderstanding`, `compile_paper_understood_direct_plan(...) -> PaperTypedToolPlan` (research module only, no public default or executor).

- [ ] RED: tests for seven-route K overflow vs named sixth, intent A+B union excluding A-only, unknown tool no-hit, source/license/permission/hidden scope refusal, declared concept/intent errors, source mutation, and model parameter hints not becoming `ToolCall.arguments`.
- [ ] Run `.venv/bin/python -m pytest -q tests/test_paper_understood_direct_plan.py` and observe missing API failure.
- [ ] GREEN: implement bounded Pydantic declarations, source-owned field union, canonical internally derived lookup alias, typed route receipt projection and repeat lookup. Explicit source type constraint only narrows. Compile only candidate original direct routes; status uses existing P2 receipt types.
- [ ] Run `.venv/bin/python -m pytest -q tests/test_paper_understood_direct_plan.py tests/test_paper_typed_tool_plan.py tests/test_paper_field_retrieval.py tests/test_native_semantic_index.py` and verify green.
- [ ] Commit Task 2 files.

### Task 3 — Review, evidence and handoff

**Files:** update `research/autoresearch/paper-understood-direct-e0-design.md` with precise E0 limitations if results differ; record final evidence in this plan. Existing `research/autoresearch/paper-indexed-agent-bridge-e0.md` may link the new Draft.

- [ ] Run focused pytest, `ruff check`, Pyright and repository-wide pytest; report all failures/timeout without overclaim.
- [ ] Confirm no untrusted model payload, default route, existing agent or source authority change in the diff; inspect output metadata and negative paths.
- [ ] Publish an isolated stacked Draft on #1754 only if authenticated GitHub connector remains available; compare local and remote Git tree SHA. Do not merge.
- [ ] Record E0_ONLY; independent E2 #1346/#1477 and release #1356 HARD HOLD.

**Approval/execution:** Previously approved direct sequential A-option; the user explicitly opted out of routine approval questions on 2026-10-25. Native sequential execution continues under the existing authorization boundaries.

## 2026-10-25 implementation checkpoint

- Task 1 RED reproduced: 8 failures for the absent `allowed_tool_keys` argument. GREEN: `tests/test_native_semantic_index.py` **71 passed**. Exact-tool filtering is before candidate qualification/K, with original principal/source validation unchanged.
- Task 2 RED reproduced: missing `schemarouter.paper_understood_direct_plan` import. GREEN: `tests/test_paper_understood_direct_plan.py` **11 passed**; combined paper P1/P2 and posting-index regression **118 passed**.
- Fresh `ruff check .`: **all checks passed**. Full Pyright over the local optional-dependency environment reports **21 existing errors** in untouched adapters/integrations/provider profile/document loader; **no errors in the changed files** after correcting one newly introduced `Literal` status type issue.
- Full repository `timeout 55s .venv/bin/python -m pytest -q`: **timed out with exit 124** after reaching ~12% of the suite; no full-suite success is claimed. Earlier isolated full-suite work on the stacked parent also observed the unrelated synchronous capability-removal test stall.
- This is **E0_ONLY**. `PaperUnderstanding` is a pre-parsed untrusted input, not a shipped LLM Understand parser; model `parameter_hints` are explicitly not bound to invocation arguments. Direct-only results, no new producer/consumer join, no calibrated no-fit or E2 quality claim. #1346 and #1477 are `BLOCKED_EXTERNAL`, #1356 remains `HARD HOLD`.
