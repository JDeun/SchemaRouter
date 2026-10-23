# Original-paper Algorithm 1 ToolCall Projection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Project source-attested original-paper complete field alternatives into ordered, dependency-aware existing `ToolCall`s without granting execution or fabricating arguments.

**Architecture:** Consume current opt-in `retrieve_paper_field_coverage`, original registry and the same principal-scoped source view. Build nonexecuting structured call recipes by reusing the existing `ToolCall`/evidence contracts and rechecking the original proof before return; keep default product routing untouched.

**Tech Stack:** Python 3.10+, Pydantic v2, SchemaRouter native graph index, pytest, Ruff.

**Spec:** `docs/superpowers/specs/2026-10-24-paper-algorithm1-toolcall-design.md`

## Global Constraints

- Fixed K5; explicit principal, owner-reviewed concept catalog, current source index and policy; no new planner, index, agent or executor.
- Never manufacture downstream input values from query or structural graph. Dependent `ToolCall.arguments` must remain empty and `missing_required_arguments` must expose source-bound requirements. An approved typed G5 inputful root must similarly expose **missing** original host input parameters, not fabricate values.
- Exact source-visible original field projection, schema/tool fingerprints and available evidence only; reject private/hidden or drifted source names.
- Output stays opt-in, nonexecuting, non-authoritative; no default/release/independent-E2 promotion.

## Review Focus

1. A dependent parameter accidentally marked executable despite having no observed producer value — regression `test_compiled_fork_unbound_arguments_remain_nonexecutable`.
2. A same-name private field leaking in the compiled `ToolCall.fields` — regression `test_compiled_direct_reuses_exact_scoped_field_projection`.
3. A malformed forward dependency or duplicate binding being projected as an executable plan — regression `test_compiler_rejects_unproved_or_changed_dependency`.
4. Source scope/availability changing between proof and return — regression `test_compiler_rejects_mid_projection_source_revocation`.
5. A noncomplete K5 result quietly exposing calls — regression `test_compiler_preserves_no_proven_hit_or_over_k`.

---

## Task 1: Existing ToolCall contracts over proved P1 receipts

**Files:** create `src/schemarouter/paper_field_plan.py`, create `tests/test_paper_field_plan.py`, modify `src/schemarouter/__init__.py` and `tests/test_public_api.py`.

**Interfaces:** `compile_paper_field_toolcalls(router, query, *, principal, catalog, index, k=5) -> PaperFieldToolCallPlan`; `PaperFieldArgumentDependency(consumer_call_index, parameter, producer_call_index, producer_field)`; `PaperFieldCallAlternative(calls, dependencies, required_semantic_ids)`; `PaperFieldToolCallPlan(status, snapshot_id, registry_version, requested_k, alternatives, executable_authority=False, independent_quality_evidence=False)`.

- [x] Write RED tests for exact direct field projection, complete one-root/two-leaf fork with unresolved consumer arguments, and preserving noncomplete source dispositions.
- [x] Run selected RED tests and confirm missing compilation API as the reason.
- [x] Implement minimal explicit planner-model composition and source authorization/provenance checks; invoke fresh P1 proof before and after projection.
- [x] Verify GREEN and add negative RED tests for malformed dependency/late revoked scope/unchanged default; implement corresponding fail-closed guards.
- [x] Run focused paper/native tests and repository lint; full suite outcome recorded below.
- [x] Commit isolated work and publish as [stacked Draft PR #1747](https://github.com/JDeun/SchemaRouter/pull/1747) against existing PR #1746; no merge or parent-issue closure.

## Task 2: Later owner-reviewed parameterized sources and native adapter evidence (out of this first slice)

- [ ] Require an explicit host-approved original input contract before permitting any parameterized source/root; no guessed OPTIMADE unit normalization.
- [ ] Prove concrete root argument validation and existing executor behavior against source-native real adapters; hold independent E2 until #1346 has provenance.

## Implementation ledger

- Plan started after exact-head #1746 P1 dedicated CI succeeded; full `CI` workflow was still in progress. No default release or independent E2 claim.
- RED: compilation API absent, import collection failed; GREEN: initial 10 public/plan tests then 76 focused paper/native/public-API tests passed, Ruff clean. Added 5,000-source-route fork contract, six-alternative `over_k_unranked`, unbound arguments, exact original projection and unchanged default.
- Additional observed RED: changing owner catalog aliases or authorization policy **after first P1 proof** preserved the same selected fields and wrongly returned success (two tests failed). GREEN: freeze principal, catalog, policy and source witness before the first proof; compare after the second proof, with late-change regressions passing.
- Native graph dependencies are structural only; the compiler emits no concrete dependency values. Host-approved typed G5 inputful roots are represented with missing values; concrete host-bound arguments and OPTIMADE optional/required parameter adaptation are explicitly out of this slice.
- Reviewer found the P2 direct test did not actually use a `DataScopeRule`; added real hidden-field and hidden producer-ID cases plus EN/KO/JA compiled native OpenAPI/MCP scope restriction tests. Actual scoped visibility changed empty input-schema envelope presentation, so compiler must verify input-free roots from the authoritative original endpoint, not the derived scoped view.
- Reviewer also reproduced valid P1-approved inputful G5 root failure. Added RED native post ID→user ID→username case, then GREEN qualified `approved_host_roots` + `_host_source_input_names` verification and exact **missing** host-root arguments. Unsupported/unreviewed inputful roots still fail closed. Concrete host values remain excluded.
- Post-review focused verification: **101 passed** (`test_paper_field_plan`, source-native OpenAPI/MCP/OPTIMADE P1 coverage, native fork/G5 host root, native FieldGroup, public ABI). `ruff check .`: **All checks passed**. `pyright src/schemarouter/paper_field_plan.py`: **0 errors, 0 warnings**. Earlier bare pytest was attempted but stopped after lengthy no-progress near 13%, so full-suite-green is **not** claimed.
- Reviewer verdict: no Critical; two Important findings (real data-scope test gap and approved inputful-root ambiguity) fixed with tests before publishing; one Minor mutable nested `ToolCall` receipt explicitly documented. No independent E2.
- Publication: GitHub connector commit `965234e066e87ab1aa0a9399224567dd187f491a` has exactly the same tree SHA `76cadecd35695e6c93ede9965abaa5b92a3909bb` as locally verified `c4598fb` and remote P1 parent `5a530e6`. PR #1747 targets the P1 feature branch and remains Draft. Issue #1560 received exact-head status comment. Parent PR #1746 broad exact-head CI run #40040143730 ultimately succeeded; P2 exact-head Actions were still running at publication.
