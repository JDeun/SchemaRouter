# Original Algorithm 1 Native Rank Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Supply an explicitly reviewed, source-pinned deterministic `Rank()`
that selects five among 500/5,000 authorized native direct FieldGroup routes,
and wire it to the reusable paper session without promoting the default.

**Architecture:** A host-owned typed policy holds route-domain, web and
priority annotations. The existing semantic index performs full live source
qualification before a local bounded heap chooses Top-K5. Paper direct
plans and opt-in session entrypoints propagate an `ranked_unverified` marker.

**Tech Stack:** Python 3.12, dataclasses/Pydantic, heapq, pytest, Ruff, Pyright.

**Spec:** `research/autoresearch/paper-native-rank-policy-20261028-design.md`.

## Global Constraints

- Exact K=5; never inspect unreviewed source descriptions for rank authority.
- Do not change original ToolSpec schema fingerprints, snapshot hash or defaults.
- Recheck original RBAC, data scope, availability and source snapshot before
  and after any rank; no provider execution or model callback inside ranking.
- Preserve legacy `over_k_unranked` and the research callback's cap 32.
- E0 heuristic only; `ranked_unverified=True`, no E2/quality/release claim.

## Review Focus

- A scoped hidden output must not change a permitted route's tie-break via
  original field count: test two principals with different visible sets.
- A denied or unhealthy route with a very high owner priority is not
  eligible: test forbidden/unavailable with a tempting rank annotation.
- An owner domain tag on an unregistered route and a mismatched source
  snapshot must fail before returning a ranked candidate.
- A mutated owner policy or current source during the model callback must
  not produce a stale plan: test both mutation paths.
- A registered tool with several endpoints and explicit named override
  must never convert the override into a guessed ranked execution grant.

### Task 1: Source-pinned owner Rank contract and pure score

**Files:** create `src/schemarouter/paper_native_rank.py`; modify
`src/schemarouter/paper_understood_direct_plan.py`; tests new
`tests/test_paper_native_rank.py`.

**Interfaces:** `PaperNativeRankPolicy(snapshot_id, route_domains,
route_priorities, web_route_ids)` and deterministic local
`rank_authorized_paper_direct(...)` whose tuple offsets only index the
already qualified source receipts. Optional `PaperIntentDeclaration.domains`.

- [x] RED: write exact match/substring, web, priority, visible-field-count,
  deterministic tie, domain and invalid owner metadata test cases.
- [x] Confirm these fail for missing production contract.
- [x] GREEN: typed bounded owner declaration, safe pure rank key and bounded
  heap, with no registry/provenance mutation or extra provider calls.
- [x] Run new contract tests, Ruff and changed-source Pyright (0 errors with
  an external local configuration that explicitly includes the installed
  Python 3.12 Pydantic site-packages; the repository default misses this
  environment's external dependency location).
- [x] Commit Task 1.

### Task 2: Integrate post-auth native index selection before K

**Files:** modify `src/schemarouter/native_semantic_index.py`, tests
`tests/test_native_semantic_index.py` and `tests/test_paper_native_rank.py`.

**Interfaces:** optional `_paper_rank_policy`, `_paper_rank_aliases` and
`_paper_rank_domains` internal source-owned `lookup` arguments; explicit
result marker distinct from arbitrary `_research_ranker`.

- [x] RED: 6 / 5,000 ranked current-principal original endpoints, independent
  expected Top-K5 oracle, named override, hidden/denied/unavailable and
  mid-request policy/source revocation regressions.
- [x] Confirm RED is missing rank/index connection.
- [x] GREEN: rank ONLY qualified originals, seek source-attested route
  metadata, return original candidate receipts and reattest full cohort.
- [x] Run native posting/index and SQLite delta parity tests; Ruff/Pyright
  with the explicit external installed-package resolver.
- [ ] Commit Task 2.

### Task 3: Public Algorithm 1 opt-in routing and no-authority receipt

**Files:** `src/schemarouter/paper_understood_direct_plan.py`,
`src/schemarouter/paper_understood_graph_plan.py`,
`src/schemarouter/paper_typed_tool_plan.py`,
`src/schemarouter/field_routing_session.py`,
`src/schemarouter/paper_query_understanding.py`, `src/schemarouter/__init__.py`,
`tests/test_schema_field_routing_session.py` and new Rank session tests.

**Interfaces:** optional `rank_policy` on `compile_understood` and
`acompile_query`, immutable `PaperTypedToolPlan.ranked_unverified`.

- [x] RED: no-policy legacy refusal; policy direct plan Top-K5 marker;
  named tool no auto ranking; async callback `Understand→Rank→nonexecuting
  ToolCall`; mutation during callback fail closed; no provider calls.
- [x] Confirm RED on missing new public arguments and marker.
- [x] GREEN: forward optional policy through original compilers, preserving
  G5 dependency abstentions and all existing source reattestation.
- [x] Run related session/paper/G5 tests, Ruff, Pyright and sample code.
- [ ] Commit Task 3.

### Task 4: Benchmark, documented limitations, branch qualification

**Files:** benchmark `scripts/benchmark_paper_native_rank_b1.py`, tests,
README, example and canonical
`research/autoresearch/paper-toolcall-implementation-e0.md`.

- [x] Synthetic 500/5,000 fully registered heterogeneous
  original source fixtures, rank/oracle parity and page CPU/schema bytes.
- [ ] Run full adjacent suite, repository Ruff, Pyright and attempt full
  project tests; don't call interrupted runs green.
- [ ] Independent whole-branch review; RED→GREEN for Important findings.
- [ ] Publish stacked Draft PR against #1796, link to issue and record
  exact-head CI. Keep external A6/A7/A8 quality and E2 gates open.
