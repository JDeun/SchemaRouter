# Paper host empty-menu refusal E0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use RED/GREEN TDD and checkbox tracking.

**Goal:** Make absent/denied/unproven original native tool menus terminate at the host before model/tool execution, while admitting source-verified structured Algorithm 1 direct candidates into the existing fixed5 agent loop.

**Architecture:** Add one default-off terminal guard inside the existing `run_generated_episode`, with a sanitized public trace flag. Add a source-scoped callback adapter that compiles the existing `PaperUnderstoodDirect` typed plan, without duplicating agent or executor. Keep no-fit uncalibrated and K-overflow distinct.

**Tech Stack:** Python 3.10+, existing fixed5 script evaluator, Pydantic, pytest, Ruff.

**Spec:** `research/autoresearch/paper-host-empty-menu-refusal-e0-design.md`

## Global Constraints

- E0 only, default off; protected historical #432 conditions and production routing/execution unchanged.
- Strict K=5 and currently authorized native principal/fields/availability/source fingerprints. No new LLM parser, hidden names or gold leakage.
- `REQUEST_MORE_TOOLS` is a fixture terminal meaning **not offered/verified for this principal**, not universal unsupported classification. Over-K and budget unresolved remain explicitly distinct.
- Do not merge, modify original benchmark data or claim E2; #1346/#1477 still blocked and #1356 HARD HOLD.

## Review Focus

1. Empty model menu under authorized filtering must produce zero *model* turns and zero tool *attempts* (Task 1).
2. A genuinely supported task with an empty menu must fail the original supported grader, not inflate unsupported pass rate (Task 1).
3. A source drift before terminal cannot be relabeled as missing tools or hide authorization revocation (Task 1).
4. An untrusted named ToolSpec outside current principal/field/source authorization must not appear even if the planner returns a route (Task 2).
5. K-overflow/byte-budget cannot become a semantic no-fit assertion; malformed model hints cannot grant argument values (Task 2).

---

### Task 1 — Host-owned empty-menu terminal in existing fixed5 evaluator

**Files:** `scripts/agent_utility_generated_common.py`, `scripts/research_authorized_agent_tool_surface.py`, `tests/test_research_authorized_concept_fixed5_agent_bridge.py`.

**Interfaces:** Consume `experimental_candidate_selector` and `experimental_agent_tool_surface`; produce optional `experimental_host_empty_menu_terminal: bool=False`. Public metrics add `host_empty_menu_terminal: bool` only when host opted in.

- [ ] RED: tests for unsupported empty selector exact terminal passing without model call/tool attempts; supported empty selector false refusal; nonempty normal model execution; wrong scope/type, source mutation, sanitized flag.
- [ ] Run `.venv/bin/python -m pytest -q tests/test_research_authorized_concept_fixed5_agent_bridge.py -k host_empty_menu` → expected missing keyword failure.
- [ ] GREEN: validate flag with fixed5+principal-scoped selector only; after source-pinned selection initialize host `final_text` to exact generic terminal on empty menu, skip generator loop, preserve original grader and source checks. Export optional typed boolean through existing `public_trace` whitelist.
- [ ] Run `.venv/bin/python -m pytest -q tests/test_research_authorized_concept_fixed5_agent_bridge.py tests/test_research_authorized_agent_tool_surface.py` → all pass.
- [ ] Commit Task 1 changes.

### Task 2 — Original structured paper direct-plan → existing scoped selector

**Files:** `scripts/research_authorized_concept_fixed5_agent_bridge.py`, `tests/test_research_authorized_concept_fixed5_agent_bridge.py`.

**Interfaces:** Consume `AuthorizedAgentToolSurface`, `PaperIntentRegistry`, `PaperUnderstanding`, `NativeConceptCatalog`, `NativeSchemaGraphIndex`, `compile_paper_understood_direct_plan`; produce `AuthorizedPaperUnderstoodDirectFixed5Selector` with existing `(query, visible_route_ids) -> list[str]` callback and `last_status`.

- [ ] RED: named sixth tool only if in current source view; missing/hidden/denied/wrong-license/partial tool yields no menu, K-overflow yields no menu with separate status; structured hints/intent/catalog mutation reject; confirmed route and source fingerprints are exact; no model-supplied arguments become evidence.
- [ ] Run `.venv/bin/python -m pytest -q tests/test_research_authorized_concept_fixed5_agent_bridge.py -k paper_understood` → missing adapter failure.
- [ ] GREEN: implement callback using original compiler; check immutable inputs and view, only accept status `ready`/`requires_arguments`, route set subset of visible source with pinned fingerprints, cap 5 and serialize definitions; no execution or grade access. Missing proof returns [] + original status.
- [ ] Run `.venv/bin/python -m pytest -q tests/test_research_authorized_concept_fixed5_agent_bridge.py tests/test_paper_understood_direct_plan.py tests/test_native_semantic_index.py` → all pass.
- [ ] Commit Task 2 changes.

### Task 3 — Verification, record and stacked Draft

**Files:** append run output/limitations to this plan.

- [ ] Run Ruff, Pyright, target tests and repository-wide pytest; report exact failures and timeouts.
- [ ] Inspect diff for frozen-mode behavior, gold exposure, private names, misleading no-fit assertion. Local author self-review (no subagents authorized).
- [ ] Update stacked Draft #1755 by verified Git tree and expected SHA using authenticated connector if available; do not merge. Record CI status and E0-only limit.

**Execution authority:** User preapproved native sequential changes and requested no routine reapproval, within existing branch/PR scope.

## 2026-10-25 implementation checkpoint

- Task 1 RED: five failing new tests (`unexpected keyword argument 'experimental_host_empty_menu_terminal'`). GREEN: 83 passed across the scoped selector and captured source-view suites. `1f0075a` adds a default-false empty-menu host terminal and privacy-whitelisted boolean, with frozen condition validation, no generator call/tool attempt, supported false-refusal preservation and mutation abort.
- Task 2 RED: missing original paper selector import during isolated pytest collection. GREEN: 25 passed in the new direct-plan-to-existing-agent suite plus previous selector tests. `8b80ea1` adds the exact original-plan-to-source-view callback with current fingerprints, source/license/field permissions, K5 and model-definition byte cap. All data stay inside scoped receipts; no synthetic E0 validation becomes E2 evidence.
- Seven combined P1/P2/posting/agent test modules: **210 passed in 10.54s**. Fresh `.venv/bin/ruff check .`: **all checks passed**. Changed selector file `.venv/bin/pyright scripts/research_authorized_concept_fixed5_agent_bridge.py`: **0 errors**.
- Full `.venv/bin/pyright` without an explicit environment path reports **85 errors / 8 warnings**, primarily missing optional imports (`pydantic`, `httpx`, `anyio`, `sqlalchemy`) in this local interpreter resolution plus existing unrelated modules. Targeted changed module has zero errors; do not claim repository-wide typecheck green.
- Entire repository `timeout 85s .venv/bin/python -m pytest -q` exited **124**, after approximately **12%** of the suites and no final result. This is **not** full-suite passing evidence. No frozen benchmark was modified to work around the local run.
- Author's whole-change self-review: default `experimental_host_empty_menu_terminal=False` preserves the existing generator and frozen scenarios; `True` is scoped to original principal-authorized E0 menus and emits no private original query or tool identifier to the public trace. Empty selected menus are **unverified**, not independently unfit. The direct selector never receives gold fixtures, planner execution authority, or source provider results. Test file inter-test import coupling was eliminated; its 9 tests passed both ordinary and `--import-mode=importlib` pytest runs.
- Remote Draft publication pending at this checkpoint. #1291 calibrated no-fit remains independent and open; #1346/#1477 E2 and #1356 release remain gated.
