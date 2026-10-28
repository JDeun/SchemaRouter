# Public Anonymous API/MCP/OPTIMADE E1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Execute and validate source-specific real, anonymous, read-only tasks against an actual mixed REST/OPTIMADE/remote-MCP SchemaRouter catalog.

**Architecture:** Register the already supported authentic Crossref, COD OPTIMADE and DeepWiki Streamable HTTP sources in one research-only router, execute fixed safe source-declared endpoints through the existing bound invokers, cross-check the Crossref DOI separately with Europe PMC, and report only bounded evidence. An offline test suite mirrors external shapes; the actual live mode must use network and cannot be faked by the offline suite.

**Tech Stack:** Python 3.12, SchemaRouter native adapters/executor, optional `mcp>=2,<3`, `httpx`, pytest/Ruff/Pyright.

**Spec:** `research/autoresearch/public-anonymous-api-mcp-optimade-e1-design.md`

## Global constraints

- No authenticated APIs, API keys, arbitrary user/model URL or write verbs.
- Fixed bounded task inputs, original source observation; no fake live receipts.
- Live mode opt-in and separate from default CI. All source results untrusted.
- Preserve independent E2 gates and release HARD HOLD.

## Review focus

- A public MCP tool with ambiguous/missing read-only hint must not be silently permitted to mutate server state.
- Crossref DOI body inconsistent with the requested DOI must fail before Europe PMC lookup.
- Europe PMC 200 with zero matched DOI entries is a factual failed task, not a successful HTTP benchmark.
- COD structure result with incompatible element cardinality must fail despite HTTP 200.
- Protocol/HTTP failures must not be rewritten as synthetic fixture successes.

---

### Task 1: Pinned public source-specific result validators and offline RED→GREEN

**Files:**
- Create: `scripts/research_public_heterogeneous_live_e1.py`
- Create: `tests/test_research_public_heterogeneous_live_e1.py`

**Interfaces:** Fixed `DOI`, `REPO`, OPTIMADE filter and endpoints; source-shape validators `validate_crossref_work`, `validate_europe_pmc_doi`, `validate_optimade_structure`, `validate_deepwiki_mcp_result`.

- [x] Add failing literal original-shaped positive/negative tests for DOI mismatch, empty Europe PMC list, wrong OPTIMADE cardinality, malformed/oversized MCP response and unknown endpoint.
- [x] Run targeted tests and confirm RED for missing code.
- [x] Implement bounded independent response validators, without accepting synthesized success values.
- [x] Rerun tests and confirm GREEN.

### Task 2: One actual mixed-source router and opt-in live execution

**Files:**
- Modify: same script and tests.
- Update: `research/autoresearch/paper-toolcall-implementation-e0.md`

**Interfaces:** `async run_live_anonymous_source_matrix(...) -> dict[str, Any]`; `SchemaRouter.add_provider('crossref')`, `SchemaRouter.add_url(...,kind='optimade')`, `SchemaRouter.add_url(...,kind='mcp')`, existing `ExecutionPlan`/`ToolCall`/bound invokers and Europe PMC httpx client.

- [x] Add offline source-contract/route allowlist/HTTP rejection tests and real one-registry source-task runner; unknown URLs are never accepted as inputs.
- [x] Confirm RED and implement source-native per-protocol discovery/invocation through current runtime (no second executor).
- [x] Confirm GREEN and run related native adapter tests and Ruff (114 related tests passed); isolated Pyright 0 errors/0 warnings. Local full suite hit the 110-second cap (~8–9%, exit 124), not green.
- [x] Run **opt-in real public networks**, record exact per-source status and test failures without renaming unavailable services as passed. Three tasks PASS on four separate network runs after one fail-closed missing-projection discovery; last run 4.94 seconds with hardened MCP transport stream caps and compression rejection.
- [x] Address independent read-only review: content-shaped MCP acceptance (not generic error text), prebuffer streaming caps for Europe PMC and public MCP, compression-bomb fail-closed, sanitized CLI/CI failure logging. Add source-shaped negative tests (15 total).
- [x] Commit code, tests, design/plan and canonical handoff as one issue-sized Draft PR update; verify exact remote Git tree and new-head CI without merging (publication/CI state recorded in the PR conversation).
