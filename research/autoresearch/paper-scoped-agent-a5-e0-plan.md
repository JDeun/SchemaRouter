# Scoped Paper A5 E0 Completion Plan

> **For agentic workers:** Use the existing source-scoped A5 code and TDD;
> the original graph contract precedes any newer A5 adapter convenience.

**Goal:** Fix the latest Python 3.12 graph regression while preserving an
actual bounded source-safe Understand → fixed-K agent E0 vertical slice.

**Architecture:** `analyze_paper_understanding_scoped` produces untrusted
hints, G5 produces non-executing typed receipts, the A5 adapter narrowly
handles missing ordinary direct scalars, and the existing
`run_generated_episode` is the only agent executor.

**Tech Stack:** Python 3.12, Pydantic v2, pytest, Ruff, Pyright, Actions CI.

**Spec:** `research/autoresearch/paper-scoped-agent-a5-e0-design.md`.

## Global constraints

- Exactly K5; no default change, no model parameter authorization.
- A graph-only missing dependency remains `no_proven_hit`.
- An unobserved 1/2-hop DAG is not an executable route menu.
- Source policy, principal, license, availability and fingerprints are authoritative.
- #1346/#1477 independent E2 blocked; #1356 release HARD HOLD.

## Review focus

1. Named 1/2-hop target must not short-circuit on direct missing inputs.
2. Missing typed identifier cannot be mistaken for ordinary host scalar.
3. Denied/hidden intermediate or source mutation cannot disclose partial DAG.
4. Valid source-only direct input must remain a distinguishable deferred request.
5. Supported empty-menu episode must record failure with zero tool attempts.

### Task 1: Restore graph-only semantics

**Files:** `src/schemarouter/paper_understood_graph_plan.py`,
`tests/test_paper_understood_graph_plan.py`.

- [x] RED: previous Python 3.12 exact-head full CI produced 10 related
  failed graph tests; reproduced locally with the same 10 failures.
- [x] GREEN: restore `requires_arguments` as an eligible graph lookup,
  retaining direct `ready` precedence and named-only exploration.
- [x] Targeted graph regression passes locally.

### Task 2: Preserve a safe A5 direct missing-scalar diagnostic

**Files:** `scripts/research_paper_scoped_plan_e0.py`,
`tests/test_research_paper_scoped_agent_real_e0.py`.

- [x] RED: missing typed semantic identifier unexpectedly reached the agent.
- [x] GREEN: recover a single verified direct `requires_arguments` receipt
  only for all-untyped, source-declared missing inputs and only after graph
  returns `no_proven_hit`.
- [x] Review RED: model omission of `named_tools` bypassed the guard through
  the graph compiler's existing direct compatibility branch. GREEN: apply
  the exact same source-declared scalar gate to all A5 `requires_arguments`
  results; an unproved semantic input now yields empty generic abstention.
- [x] Verify unnamed ordinary scalar still yields `request_arguments`.
- [x] Review RED: 33 denied named endpoints returned `budget_unsatisfied`
  versus `no_proven_hit` for unknown name; GREEN: scope current eligible
  targets before the G5 route cap, preserving canonical graph authorization.
- [x] Verify both denied and field-hidden 33-endpoint names remain
  indistinguishable from unknown under principal scope.
- [x] Add actual one/two-hop fixed5 episodes and verify no DAG flattening,
  zero generations/attempts, and supported-case fail-closed outcome.
- [x] Final local related scope: 140 passed, Ruff all passed, targeted graph
  Pyright 0 errors.

### Task 3: Remote exact-head qualification and handoff

**Files:** this plan, canonical
`research/autoresearch/paper-toolcall-implementation-e0.md`, Draft #1755.

- [x] Published atomic source/test/handoff changes on Draft #1755, latest
  verified code head `24a8cb0448c399f10dbe1dc86c898cbb8d328799`;
  Git tree `68731e2770a1eb143bf7901ec6afe60899d27117` matches local.
- [x] Full protected CI for **that exact code HEAD** passed: all 28 returned
  PR workflows successful, main run `40251600240`, Python 3.12 6403 pass /
  3 skip, coverage 85.00%, CI typecheck and Ruff pass.
- [ ] Separately obtain CodeQL check evidence when available; it did not
  appear among the 28 PR-workflow results returned by the connector.
- [x] Marked A5 E0 checked in canonical checklist with qualified code-head
  evidence; docs-only publication has a separate CI lifecycle.
- [x] Recorded A6/A7 next work, exact qualified SHA and #1560 checkpoint.
