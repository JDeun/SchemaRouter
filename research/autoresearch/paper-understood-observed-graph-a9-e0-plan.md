# A9 E0 Named Graph Execution Plan

**Goal:** Complete the bounded opt-in original `Understand` 1-/2-hop
observation-to-execution vertical slice without duplicating the executor.

**Architecture:** Extend the existing named G5 compiler for approved host
root arguments; implement one explicit async bridge in the existing paper
consumer execution module. Reuse original edge scalar validation and the
existing registered SchemaRouter executor. Detailed design:
`paper-understood-observed-graph-a9-e0-design.md`.

**Stack:** Python 3.12, pytest/pytest-asyncio, Ruff, Pyright, GitHub Actions.

### Task 1 — RED source-bound one/two-hop execution tests

- [x] Write one-/two-hop registered-executor tests including observed ID
  forwarding, 1-call-per-node budget, exact named target and host inputs.
- [x] Write fail-closed adversarial tests for result type/presence, policy,
  principal/source mutation, forged model parameter, no proof and retry.
- [x] Capture expected RED before implementation: 19 failures for the absent
  opt-in function/host-parameter interface.

### Task 2 — GREEN opt-in bridge

- [x] Extend the existing G5 graph compiler for approved root values only.
- [x] Execute current complete typed DAG serially through `router.execute`;
  reuse original typed observation checker for both edges.
- [x] Check source/identity/typed shape before and after each await and
  observation; preserve non-E2/non-executable provenance flags.

### Task 3 — Verification and safe continuation

- [x] Run focused + relevant original paper regressions and Ruff/Pyright:
  **27 new A9 tests**, **193 passed** including G5 two-hop, host-root,
  original typed plan, observed consumer and real scoped-agent regression;
  repository Ruff green, changed runtime modules Pyright 0 errors.
- [x] Self-review security transitions and handle regressions before publish:
  root/middle/target policy, deep principal owner snapshots, typed route
  contracts and exact one-call budget; empty identifier fail-closed fixed.
- [x] Update the canonical resume, issue #1560 and Draft #1755 with exact
  passing evidence; publish without merging and wait exact-head CI.
- [x] Keep A9 broader qualification and #1356 HOLD explicitly open.

**First published A9 head CI forensic result (2026-10-26):** commit
`1a20df99c7e32a3ab5f7581e4150acb8a42fe081`, tree
`966934f8595cf253a94347ae81ff169e69d2b938` had **29 successful and
6 failed** workflow runs. [CI #7184](https://github.com/JDeun/SchemaRouter/actions/runs/40270899439)
and five other workflows all failed the *same* intentionally frozen
`tests/test_public_api.py::test_public_framework_exports_are_intentional_and_stable`
comparison: the two newly public A9 names were missing from its expected
`__all__`. Example minimum-dependencies job had **6394 passed, 11 skipped,
2 deselected, 1 failed** (the public ABI list), not an execution regression.
Verified local RED in `tests/test_public_api.py`, then explicitly updated
the public ABI expectation. This first remote head is **not green**.

### Task 4 — Scoped one-shot model → existing observed executor (next E0 slice)

- [x] RED: registered 1-/2-hop end-to-end with one scoped Understand model
  call; missing host inputs/unknown target/empty captured menu trigger no I/O.
- [x] RED: mutations during model analysis/tool execution, source-scope
  mismatch and model parameter forgeries cannot execute a foreign input.
- [x] GREEN: an opt-in wrapper reuses the **same** scoped model callback and
  A9 observed executor, pins `AuthorizedAgentToolSurface` before/after, and
  requires every planned route to belong to its captured visible route IDs.
- [x] Verify focused regressions and update handoff; publish follow-up to
  the **same Draft** only after the preceding exact-head CI is accounted for.

**Task 4 local evidence:** Seven initial missing-module RED tests; seven
GREEN real scoped one/two-hop integrations in
`scripts/research_paper_scoped_observed_graph_a9_e0.py`. Following the ABI
fix, expanded 15-file regression suite **283 passed**, repository Ruff
green, changed implementation Pyright **0 errors/0 warnings**, Git diff
whitespace clean. The explicit wrapper leaves the existing A5 fixed5 agent
unchanged; it does not claim automatic natural-language answer synthesis.

### Exact-head A9 protected CI closeout — 2026-10-26

- **Qualified Draft code HEAD:**
  `5683426c7ea6adf41d53ec699741e042e2e2db41`, Git tree
  `5b344964eea83d1f08e7abac634e025bbfe43f09`. **35/35 returned PR
  workflows completed successfully** for this exact code head, including
  the original typed-paper A9 Python 3.12 workflow, native graph/ABI checks,
  fixed5 model Qwen CPU research and cross-platform package checks.
- [Main CI #7185](https://github.com/JDeun/SchemaRouter/actions/runs/40273198187):
  Linux Python 3.12 **6482 passed, 3 skipped in 798.88s**, coverage
  **85.02%**, above the protected 84% floor. Full protected job suite
  concluded success; **no CodeQL success claim** for the stacked non-main
  Draft target.
- This documentation-only update, when published, creates a **new SHA** and
  needs its **own exact-head CI**. Do not transfer the code-head result to it.
- A9 external provenance, semantic/agent-output quality and independent E2
  **remain unchecked**. This checklist confirms the E0 implementation and
  CI only, not default agent promotion or #1356 release readiness.
