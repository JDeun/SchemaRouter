# Prepared Session Refresh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire existing B1 source-versioned incremental semantic + G5 graph refresh into the public provider-neutral prepared session.

**Architecture:** Keep immutable session handles and original canonical graph refresh, including exact journal owner checks or fully verified explicit delta hints. Reuse current source/policy guards; no provider adapters or data execution.

**Tech Stack:** Python 3.12, Pydantic, pytest, Ruff, Pyright.

**Spec:** `research/autoresearch/core-session-refresh-20261027-design.md` and #1560.

## Global Constraints

- Strict original K=5, owner-approved contracts, per-principal current authorization.
- Previous sessions must fail closed after registry churn.
- Never call invokers or infer model argument values.

## Review Focus

- Expired/wrong source journals: refuse with no fallback.
- Explicit incomplete changed-key hints: refusal by source fingerprint oracle.
- Policy mutation during refresh: no new session publication.
- Revoked host-approved routes: refuse rather than silently altering approved set.
- Ordinary large-catalog reads and native executor calls: no full scan on journal or provider I/O.

### Task 1: End-to-end immutable prepared refresh

**Files:**
- Modify: `src/schemarouter/field_routing_session.py`
- Test: `tests/test_schema_field_routing_session.py`

**Interfaces:**
- Consumes: `NativeSchemaGraphIndex.refresh_from_inmemory_journal`, `refresh_from_sqlite_journal`, `NativeSchemaPostingIndex.refresh`, `NativeSchemaGraphIndex.refresh`.
- Produces: `SchemaFieldRoutingSession.refresh(*, changed_tool_keys: tuple[str, ...] | None = None) -> SchemaFieldRoutingSession`.

- [x] Step 1: Write integration regressions for 500-route in-memory refresh parity, stale old session, no journal on unchanged source, explicit hint verification, policy drift and no provider I/O.
- [x] Step 2: Run tests and record expected missing API (RED): 4 expected `AttributeError` failures.
- [x] Step 3: Implement minimal immutable dispatcher to existing source-checked native graph refresh APIs, without a new index or full build fallback.
- [x] Step 4: Verify new and affected routing/journal tests, Ruff and source Pyright (GREEN): 181 passed in five scoped suites; Ruff 0 issues, source Pyright 0 errors. Deliberately invalid-input test cases are outside strict static typing.
- [ ] Step 5: Update README and canonical resumption note, commit and publish stacked Draft after CI review.

## Implementation decision and qualification limit

The original native source-owned graph journal methods already enforce source
identity, bounded atomic history and source revision. The public wiring adds
an explicit policy-digest witness before/after refresh and independently
rechecks the refreshed original-source index. A session points to the newest
source only after these verifications; no implicit rebuild fallback.

Independent read-only code review found no Critical code defect, but requested
meaningful semantic churn, host-root revocation, journal overflow, custom
registry and same-object policy-mutation public tests. These were added and
verified, including a real producer delete/restore and SQLite semantic
replacement (not just an inert added endpoint).

The 181-case local subset and code checks are **E0 implementation evidence**, not
protected full CI or 5000 heterogeneous/E2 qualification. No production
default ranking, provider execution or release-gate change is authorized.
