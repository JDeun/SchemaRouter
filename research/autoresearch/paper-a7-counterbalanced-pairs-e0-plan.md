# A7 counterbalanced paired agent E0 implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:executing-plans with test-driven-development. The user already
> authorized direct sequential implementation, one Algorithm 1 item at a time.

**Goal:** Rehearse existing A7 baseline/paper agent comparison in both
execution orders without changing route authorization, fixed5 execution or
independent-gold claims.

**Architecture:** Add a strict order branch to the current paired adapter,
then an all-or-nothing two-trial wrapper that validates fresh Understand
callbacks and all four agent instances. Existing A7 metrics remain intact.

**Tech Stack:** Python 3.10+, pytest-asyncio, Ruff, Pyright, GitHub Actions.

**Spec:** `research/autoresearch/paper-a7-counterbalanced-pairs-e0-design.md`.

## Global Constraints

- Research-only E0; never change default selector or route/agent executor.
- Preserve exact host source/role/owner/task proof and K5; never reveal gold.
- No unsupported provider-independence, E2 or statistical-order claim.

## Review Focus

- A bad order cannot invoke even the agent factory or Understand callback.
- Paper-first execution must genuinely run before the baseline, not only
  swap returned labels.
- All four agent instances must be distinct and have exactly the same
  strict configuration, even across two pairs.
- Provider model callback objects must be fresh and of the same concrete
  type; mismatch fails before any episode.
- Mutation/error in the second trial cannot yield a seemingly complete
  crossover record or expose private original task/gold data.
- Mutating source-owner declarations or hidden gold **inside model_factory**
  before the first pair cannot redefine the evidence baseline.

## Task 1 — strict AB/BA on the original paired executor

**Files:** `scripts/research_paper_paired_agent_e0.py`,
`tests/test_research_paper_paired_agent_e0.py`.

**Interfaces:** `run_paper_paired_agent_e0(..., execution_order:
Literal["baseline_first", "paper_first"] = "baseline_first")`;
the existing `PaperPairedAgentE0` gains its literal `execution_order`.

- [ ] RED: test actual agent/model invocation order and reject invalid order
  before calling either branch. Existing baseline-first callers still pass.
- [ ] GREEN: factor the same two existing branch executions into local
  helpers and sequence them based on the strict order, rechecking before
  and after each branch.
- [ ] VERIFY: run focused A7 paired tests, Ruff and targeted Pyright.

## Task 2 — source-safe two-order crossover

**Files:** `scripts/research_paper_paired_agent_e0.py`,
`tests/test_research_paper_paired_agent_e0.py`.

**Interfaces:** `run_paper_counterbalanced_agent_e0(model_factory,
agent_factory, *, view, task, catalog, intent_registry, index,
model_visible_intent_ids, model_visible_concept_ids)` returning immutable
`PaperCounterbalancedAgentE0(baseline_first, paper_first, ...)`.

- [ ] RED: four distinct matching agents/two fresh Understand callbacks,
  correct AB/BA side effects, sanitized receipts and no independent E2.
- [ ] RED: cross-trial config/class/object reuse, callback reuse, second
  trial failure and source drift reject without result publication. Require
  explicit RED tests for model-factory gold/owner mutation before first pair.
- [ ] GREEN: validate model factory before any run; use guarded original
  agent factory across both calls to the original paired function. Pin the
  task digest and owner snapshot before model factories and verify after each
  factory and trial.
- [ ] VERIFY: focused and scoped regression suites; repository Ruff,
  changed-module Pyright, CI workflow YAML and `git diff --check`.

## Task 3 — integration evidence and publication

**Files:** `.github/workflows/original-paper-toolcall-plan-e0.yml`,
`research/autoresearch/paper-toolcall-implementation-e0.md`.

- [ ] Extend the existing original-paper workflow with explicit A7
  counterbalanced positive/negative tests, without a second CI pipeline.
- [ ] Keep canonical A7 checkbox open, clearly separating E0 order
  rehearsal from externally reviewed EN/KO/JA model E2.
- [ ] Publish one Draft #1755 continuation by expected-SHA fast-forward;
  check the exact commit's workflow status and leave #1560/#1477 open and
  #1356 release on HARD HOLD.
