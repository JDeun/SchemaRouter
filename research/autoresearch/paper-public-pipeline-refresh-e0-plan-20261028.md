# Public Algorithm 1 Refresh Profile Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an opt-in, source-verified cold/rebuild-vs-refresh E0 timing profile without changing the existing public routing benchmark.

**Architecture:** Reuse the current synthetic fixture and immutable public prepared session. Change one unrelated source route, time its public journal refresh and a full public reprepare, then compare snapshots and actual source-pinned plans.

**Tech Stack:** Python 3.10+, Pydantic, pytest, Ruff.

**Spec:** `research/autoresearch/paper-public-pipeline-refresh-e0-design-20261028.md`

## Global Constraints

- Fixed K=5 and 500/5,000 original route counts; no model/provider invocation.
- Existing `benchmark()` and CLI output remain schema-version-1 compatible by default.
- No production routing/default or release changes, E0 is not independent E2.

## Review Focus

- Mutation of unrelated source fields must never change expected G5 target/path.
- Cached old session must reject source drift even if only a noise route changes.
- Cold rebuild and journal refresh must agree on their posting snapshot, full native graph, counters and source-contract sidecar, not merely count.
- Every refresh must follow a new registry revision rather than reusing a stale journal cursor.
- `measure_refresh` must be exactly boolean and never enable network or execution.

---

### Task 1: Optional source-verified refresh measurements

**Files:**
- Modify: `scripts/benchmark_paper_public_pipeline_e0.py`
- Modify: `tests/test_benchmark_paper_public_pipeline_e0.py`

**Interfaces:**
- Consumes: `SchemaFieldRoutingSession.refresh()`, `SchemaRouter.prepare_field_routing(catalog=...)`, `PaperNativeRankPolicy(snapshot_id=..., route_domains=..., route_priorities=...)` and current `_assert_plan`.
- Produces: `benchmark(routes: int, *, hops: int = 1, repeats: int = 3, warmup: int = 1, measure_refresh: bool = False) -> dict[str, Any]`; optional `incremental_refresh` in schema version 2 and CLI `--measure-refresh`.

- [x] **Step 1: RED test:** `test_public_algorithm1_refresh_profile_matches_cold_public_snapshot` for 500/1-hop and 500/2-hop: `benchmark(..., repeats=2, warmup=0, measure_refresh=True)` reports version 2, exactly same route count, 2 source changes, source parity and stale-old-session rejection, nonnegative p50/p95/p99 CPU+wall and exact same G5 expected route IDs; zero provider/model calls.
- [x] **Step 2: Verify RED:** run `pytest -q tests/test_benchmark_paper_public_pipeline_e0.py -k refresh` and observe missing `measure_refresh` argument.
- [x] **Step 3: Implement:** `_measure_refresh(router, session, catalog, intents, expected, repeats, routes)` using source-tool replacement, `session.refresh()`, public cold rebuild, full source snapshot and graph equality, old-handle refusal and public source-plan oracle. Add optional `measure_refresh` validation, return schema version 2 only when selected, CLI opt-in.
- [x] **Step 4: Verify GREEN:** re-run focused tests (including 5,000/2-hop and invalid flag), all existing benchmark tests, Ruff, typecheck where available.
- [x] **Step 5: Commit:** `bench(paper): profile public Algorithm 1 source-journal refresh against cold rebuild`.
