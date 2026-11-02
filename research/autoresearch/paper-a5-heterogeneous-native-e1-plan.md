# Original A5 Heterogeneous Native E1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run several source-approved original-paper A5 direct agent choices on one registered, heterogeneous native OpenAPI/MCP/OPTIMADE catalog.

**Architecture:** Strict host matrix preflight; sequential composition of the reviewed A5 E1 direct bridge per protocol; no new invoker, no model-visible provider results.

**Tech Stack:** Python 3.12, SchemaRouter native registry/executor, real native adapter compilers, pytest-asyncio, Ruff, Pyright.

**Spec:** `research/autoresearch/paper-a5-heterogeneous-native-e1-design.md`

## Global Constraints

- Do not change frozen E0 benchmarks, default product routes, model inference, licensing, auth or executor semantics.
- Principal-visible, source-attested single-route readiness is mandatory for each call, with host-owned parameters.
- Validate complete matrix before any tool I/O; never claim atomic rollback after a failed later read.
- Structured Crossref object/OPTIMADE array source fields are **not** a scalar P2 proof; refuse instead of projecting/fabricating.
- Keep #1346/#1477 external and #1356 release HOLD; publish stacked Draft only.

## Review Focus

1. Invalid scenario after a valid one must not allow any earlier provider call during preflight.
2. Reused tool endpoint under two scenario IDs must not duplicate unintended side effects.
3. Agent routes to unoffered or different source (or forges values) must not escape host scope.
4. A source policy or native invoker rebind during execution must fail closed.
5. A partial successful read followed by a failed provider must never be counted as a successful *whole* matrix.

---

### Task 1: Multi-provider E1 A5 direct scenario bridge

**Files:**
- Create: `scripts/research_paper_heterogeneous_native_e1.py`
- Modify: `scripts/research_paper_scoped_native_direct_e1.py` (optional expected-route guard)
- Create: `tests/test_research_paper_heterogeneous_native_e1.py`

**Interfaces:**
- Consumes: `AuthorizedAgentToolSurface`, `NativeConceptCatalog`, `PaperIntentRegistry`, `NativeSchemaGraphIndex`, and a bounded tuple of trusted cases (`case_id`, `route_id`, `intent_id`, `concept_id`, `model`, `agent`, `host_arguments`).
- Produces: `async run_paper_heterogeneous_native_e1(...) -> PaperHeterogeneousNativeE1`; a host-only receipt with actual ordered `PaperScopedNativeDirectE1` results and E1-only flags.

- [x] RED: three real adapter-compiled registered OpenAPI/MCP/OPTIMADE scalar routes execute with original P2 and agent ToolCall, with host arguments enforced and typed projected results.
- [x] RED: manifest containing duplicate, unauthorized, bad later route/intent/concept/argument gives zero agent/provider calls.
- [x] GREEN: strict matrix preflight and sequential reuse of exact A5 E1 native bridge; never leak private result in public summary.
- [x] RED: refused or failing later call does not claim whole matrix success; no more provider calls after failure.
- [x] GREEN: 18 focused tests; independent review prompted RED→GREEN coverage for whole-matrix binding snapshots, availability-time rebinds, a valid but nonmanifest input-free model source, wrong-arity later generators, and truthful heterogeneity reporting. Final broad regression **855 passed**, historical agent-utility **237 passed**, repository Ruff passed, changed-module Pyright **0 errors/0 warnings**.

### Task 2: Handoff, review and publication

**Files:**
- Modify: `research/autoresearch/paper-toolcall-implementation-e0.md`

- [x] Record exact E1 scope and limitation, including scalar output and external gold gates.
- [x] Fresh independent read-only branch review: two Important findings (later binding swap and post-I/O route mismatch) and follow-up preflight rebind edge reproduced RED and fixed GREEN; callable signature and registered source-type receipt clarified.
- [ ] Verify exact tested remote tree, stacked Draft above #1760, note GitHub Actions status and issue linkage.
