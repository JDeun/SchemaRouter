# B1 Mixed-Source Churn E0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkboxes for tracking.

**Goal:** Prove bounded mixed-source graph/posting journal freshness and live principal/policy/health invalidation against an exhaustive original-source oracle.

**Architecture:** Reuse the previous E0 heterogeneous fixture and source oracle, with real built-in registry mutation and both existing journal refresh and complete build paths. Export aggregate E0 statistics only.

**Tech Stack:** Python 3.12, pytest, SchemaRouter canonical native index, GitHub Actions.

**Spec:** `research/autoresearch/native-heterogeneous-churn-e0-design.md`

## Global Constraints

- Never change default retrieval, agent execution, or independent-quality flags.
- Never infer independent gold or permissions from the model or from E0 fixtures.
- Only catalog sizes 500/5000, all four original native-like source types, EN/KO/JA aliases, scoped original source oracle.
- Persist CI truth per exact remote commit; leave PR Draft and release on hold.

## Review Focus

- Revoked source still returned by an old versioned index (must fail closed).
- Journal delta accidentally omits revoked license (must agree with full rebuild and oracle).
- Restored source stays stale after second delta (must agree and reappear).
- Policy/role changes under same registry version leak an old route (must disappear).
- Availability changes behind the same predicate object leak stale routes (must disappear).

### Task 1: Versioned mixed-source churn audit

**Files:**
- Create `scripts/benchmark_native_heterogeneous_churn_e0.py`
- Create `tests/test_benchmark_native_heterogeneous_churn_e0.py`
- Modify `.github/workflows/indexed-concept-direct-parity-e0.yml`
- Modify `research/autoresearch/paper-toolcall-implementation-e0.md`

**Interfaces:**
- Consumes `build_heterogeneous_fixture`, `configure_heterogeneous_scope`, `original_heterogeneous_oracle`, `ACTOR`, `CASES`, `CATALOG` from `scripts/benchmark_native_heterogeneous_parity_e0.py`, `NativeSchemaGraphIndex.refresh_from_inmemory_journal` and `.build`.
- Produces `audit_heterogeneous_churn(registered_routes: int, *, iterations: int = 1) -> dict[str, Any]` and CLI `--registered-routes 500|5000 --iterations 1..4`.

- [x] **Step 1 RED:** Test versioned revocation and restoration, old-index fail-close, delta/full identity and original-source parity, permission/role/health invalidation, *common-mode* independent expected denied/hidden fixture conditions, all four sources and three languages, bounded arguments and explicit E0-only receipt.
- [x] **Step 2 RED:** Run `.venv/bin/python -m pytest -q tests/test_benchmark_native_heterogeneous_churn_e0.py`; confirmed missing module failure before code, then two new common-mode tests and one route-location test RED before fixes.
- [x] **Step 3 GREEN:** Implement same-source journal refresh and strict comparisons with original exhaustive oracle under both policies and health changes. Reject all mismatches and failures with generic exceptions; summary exports only aggregate counts and resource metrics.
- [x] **Step 4 GREEN:** Focused `pytest`: **16 passed in 162.05s** including 5000 sources after final guards.
- [x] **Step 5 REGRESSION:** Existing source/graph/index/vertical-slice tests **185 passed in 17.78s**; Ruff repository green, changed-module Pyright **0 errors**, workflow YAML and diff checked. Full local `pytest` hit 95s cap at ~8%, **not green**.
- [ ] **Step 6 CI:** Add 500/5000 existing workflow matrix execution; validate YAML and dry-run JSON, record E0 limits in canonical handoff, publish onto exact Draft #1755 remote head and verify the new dedicated CI workflow.
