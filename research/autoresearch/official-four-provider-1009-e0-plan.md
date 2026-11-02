# B1 Genuine Four-Provider 1,009-Operation E0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prove one actually registered, source-byte-pinned four-publisher catalog with 1,009 native operations and canonical source-owned journal parity.

**Architecture:** Use the existing original OpenAI operation source, original GitHub GET bundle, and original Ollama/Pirate Weather source compilers. Build a single four-tool `SchemaRouter` with default-deny; prove original inventory vs full native posting/graph rebuild through two genuine whole-provider removal/restore cycles. No new adapter or executor.

**Tech Stack:** Python 3.12, pytest, existing native schema index/graph/journal, Ruff and Pyright; offline GitHub Actions.

**Spec:** `research/autoresearch/official-four-provider-1009-e0-design.md`

## Global Constraints

- Preserve upstream Git-blob/SHA-256 pins and original license notices unchanged.
- Represent only OpenAI GET 161/POST 142/DELETE 52 plus GitHub 651 GET, Ollama 2 GET, Pirate Weather 1 GET; no source-created semantic approval.
- Preserve #1755 Draft, #1346/#1477 BLOCKED_EXTERNAL and #1356 HARD HOLD.
- Do not alter the existing native converter, execution engine or default routes.

## Review Focus

- Operation-name or tool-key collision inside a *single* provider — test unique, original operationId inventory and actual route locations.
- Wrong HTTP method or required JSON body flattened to a safe GET — test source-specific POST/DELETE structural preservation.
- Unproved licenses or auth projected as runtime execution grants — test default-deny for all four authentic tools.
- Forged incremental no-op journal accepted as current after provider removal — test failure before stale index can be used.
- Distinct prior source-catalog receipts accidentally summed as if one catalog — test 1,009 simultaneous indexed routes and original manifest at each version.

---

### Task 1: Source-faithful four-publisher bundle

**Files:**
- Create: `scripts/research_official_four_provider_catalog_e0.py`
- Create: `tests/test_research_official_four_provider_catalog_e0.py`

**Interfaces:**
- Consumes: `scripts.research_official_openai_operations_e0._source_document`, `scripts.research_official_openai_get_e0.scope_original_http_operation_source`, `scripts.research_official_github_get_e0._local_snapshot` / `compile_official_github_get_bundle_e0`, `scripts.research_official_openai_operations_e0._other_providers`, `tool_from_openapi`.
- Produces: `compile_four_original_provider_tools_e0() -> tuple[ToolSpec, ToolSpec, ToolSpec, ToolSpec]`, returning OpenAI/GitHub/Ollama/Pirate order; source IDs and metadata are real.

- [x] **Step 1: RED** Add test that the exact four authentic tools compile, with 355/651/2/1 endpoints, exactly original source names, methods and denied execution. Assert concrete original POST/DELETE paths and required request JSON/body constraints.
- [x] **Step 2: Verify RED** Run `python -m pytest -q tests/test_research_official_four_provider_catalog_e0.py::test_four_original_publishers_in_one_catalog_preserve_methods` → missing function failure.
- [x] **Step 3: GREEN** Implement the minimum original-source validated tool bundling; explicitly reject source HTTP operation drift and the 16 unsupported cases, without relaxing existing converter.
- [x] **Step 4: Verify GREEN** Re-run the same test; PASS in 47.09s.

### Task 2: Canonical mixed catalog churn and measured receipt

**Files:**
- Modify: `scripts/research_official_four_provider_catalog_e0.py`
- Modify: `tests/test_research_official_four_provider_catalog_e0.py`
- Modify: `.github/workflows/research-official-provider-openapi-e0.yml`
- Modify: `research/autoresearch/paper-toolcall-implementation-e0.md`

**Interfaces:**
- Consumes: Task 1's publisher bundle; `NativeSchemaPostingIndex`, `NativeSchemaGraphIndex`, `SchemaRouter.registry`, `unregister_if_current`.
- Produces: `audit_original_four_provider_native_churn_e0() -> dict[str, Any]` with exact route counts `[1009,358,1009,654,1009]`, four provider keys, stale lookup rejections=4, exact source-route manifest and journal/full parity, timing/RSS diagnostics and no execution/E2.

- [x] **Step 1: RED** Add actual 1,009-route manifest/journal acceptance test, two genuine publisher remove/restore tests, forged journal negative test, and diagnostic type/range tests.
- [x] **Step 2: Verify RED** Run named audit test → missing function failure.
- [x] **Step 3: GREEN** Implement the mixed source-owned journal audit and explicit process timing/peak memory reporting using existing engine; source route oracle derives from the pristine documents rather than the compiled endpoints.
- [x] **Step 4: Verify GREEN** Run the new suite; **4 passed in 365.00s**, including forged no-op journal refusal.
- [x] **Step 5: Verify related + CI wiring** Native posting/graph **133 passed**; Ruff whole repo passed; changed script Pyright 0 errors/0 warnings; workflow YAML parsed. Whole local pytest capped at 110s/~8% (exit 124), not green. Dedicated Python 3.12 offline CI extended for a single 1,009-route receipt. Existing earlier official-source tests remain independently qualified on the previous HEAD; no full-new-HEAD CI claim.
- [ ] **Step 6: Review and publish** Review diff, commit one cohesive issue-sized change; publish to existing Draft #1755 using exact Git tree and expected-parent lease, verify exact SHA / GitHub checks, keep all independent gates blocked.
