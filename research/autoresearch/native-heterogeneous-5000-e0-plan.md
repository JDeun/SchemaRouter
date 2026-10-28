# B1 Heterogeneous 500/5000 Native Catalog Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: use superpowers:executing-plans
> and superpowers:test-driven-development with observed RED→GREEN evidence.

**Goal:** Prove exact source-oracle parity on synthetic mixed-source 500/5000
native catalogs with principal/scope/churn safety, and record bounded CPU.

**Architecture:** Compose the already registered ToolSpec → existing native
posting/graph index → existing concept retriever; scan original registered
ToolSpecs separately only for offline comparison. No duplicate router.

**Tech Stack:** Python 3.12, pytest, Ruff, Pyright.

**Spec:** `native-heterogeneous-5000-e0-design.md`.

## Global Constraints

- Research E0 only; #1560 open, Draft #1755 unmerged, #1356 release HOLD.
- Preserve original principal, data-scope, availability, source and typed
  field boundaries before K5.
- 5000-route thorough sweep is an opt-in manual CLI; do not add another
  expensive unconditional CI matrix job.

## Review Focus

- Near-matching hidden or wrong-license source must not be counted as valid.
- A stale source snapshot must refuse instead of emitting obsolete results.
- Mixed Korean/Japanese aliases must not accidentally resolve another type.
- Denied/unavailable tools cannot escape because they appear in postings.
- Avoid indexing all 5000 records inside each measured lookup.

## Task 1 — Source-heterogeneous fixture and independent oracle

**Files:** `scripts/benchmark_native_heterogeneous_parity_e0.py` (new),
`tests/test_benchmark_native_heterogeneous_parity_e0.py` (new).

**Interfaces:** `build_heterogeneous_fixture(registered_routes: int) ->
SchemaRouter`; `original_heterogeneous_oracle(router, concept_id: str,
principal: PrincipalContext) -> tuple[str, ...]`; `audit_heterogeneous(...)`.

- [x] RED: exact catalog cardinality and four source-disjoint EN/KO/JA
  positive fixtures; independently expected original route names.
- [x] RED: hidden-field, policy-denied, unavailable, bad license/schema
  decoys cannot become valid route witnesses.
- [x] Reviewer-found RED: identical semantic ID, JSON type, and license under
  a **wrong native source type** must be excluded in both 500/5000 catalogs.
  Corrected fixture includes four source-collision decoys within the same
  exact route counts; 2 new tests observed RED before GREEN.
- [x] GREEN: minimal single fixture/oracle harness and existing-index queries.
- [x] Verify test suite and Ruff/Pyright: **13 focused passed**, full-repo
  Ruff and new script Pyright **0 errors, 0 warnings**.

## Task 2 — Mutation refusal and bounded CPU audit

**Files:** same script and tests; this plan and canonical handoff.

- [x] RED: replacement of a registered source tool refuses stale index,
  fresh index returns correct result; no absent source inference.
- [x] RED: CLI/audit output explicitly limits gold and quality claims,
  rejects wrong route cardinality or too-small sample counts.
- [x] GREEN: bounded audit with unchanged source snapshot, per-scenario
  original-oracle equality and p50/p95/p99 process CPU/wall evidence.
- [x] Run 500 and 5000 manually: **96/96 exact oracle matches each**, four
  source types, EN/KO/JA, four policy/scope/health scenarios. Linux Python
  3.12.14 indexed-query wall p50/p95/p99: 500 routes **1.310/2.031/4.751ms**;
  5000 routes **1.313/2.315/2.475ms**. Developer-synthetic, not E2/SLO.
- [x] Run related index/graph/original-paper tests: **177 passed**, Ruff
  on new source/test and new-script Pyright green; broader checks separately.
- [x] Wire the opt-in mixed-source audit into the existing indexed-concept
  CI matrix without adding another unconditional desktop/package matrix.
- [x] Initial six-file audit published with non-force expected-SHA to Draft
  #1755 at `8b079dab`; latest code-review follow-up must be republished and
  requalified on its **own** commit SHA.
- [ ] Publish the source-collision review fix using non-force expected-SHA;
  verify all required protected CI against that newest exact head.

## Progress ledger

- 2026-10-26: Created plan against existing #1560 B1 criteria and
  currently verified Draft #1755 head `bfedf637`.
- 2026-10-26: Observed failing import before implementation, then 13 GREEN
  cases. 500 and 5000 CLI audit each 96/96; 177 related regressions.
  Workflow YAML parses locally. This remains E0; actual provider-reviewed
  5000 mixed adapters, source-gold and paired E2 remain open.
- 2026-10-26: Independent review found no runtime routing bug but one Important
  audit coverage gap: source-type collisions were absent. Added same-semantic,
  same-type, same-license wrong-source fixtures after observing 2 expected
  RED tests; 15 focused GREEN, 197 related GREEN, full Ruff and script Pyright
  GREEN. Both updated 500/5000 CLI audits returned 96/96 exact parity. Local
  wall p50/p95/p99 were 1.449/2.019/2.408 ms for 500 and
  1.448/2.210/2.529 ms for 5000 (E0 only, not a throughput/SLO claim).
  Reviewer also suggested optional broader privacy-serialization and anonymous
  indexed-boundary test coverage; actual sampled outputs showed no leak.
