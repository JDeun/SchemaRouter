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
- [x] Publish exact remote Draft code HEAD `6f35b57c8f0d2dd0618ccc43b392dd7cff82d7f4`,
  tree `b179d92d558b8fb60fcf0afa08373ec9d364233d`, matching local
  reviewed tree. **29/29 PR workflows successful**; [main CI #7180](https://github.com/JDeun/SchemaRouter/actions/runs/40263102244)
  Linux Python 3.12 **6436 passed / 3 skipped**, coverage **85.00%**.
- [x] Update issue #1560 and Draft #1755 with the code and qualification
  evidence; canonical handoff updated in this docs-only follow-up. Full A7
  remains unchecked without authentic provider/independent paired data.
- [ ] Confirm exact-head CI for this subsequent documentation-only commit;
  previous code-head green cannot be inherited silently.
