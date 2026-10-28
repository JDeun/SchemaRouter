# Actual Anonymous Public Route Selection E1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Quantify honest unhinted natural-language tool/endpoint/field selection against the previously verified real public REST, OPTIMADE and MCP registry.

**Architecture:** Fixed multilingual source-task labels are withheld from the native router. Existing bound native retrieval and planning outputs feed a source-agnostic metric calculator; only an opt-in live entry point registers original public providers. All evaluation outcomes, including misses/zero-score/no-fit and missing arguments, are preserved as observations, without oracle-assisted execution or ranking changes.

**Tech Stack:** Python 3.12, native SchemaRouter planner/retrieval, existing public 3-provider loader, pytest/Ruff/Pyright, dedicated GitHub Actions offline workflow.

**Spec:** `research/autoresearch/public-anonymous-route-selection-e1-design.md`

## Global constraints

- Frozen host cases; never put oracle tool, endpoint, language or concepts into `PlanRequest` besides natural query text.
- Real external discovery only with explicit `--live`; no key/auth, arbitrary URL, side-effect tool execution or external network PR job.
- Source-owned route names/fingerprints; no fake publisher gold, automatic cross-provider semantic claims or E2 qualification.
- Preserve Draft #1755, #1346/#1477 BLOCKED_EXTERNAL and #1356 HARD HOLD.

## Review Focus

- Native retrieval returns 0-score candidates: metric must not count them as evidenced successes or execute them.
- Two endpoints of one provider tie: exact endpoint matters; provider-only hit is insufficient.
- A Japanese/Korean no-match must not be changed to success by a source-named query or an expected-tool override.
- Actual planner may propose a different endpoint: report it as observed and retain missing mandatory arguments; do not fabricate source values.
- Source discovery failure or stale registry must fail the live run, not use offline snapshots and call itself live.

---

### Task 1: Offline reproducible host-labeled source-task evaluator

**Files:** Create `scripts/research_public_heterogeneous_selection_e1.py`, `tests/test_research_public_heterogeneous_selection_e1.py`.

**Interfaces:** `CASES: tuple[SourceQueryCase, ...]`, `evaluate_selection(router: SchemaRouter, cases=CASES) -> dict[str, Any]`, `score_selection_report(rows: list[dict[str, Any]]) -> dict[str, Any]`.

- [x] Add failing test for Top-1/Top-5 exact endpoint, correct denominators, zero-score negative/positive distinction, no-label-leak and planner missing argument capture. Observed targeted RED during implementation.
- [x] Implement frozen EN/KO/JA + off-topic cases and bounded pure report scorer, use real `router.retrieve_executable`/`router.plan_executable`, no mocked ranking or model.
- [x] Rerun targeted pytest GREEN; verify existing source validation suite unchanged (248 related tests passed, including original live adapter tests).

### Task 2: One real registry and reproducible CI handoff

**Files:** Modify same script/tests; create `.github/workflows/research-public-heterogeneous-selection-e1.yml`; update `research/autoresearch/paper-toolcall-implementation-e0.md` and this plan.

**Interfaces:** `async run_live_selection_e1() -> dict[str, Any]`, `--live` opt-in CLI.

- [x] Cover unsafe source/endpoint drift, strict report evidence flags, CLI no-network guard and source-failure redaction in the offline tests. The initial source-drift/evidence tests observed RED; later CLI safety additions were checked directly GREEN.
- [x] Register Crossref's **bundled original-source provider profile**, remotely discover COD OPTIMADE and remote DeepWiki MCP under one `SchemaRouter`, evaluate unhinted queries with **no endpoint execution**, report per-language and all failures verbatim as structured bounded outcomes.
- [x] Verify source-derived metrics with opt-in real network; source defects are factual fail or incomplete, never force a passing numerator. Crossref live contract discovery is **not** claimed: the separate preceding source matrix already executed Crossref REST.
- [x] Repository Ruff and scoped Pyright passed, 248 related native tests passed. Capped full pytest ran 75s to about 8% without finishing (exit 124): **not** a full-suite green claim.
- [ ] Independent read-only review, commit one issue-sized update to Draft #1755; verify remote blob/tree SHA and exact-head CI, never merge/promote.
