# Implementation plan: G5 dependency-path Rank

Spec: [2026-10-28-paper-native-g5-path-rank-design.md](../specs/2026-10-28-paper-native-g5-path-rank-design.md)
Issue: #1799. Base: Draft #1798 head `e6493ae66aaafa64c14a1f990a405ce0894296cc`.

## Global constraints

- No policy means byte-compatible/default status behavior.
- No model or provider callback performs ranking; no source tool is executed.
- Rank only complete, current-authorized and source-pinned typed candidate paths.
- One complete dependency DAG per plan; no mixing path bindings.
- Preserve explicit named target override, exact K5 and non-executable plan receipts.
- Owner-ranked path expansion hard-caps at 5,000. Do not expose partial paths/counts after overflow.
- E0 results do not satisfy independent E2 or release gates.

## Task 1 — Write RED regression tests first

**Files:** `tests/test_paper_native_rank.py`, `tests/test_native_graph_index.py`, `tests/test_paper_understood_graph_plan.py`.

- Test the path comparator with source-pinned one-hop and two-hop candidate fixtures: exact match before partial, web demotion, named-target priority, minimal visible binding/output count, and stable complete-path tie.
- Test compiler selects one highest-ranked path under explicit policy but still returns `ambiguous_paths` / `over_k_unranked` without policy.
- Test target names remain an explicit override, a policy cannot mutate during an availability callback, and revoked/hidden/denied/source-drift paths are never returned.
- Test owner-ranked cohorts of 500 and 5,000 paths against an independently computed fixture oracle; 5,001 must fail closed without candidate names or partial counts.
- Run focused tests and confirm expected failures before implementation.

**Expected RED:** new APIs/behavior absent; no existing unrelated regression.

## Task 2 — Implement deterministic path Rank and bounded G5 support

**Files:** `src/schemarouter/paper_native_rank.py`, `src/schemarouter/native_graph_index.py`.

- Add path-ranking helpers using complete one-hop/two-hop candidates and the existing `PaperNativeRankPolicy`.
- Add opt-in rank-policy plumbing to native G5 lookups, validate snapshot/annotation routes, and make target-prefilter bounds policy-dependent (32 legacy/research, 5,000 owner-ranked).
- Keep full current-authorization, availability, scope, source fingerprint and typed-binding revalidation. Return only K5 ranked candidates and a separate deterministic-rank marker.
- Preserve the external research callback's existing 32-candidate cap and prohibit combining it with owner policy.
- Add a generic fail-closed budget status for owner-ranked expansion above 5,000.

**Expected GREEN:** focused native graph/rank tests pass; old research callback tests retain the 32-path contract.

## Task 3 — Wire one-DAG selection and add E0 benchmark

**Files:** `src/schemarouter/paper_understood_graph_plan.py`, `tests/test_paper_understood_graph_plan.py`, new `scripts/research_paper_graph_rank_benchmark_e0.py`, this plan/spec and research notes.

- Derive rank aliases only from owner-reviewed intent/concept declarations.
- Pass explicit owner policy into one-/two-hop G5 lookup and re-attest policy/source after candidate ranking and materialization.
- Select exactly the top complete DAG only when the deterministic owner policy was used; otherwise retain ambiguity and overflow statuses.
- Mark the resulting plan `ranked_unverified=True`, with `executable_authority=False`.
- Benchmark deterministic 500/5,000 candidate cohorts against an independent oracle; report p50/p95/p99 wall/CPU and output bytes without E2 or speedup claims.

**Expected GREEN:** graph-plan tests, benchmark smoke, Ruff and Pyright pass.

## Task 4 — Final verification and review

- Run focused G5, direct Rank, public session, model-callback, native index, benchmark and package test suites.
- Check the latest exact-head GitHub Actions run and all required checks; if any fail, diagnose the cause and fix in a new test-first pass.
- Review the complete diff for authorization/visibility leaks, callback mutation, typed-join revalidation, accidental default promotion and altered legacy semantics.
- Create a draft PR stacked on #1798. Do not merge or promote defaults.

**Expected:** exact-head checks green before describing the implementation as CI-verified; any still-running or unavailable checks are explicitly reported.
