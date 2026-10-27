# B1 Reviewed Host Root Revision Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Activate and revoke reviewed native input roots without rebuilding the prepared full native source index.

**Architecture:** Reproject affected original-source graph contracts and call the single canonical incremental edge updater; let `revise_catalog` atomically publish both new owner concepts and root approvals.

**Tech Stack:** Python 3.12, pytest, Ruff, Pyright.

**Spec:** `research/autoresearch/core-host-root-revision-20261027-design.md`, issue #1793.

## Global Constraints

- No provider-specific adapter, data invocation, implicit authorization or new graph engine.
- Preserve current principal, source fingerprint, data scope and availability gates, exact K5 and release HOLD.
- Source `snapshot_id` is independent of owner-reviewed root approval and semantic catalog revisions.

## Review Focus

- Adding a host root to an **unchanged** original tool must reclassify it from dependent consumer to host-owned root.
- Removing a host root must restore the native producer→consumer dependency in subsequent P1/P2 receipts.
- A direct-only scalar host root must preserve `native_root_count` despite carrying no identifier-producing graph edge.
- Unknown/deleted/malformed/destructive host roots must fail closed before a successor handle is returned.
- Source/authorization-policy mutation during revision must not publish a replacement or expose raw plugin diagnostics.

### Task 1: Original-source graph approval delta

**Files:** `src/schemarouter/native_graph_index.py`, `tests/test_schema_field_routing_session.py`.

**Interfaces:** `NativeSchemaGraphIndex.revise_host_roots(*, approved_host_roots: frozenset[str]) -> NativeSchemaGraphIndex`, reuses `update_capability_dependency_graph`.

- [x] Step 1: Add exact producer→host-root→producer, 500/5000 parity, bogus root, malformed type and no-global-scan cases using the original native fixtures.
- [x] Step 2: Run targeted cases RED on the missing graph method.
- [x] Step 3: Validate input and pinned source, rederive only original tools affected by the root-set symmetric difference, use canonical graph updater and verify exact accepted roots.
- [x] Step 4: Run targeted cases GREEN and adjacent G5 refresh regression files.

### Task 2: Atomic public owner approval and identity

**Files:** `src/schemarouter/field_routing_session.py`, `tests/test_schema_field_routing_session.py`, `README.md`, `examples/schema_only_field_routing.py`, canonical paper handoff.

**Interfaces:** `SchemaFieldRoutingSession.revise_catalog(*, catalog: NativeConceptCatalog, approved_host_roots: frozenset[str] | None = None) -> SchemaFieldRoutingSession`; root-aware `catalog_revision_id`.

- [x] Step 1: Add RED public TDD with review-only onboarding, typed `requires_arguments`, host scalar ready, revocation, identity partition and old-handle isolation; no provider I/O.
- [x] Step 2: Run exact tests RED on missing public parameter/digest.
- [x] Step 3: Bind optional reviewed roots to the graph revision before returning new detached catalog, recheck source and policy; update digest for nonempty approved roots.
- [ ] Step 4: Run exact tests GREEN plus broad related tests, Ruff, Pyright, the example and repo-wide pytest with honest timeout/status reporting.
- [ ] Step 5: Document host-controlled opt-in and limitations, record evidence, commit and publish stacked Draft after #1792; verify exact-head Actions. No merge/release claim.
