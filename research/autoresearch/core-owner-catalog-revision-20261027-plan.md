# B1 Owner Catalog Revision Wiring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a host replace only its reviewed schema-field meaning catalog without rebuilding a still-current native posting/G5 graph.

**Architecture:** Add a strictly opt-in immutable `SchemaFieldRoutingSession.revise_catalog` operation. Reuse the original pinned index after source/policy checks and detach a newly validated owner catalog. Expose an opaque owner semantic revision digest separately from source `snapshot_id`.

**Tech Stack:** Python 3.12, Pydantic, pytest, Ruff, Pyright.

**Spec:** `research/autoresearch/core-owner-catalog-revision-20261027-design.md`; parent #1560.

## Global Constraints

- Preserve source-owned field and typed dependency proofs, per-principal authorization, strict K5 and no provider I/O.
- Do not silently mutate the old session or redefine `snapshot_id`.
- This is explicit host-handle replacement, not global semantic catalog revocation and not E2/default release.

## Review Focus

- Mutating original catalog after creation cannot mutate a newer prepared session.
- Native schema revision invalidates catalog-only replacement; host must use `.refresh()` or full prepare.
- Same-object mutable authorization policy drift during copy must refuse publication.
- Approved host roots and canonical graph cannot be dropped or rederived silently.
- Cache identity must differ on changed reviewed semantics even when registry snapshot is identical.

### Task 1: Public catalog-only session revision

**Files:** `src/schemarouter/field_routing_session.py`, `tests/test_schema_field_routing_session.py`, `README.md`, canonical resumption note.

**Interfaces:**
- Consumes existing `NativeConceptCatalog.model_validate`, `NativeSchemaPostingIndex._assert_source`, `_policy_contents_digest` and immutable `NativeSchemaGraphIndex`.
- Produces `SchemaFieldRoutingSession.revise_catalog(*, catalog: NativeConceptCatalog) -> SchemaFieldRoutingSession` and `catalog_revision_id: str`.

- [x] Step 1: Write failing 500-route EN/KO/JA owner catalog replacement/parity and no-rebuild/provider-I/O regressions, snapshot/revision cache identity and source/policy/malformed refusal tests.
- [x] Step 2: Run and inspect expected missing-method/property RED (4 missing-API tests).
- [x] Step 3: Implement only verified immutable source-index reuse and content digest; no new graph/retriever/model.
- [x] Step 4: Run focused+native routing suites (296 passed after review fixes), Ruff, source Pyright (0 errors), provider-neutral runnable example, and `git diff --check`; protected exact-head CI remains pending until checked.
- [ ] Step 5: Update README and canonical handoff, publish stacked Draft, keep #1560/B1 and E2 open.
