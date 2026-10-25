# Named-tool Graph Understand E0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use RED/GREEN TDD.

**Goal:** Compile original-paper model named-tool understanding into source-attested 1-/2-hop typed non-executing calls.

**Architecture:** Reuse one source-owned intent→FieldGroup builder, the canonical native G5 graph, and P2 `_compile_one_route`. An explicit, no-privilege named target prefilter acts before K in both existing graph searches. Re-verify exact graph and receipts after materialization.

**Tech Stack:** Python, Pydantic v2, pytest, Ruff, Pyright.

**Spec:** `research/autoresearch/paper-named-graph-understand-e0-design.md`

## Global Constraints

- Default behavior and existing fixed5 direct agent selector unchanged.
- No independent semantic fit, no model parameter execution, no hidden tool disclosure, no new executor or tool registry.
- Return entire source-typed route+binding evidence or an empty abstention; exactly K5.
- Continue on existing stacked Draft #1755 only; release #1356 and independent E2 hold.

## Review Focus

1. Six matched targets with one explicitly named sixth: qualify before K; test Task 1.
2. Revoked/hidden intermediate with available final consumer: no partial path; test Task 2.
3. Duplicate paths reusing a root: count unique **exposed** route IDs, reject >K; test Task 2.
4. Availability/policy change after first graph proof: generic failure, no partial receipt; test Task 2.
5. Forged model parameters and tool name absent from current source: unbound/refuse; test Task 2.

---

### Task 1 — Structural pre-K target filter in canonical G5

**Files:** Modify `src/schemarouter/native_graph_index.py`; test `tests/test_native_graph_two_hop.py` and `tests/test_native_graph_one_hop.py` or existing G5 unit tests.

**Interfaces:** `NativeSchemaGraphIndex.lookup(..., allowed_target_routes: frozenset[str] | None = None)` and `lookup_two_hop(..., allowed_target_routes: frozenset[str] | None = None)`; never authorize by filter alone.

- [ ] RED: six source-qualified target routes overflow unfiltered K; pre-K one exact sixth target is complete for both 1-/2-hop. Reject malformed filter input.
- [ ] Run targeted pytest; expect TypeError for missing named argument.
- [ ] GREEN: bounded filter contract and structural target intersection before source-qualified path expansion in both methods; preserve existing private fork filter behavior.
- [ ] Run target one-/two-hop G5 tests, source-scope tests, Ruff.
- [ ] Commit code and tests.

### Task 2 — Source-owned structured Understand graph plan

**Files:** Modify `src/schemarouter/paper_understood_direct_plan.py` to share semantic owner demand; create `src/schemarouter/paper_understood_graph_plan.py`; test `tests/test_paper_understood_graph_plan.py`.

**Interfaces:** `compile_paper_understood_graph_plan(router, understanding, *, principal, catalog, intent_registry, index, k=5, max_hops=2) -> PaperTypedToolPlan`.

- [ ] RED: direct still valid; named 1-/2-hop complete binding receipts; named sixth before K; no named tool, denied/hidden/type-unproven, >K, owner/policy drift, parameter hints untrusted; never call execute.
- [ ] Run targeted pytest; expect missing API import failure.
- [ ] GREEN: construct exact shared FieldGroup, prove eligible named final routes using existing G5 pre-K filter, materialize P2 receipts in topological order, compare second proof and receipts, fail closed on source changes.
- [ ] Run new tests + existing paper/G5/agent regressions, repo Ruff, scoped Pyright; whole-suite attempted with bounded wait and limitations reported.
- [ ] Commit code and tests.

### Task 3 — Handoff and published stacked Draft checkpoint

**Files:** Update `research/autoresearch/paper-toolcall-implementation-e0.md`, this plan; Draft #1755 description.

- [ ] Record exact status and behavior through Task 2, distinguish E0 from independent E2.
- [ ] Publish commits safely to same stacked remote Draft after matching source Git tree, check exact-head CI.
- [ ] Leave PR Draft/unmerged and #1356 HOLD; final self-review (no subagents authorized).
