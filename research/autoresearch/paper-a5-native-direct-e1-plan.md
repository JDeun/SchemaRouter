# A5 Native Direct E1 Execution Bridge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Execute one original P2 source-typed A5 direct call through the real registered SchemaRouter invoker after the actual agent selects its offered route.

**Architecture:** Compose existing `analyze_and_plan_paper_scoped_e0`, `paper_plan_fixed5_menu`, `build_paper_a5_root_binding_e0`, canonical agent tool-call parser, and `SchemaRouter.execute` in a new opt-in async E1 bridge; do not mutate the synthetic runner.

**Tech Stack:** Python 3.12, SchemaRouter native executor, pytest-asyncio, Ruff, Pyright.

**Spec:** `research/autoresearch/paper-a5-native-direct-e1-design.md`

## Global Constraints

- Never turn an untrusted parameter hint into a provider argument, widen a captured principal menu, invent provider credentials, or run non-read-only calls.
- No new executor, model-facing host inputs, frozen benchmark alteration, default rollout or E2 score.
- Only one host-proven direct route and one native execution attempt. No graph flattening or fallback outside scope.
- Keep #1346/#1477 external and #1356 HARD HOLD; stacked draft only.

## Review Focus

1. Model selects another (possibly not offered) route → no native execution.
2. Malformed or parallel tool calls → zero provider calls and no execution receipt.
3. Missing/rejected/empty host argument review → no agent turn or native call.
4. Valid P2 input but agent fabricates a different ID/surplus property → native invoker sees only the host-approved ID.
5. Source authorization, graph or host declarations mutate while agent generates or native execution awaits → fail closed, never return a success receipt.

---

### Task 1: Native original direct invocation adapter

**Files:**
- Create: `scripts/research_paper_scoped_native_direct_e1.py`
- Create: `scripts/research_paper_native_open_meteo_direct_e1.py`
- Create: `tests/test_research_paper_scoped_native_direct_e1.py`
- Create: `tests/test_research_paper_native_open_meteo_direct_e1.py`

**Interfaces:**
- Consumes: scoped A5 model, verified one-route P2 plan, source-root E0 binder and original agent call parser.
- Produces: `async run_paper_scoped_native_direct_e1(...) -> tuple[Decision, PaperScopedNativeDirectE1 | None]` with host-only `ToolResult`.

- [x] RED: registered original tool executes after approved A5 model+agent route, and actual arguments/field projections match the original direct P2 call, not the model's forged values.
- [x] RED: unknown/extra/malformed/parallel agent calls, unreviewed/missing source arguments and genuine zero-argument direct routes are handled fail-closed.
- [x] GREEN: implement bounded async adapter and independent native execution with `RunConfig` single-attempt, principal-pinned read-only scope.
- [x] RED→GREEN: changed offered tool definitions and deeply nested JSON reject before native I/O; revoked authorization during awaited provider call prevents success receipt.
- [x] RED→GREEN: same-fingerprint native invoker rebinds during agent generation or awaited before-call hook are rejected at the actual executor lookup (independent review finding).
- [x] RED→GREEN: distinct executor with matching binding generation and ambiguous duplicate-key model ToolCall are rejected (independent review findings).
- [x] RED→GREEN: actual original Open-Meteo HTTP invoker via mocked transport and one anonymous public live source request (noncommercial research only); no model-choice/E2 inference.
- [x] Verify core P2/A5/G5 (810 passed after reviewer fixes), historical frozen runner (261 passed), repo Ruff, changed-module Pyright (using explicit third-party dependency path), five selected executor suites (except four sandbox-blocked offload tests), and one final native Open-Meteo live request.
- [x] Commit the final reviewed tree.

### Task 2: Handoff, independent review and stacked Draft

**Files:**
- Modify: `research/autoresearch/paper-toolcall-implementation-e0.md`

- [x] Describe tested native E1 integration without certifying public-provider E2 or claiming model accuracy.
- [x] Independent read-only code review; same-fingerprint native rebind, executor-identity collision and duplicate-key findings RED→GREEN. No remaining important defects reported.
- [ ] Exact-head verification after publication.
- [ ] Publish tested-identical tree in Draft stacked above #1759, comment #1560, report actual CI status.
