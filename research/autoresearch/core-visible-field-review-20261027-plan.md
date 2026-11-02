# B1 Visible Field Review Inventory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give a host a bounded, safe, principal-scoped inventory of registered native field semantics to review before constructing the explicit concept catalog.

**Architecture:** Add immutable public receipt classes and `SchemaFieldRoutingSession.inspect_visible_fields` on the existing version-pinned posting index. Allow an initial review-only `prepare_field_routing()` with no catalog, then authorize routing via `revise_catalog()` on the same index. Reuse current original router policy/scope/fingerprint/availability checks, never the unscoped raw posting manifest as output. No data executor, inferred semantics, duplicate registry or default routing changes.

**Tech Stack:** Python 3.12, typed dataclasses, pytest, Ruff, Pyright.

**Spec:** `research/autoresearch/core-visible-field-review-20261027-design.md`; parent #1560.

## Global Constraints

- Preserve registered-source proof, live scoped visibility, no execution authority and fixed K5 routing.
- Preview is **not** a `NativeConceptCatalog` authorizer or a globally permission-free metadata API.
- No extra provider adapters, API calls, auto semantic inference, schema full-scan at query time, or default ranker promotion.

## Review Focus

- A restricted output field must not appear in the page, nor in route metadata/response-schema annotations.
- Authorization and availability changes during scanning must invalidate a page, never return an earlier now-revoked entry.
- Cursor must be bounded and cannot enumerate *hidden* route names via total counts.
- A source schema mutation after `prepare` must cause a stale-source refusal rather than exposing stale index fields.
- The same route's field contract must remain typed/safe after original scope projection (only scalar indexed IDs).

### Task 1: Public source-review page over the existing native index

**Files:** `src/schemarouter/field_routing_session.py`, `src/schemarouter/runtime.py`, `src/schemarouter/__init__.py`, `tests/test_schema_field_routing_session.py`, `README.md`, `examples/schema_only_field_routing.py`, canonical resumption note.

**Interfaces:** `session.inspect_visible_fields(principal=..., after_route=..., limit=...) -> SchemaFieldReviewPage` with `SchemaFieldReviewRoute` / `SchemaFieldReviewField`. `router.prepare_field_routing()` remains review-only until `session.revise_catalog(catalog=...)`; all concept-based routing APIs fail closed beforehand. Reuse `_indexable_semantic_field`, `route_locations`, source fingerprints, `_data_scope_endpoint_view` and authorization/policy witnesses; no new adapter or search backend.

- [x] Step 1: Write 500-route RED tests for paginated authorized scalar metadata, hidden-field/non-authorized omissions and scan/provider-I/O prohibitions.
- [x] Step 2: Confirm missing public method RED; add stale/invalid/availability and in-flight policy/source churn negative tests. Review-only bootstrap also began with two confirmed RED tests.
- [x] Step 3: Implement verified schema-only reviewed-field page; export stable public receipt types; wire no-catalog review → owner approval without graph rescan, while rejecting all premature plan/model calls.
- [x] Step 4: Verified 329 adjacent field/graph/typed/public API/Explorer tests (including 500/5,000 route cases, callback mutation, sensitive diagnostics and opaque cursor churn), clean Ruff, 0-error focused source Pyright, runnable example and `git diff --check`. Exact-head GitHub CI remains pending.
- [ ] Step 5: Document reviewer-only boundary, commit and publish stacked Draft linked to one GitHub issue.
