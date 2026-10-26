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
- [ ] Update the canonical resume, issue #1560 and Draft #1755 with exact
  passing evidence; publish without merging and wait exact-head CI.
- [ ] Keep A9 broader qualification and #1356 HOLD explicitly open.
