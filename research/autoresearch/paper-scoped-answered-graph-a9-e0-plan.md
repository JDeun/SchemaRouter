# A9 E0 Bounded Observed Answer Presentation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: use the selected native
> `superpowers:executing-plans` procedure and test-driven-development, with
> live RED→GREEN evidence and a verified final local/remote check.

**Goal:** Opt-in source-scoped named graph → actual tool observation → a single
tool-free answer-generation call through the existing agent interface.

**Architecture:** Compose `run_paper_scoped_named_graph_a9_e0` without
altering its source proof, original tool executor or recorded results. Expose
only validated final projected data to the existing agent API. Detailed spec:
`paper-scoped-answered-graph-a9-e0-design.md`.

**Tech stack:** Python 3.12, pytest-asyncio, Ruff, Pyright, existing GitHub
Actions protected Python 3.12 checks.

## Global constraints

- No default router integration, new invoker, more than 1 agent call, agent
  tool definitions, retry, or model-derived input.
- Last-step data only, UTF-8 bounds, JSON response validation, fail closed
  on in-flight source drift, no independent E2/verified answer claim.
- Keep issue #1560 and Draft #1755 tracked without merging, release #1356 HOLD.

## Review focus

- A malicious final observation containing prompt-like instructions must stay
  data-only; finalizer receives `tools=[]` and no source argument authority.
- Empty/denied/missing-host graph paths must perform zero final generations.
- Original output projection and actual executor field-contract mismatch must
  block the finalizer without exporting raw values.
- Host changing source permissions within `agent.generate` must reject the
  answer rather than publish a revoked receipt.
- Oversized/nonfinite payloads, malformed agent JSON or tool-call markup must
  refuse even when the upstream graph executed successfully.

## Task 1 — RED→GREEN end-to-end finalizer boundary

**Files:** `tests/test_research_paper_scoped_answered_graph_a9_e0.py` (new),
`scripts/research_paper_scoped_answered_graph_a9_e0.py` (new).

**Interfaces:** Consume
`run_paper_scoped_named_graph_a9_e0(model, *, view, catalog,
intent_registry, index, model_visible_intent_ids,
model_visible_concept_ids, host_source_arguments=None)` and existing
`GeneratedEpisodeAgent.generate(messages, tools)`. Produce
`run_paper_scoped_answered_graph_a9_e0(model, agent, *, same arguments) ->
tuple[Decision, PaperScopedAnsweredGraph | None]`.

- [x] Write integration tests for 1-/2-hop graph and one tool-free finalizer.
- [x] Run tests **RED** on missing entry point: 18 expected failures.
- [x] Implement only the bounded opt-in finalizer and immutable receipt.
- [x] Run focused GREEN: 18 passed; repo Ruff and new-module Pyright green.
- [x] Run expanded original-paper regressions: **258 passed** across 16
  related A9/G5/typed/agent/ABI/OPTIMADE regression files.
- [x] Validate adversarial input/output/permission cases and fix bugs via
  failing tests, not speculative patches; **18 RED→GREEN** scenarios.

## Task 2 — Protected qualification and cross-session handoff

**Files:** `.github/workflows/original-paper-toolcall-plan-e0.yml`,
`research/autoresearch/paper-toolcall-implementation-e0.md`, this plan/design.

- [x] Add dedicated A9 answer-presentation tests to original-paper CI paths
  and step; run Ruff and changed source Pyright (**0 errors/warnings**).
- [x] Verify expanded pytest (**258 passed**), Ruff, whitespace and change set.
- [ ] Publish all byte-verified changed files onto same Draft #1755 head
  with non-force expected-SHA lease; no merge, release or default promotion.
- [ ] Verify all returned workflows for the exact newly published head, and
  record exact evidence and remaining A9 / E2 limitations in canonical
  handoff and GitHub issue/PR.

## Progress ledger

- 2026-10-26: Design selected under previously granted user direction to
  implement without more approval prompts. Source-captured E0 scope only.
