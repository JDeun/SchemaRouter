# A5 Host-Reviewed Runtime ToolCall Binding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Carry source-approved original-paper A5 direct scalar arguments into the actual existing fixed-K5 agent ToolCall, without new executor or implicit model authority.

**Architecture:** Reuse the existing opt-in fixed-K5 episode, add a host-owned dispatch-time binding function accepted only in scoped E0 mode, then construct it exclusively for a revalidated one-route P2 direct plan. Preserve all frozen historical evaluations and track host-assist separately.

**Tech Stack:** Python 3.12, SchemaRouter original typed direct compiler, existing generated-agent fixture runner, pytest-asyncio, Ruff, Pyright.

**Spec:** `research/autoresearch/paper-a5-runtime-host-arguments-e0-design.md`

## Global Constraints

- No new executor, no production default change, no tool execution without an agent-selected call.
- Original P2 plan and current registered source/schema/policy/role remain authority; no model hint-derived grant.
- Only explicitly approved root with all required scalar inputs; never graph dependency consumers or multiple direct alternatives.
- Synthetic E0 evidence only. #1346/#1477 external; #1356 HARD HOLD; keep Draft PR stack.

## Review Focus

1. Model call chooses correct tool but sends `{}` or a different ID: actual executor sees only host-approved value; test in Task 2.
2. Model calls an unoffered route or emits parallel calls: neither receives unauthorized host values; test in Task 1 and Task 2.
3. Host/policy/schema/fingerprint mutates during the agent turn: abort before executor; test in Task 2.
4. Frozen historical/non-scoped condition tries to request the new hook: reject before agent call; test in Task 1.
5. Trace and legacy no-host behavior: count only host-assisted dispatch, never expose raw approved value or alter original frozen outcomes; test in Tasks 1–2.

---

### Task 1: Original fixed-K5 runner optional dispatch boundary

**Files:**
- Modify: `scripts/agent_utility_generated_common.py`
- Modify: `scripts/research_authorized_agent_tool_surface.py`
- Test: `tests/test_research_paper_a5_runtime_binding_e0.py`

**Interfaces:**
- Produces: `run_generated_episode(..., experimental_scoped_call_binding: Callable[[str, dict[str, Any]], tuple[dict[str, Any], bool]] | None = None)`.
- Consumes: only `EVAL-FIXED5-OPTIN` original selector and `AuthorizedAgentToolSurface`.

- [x] RED: reject callback in historical/unscoped modes, unchanged original runtime when absent; callback invoked only for the actual first offered agent call, no speculative call.
- [x] GREEN: validate exact gated callback input/output and detached unmodified model argument snapshot before `FrozenCorpusExecutor.execute`; count host-bound calls in opt-in episode/public trace without raw input.
- [x] Verify focused tests and original frozen callback regression (261 passing cases); commit with Task 2.

### Task 2: A5 source-pinned host direct root binding

**Files:**
- Modify: `scripts/research_paper_fixed5_episode_e0.py`
- Modify: `scripts/research_paper_scoped_agent_episode_e0.py`
- Test: `tests/test_research_paper_a5_runtime_binding_e0.py`

**Interfaces:**
- Consumes: Task 1 `experimental_scoped_call_binding`.
- Produces: opt-in `PaperTypedToolPlan` direct root → host-owned exact arguments at the original executor call, with per-turn `_check_current_call_scopes` and index/source proof.

- [x] RED: real scoped model + existing frozen agent returns wrong/missing ID, fixture expects reviewed root; only host-approved ID advances task, no model compliance needed.
- [x] RED: no reviewer, explicit host input, denied review (including empty `{}`), alternate route, more than one call, source/principal mutation, and no-tool action exercise fail-closed boundaries.
- [x] GREEN: construct proof-rechecking dispatch closure from the originally compiled single direct `ready` root, and pass it to Task 1; avoid sending host value in model definitions or agent prompt. Recheck all pins after host availability probe.
- [x] Verify A5, A9, P2 and native G5 related suites (777 passed), Ruff/Pyright; update canonical handoff; commit.

### Task 3: Exact-head evidence and stacked Draft

**Files:**
- Modify: `research/autoresearch/paper-toolcall-implementation-e0.md`
- Verify `tests/test_research_paper_a5_runtime_binding_e0.py`

- [x] Independent read-only code review; RED→GREEN empty-host reviewer bypass and late availability declaration mutation findings.
- [ ] Publish tested-identical remote Git tree in a new Draft stacked on #1758, update issue #1560 and exact remote CI status.
- [ ] Do not claim whole-repo or independent E2 success from the limited local test set.
