# DeepWiki MCP Original A5 Wiring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish one source-proved live MCP → original P2 → A5 → native execution feature without fabricating an MCP identifier.

**Architecture:** G5 accepts reviewed scalar-only source routes as direct-only empty-producer nodes; the existing field posting index proves typed direct matches. Source-specific registrar pins native discovery, reviews only the existing DeepWiki endpoint, and binds the existing MCP invoker. E1 runner exercises original gated planning and host-selected inputs.

**Tech Stack:** Python 3.11+, Pydantic, MCP optional adapter, pytest/asyncio, Ruff, Pyright.

**Spec:** `research/autoresearch/paper-deepwiki-mcp-native-a5-e1-design.md`

**Documentation boundary:** This is internal engineering research, intentionally
outside `docs/**/*.md` and its independently curated bilingual review corpus.

## Global Constraints

- No invented source output fields or identifier-based graph join edges.
- Host selects and supplies all execution arguments; model hints are untrusted.
- No unreviewed `readOnlyHint` privilege or unverified commercial license claim.
- Native authorization, provenance, existing invoker and original P2/A5 only.
- Integration tests offline; public live runner explicitly manual-only.

## Review Focus

- A scalar-only reviewed root cannot produce a synthetic G5 join edge.
- A remote annotation cannot substitute for host review.
- A stale full-discovery fingerprint fails before registration and execution.
- An MCP outline for another repo or truncated content fails after native call.
- An unapproved principal or forged agent argument cannot drive MCP calls.

---

### Task 1: Direct-only nonidentifier G5 host roots

**Files:** Modify `src/schemarouter/native_graph_index.py`; test `tests/test_native_graph_host_root.py`.

**Interfaces:** Existing `NativeSchemaGraphIndex.build(field_index, approved_host_roots=...)`; preserve `CapabilityDependencyGraph` node and zero edges for scalar-only root.

- [x] Write tests for scalar-only reviewed host direct root, absent approval refusal, and no graph identifier edge.
- [x] Run focused tests; observe expected host-root rejection (RED).
- [x] Accept typed scalar-only host root as an empty-producer capability; keep identifier graph edge rules intact.
- [x] Run tests; observe GREEN; commit (`f67842b9`).

### Task 2: Native DeepWiki source approval and registration

**Files:** Create `src/schemarouter/paper_deepwiki_registration.py`; modify `src/schemarouter/__init__.py`; test `tests/test_paper_deepwiki_native_a5_e1.py`.

**Interfaces:** `probe_deepwiki_paper_source(*, client_factory, network_policy) -> DeepWikiPaperSourceProbe`; `register_reviewed_deepwiki_paper_source(router, *, expected_source_fingerprint, expected_url, license, reviewed_by, client_factory) -> ToolSpec` (async); source-specific verified invoker.

- [x] Write source-shaped MCP fake and red tests for two-phase probe, schema/URL drift, refusal, and reviewed native `SchemaRouter.execute` projection.
- [x] Run tests; observe RED for missing registrar.
- [x] Implement bounded pinned source discovery, host semantic review, native runtime binding, and source identity check.
- [x] Run tests; observe GREEN; commit in integrated feature change.

### Task 3: Original Understand/P2/A5 native research runner and CI

**Files:** Create `scripts/research_paper_deepwiki_native_e1.py`, `.github/workflows/research-paper-deepwiki-native-a5-e1.yml`; test `tests/test_paper_deepwiki_native_a5_e1.py`; update canonical handoff `research/autoresearch/paper-toolcall-implementation-e0.md`.

**Interfaces:** `run_deepwiki_paper_a5(*, expected_source_fingerprint, host_repo, client_factory, network_policy) -> DeepWikiPaperA5E1`.

- [x] Write red end-to-end tests: successful source-shaped host-pinned outline, forged model arguments refused, invalid output and host repo early rejection.
- [x] Run tests; observe RED for missing runner.
- [x] Implement research-only CLI probe/run with original `run_paper_scoped_native_direct_e1`, read-only original route and manual-only workflow.
- [x] Run related tests (612 passed after independent-review fixes), Ruff, Pyright; update canonical handoff and commit in integrated feature change.

### Task 4: Review and draft integration

**Files:** Existing changes and issue/PR metadata.

- [x] Request one fresh independent read-only review; resolve Important findings with RED→GREEN (real source annotations and schema constraint guard).
- [x] Verify related original-paper suite (612 tests), real localhost MCP (2 tests), repository Ruff and targeted Pyright.
- [ ] Publish stacked Draft PR on prior Crossref feature branch and record exact remote tree/checks without merging.
