# Original Algorithm 1 A7 Paired E0 Adapter Implementation Plan

> **For agentic workers:** TDD, reuse the existing source-scoped fixed5
> executor and A7 stage meter. Do not merge or publish as E2 qualification.

**Goal:** produce a fair, original-source-fixed paired *mechanical* comparison
without changing the agent model, source authorization, K5, or private gold.

**Files:** new `scripts/research_paper_paired_agent_e0.py`, its tests,
existing `.github/workflows/original-paper-toolcall-plan-e0.yml`, this plan
and canonical `paper-toolcall-implementation-e0.md`.

## Task 1 — pair admissibility and full episodes

- [x] RED: same host-declared agent/model configuration and fresh instances
  yield two real original scoped/agent traces; baseline uses first five
  source-authorized ranked routes, paper uses the previously proved plan.
- [x] RED: reused object, different class/revision/seed, invalid task or
  source drift rejects before any publishable paired result.
- [x] RED: empty menu invokes zero agent/model callbacks; bad model usage or
  task mutation during one episode aborts pair without publishing partials.
- [x] GREEN: compose original fixed5 baseline and A7 measured paper only;
  do not introduce an agent or executor of our own.
- [x] RED→GREEN: exact two-turn baseline schema bytes, distinct from
  provider-reported token counters; nonfinite private fixture input fails
  before the agent/model factory or any scoring.

## Task 2 — verification and continuation

- [x] Verified 229 relevant Python3.12 A5/A6/A7/legacy regression tests,
  repository-wide Ruff and changed-script Pyright (0 errors), diff checks.
- [x] Independent reviewer approved E0 Draft engineering (no Critical or
  Important outstanding); a separate read-only review ran 447 scoped tests
  and rechecked authorization, gold redaction, sampling and owner drift.
- [ ] Publish exact remote Draft tree and qualify CI on Linux Python3.12.
- [ ] Update issue #1560, Draft #1755, canonical handoff; full A7 stays
  unchecked without authentic provider/independent paired qualification.
