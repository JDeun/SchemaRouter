# B1 Input Parameter Review Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. Steps use checkbox syntax.

**Goal:** Complete review-first Algorithm 1 P2 input shape wiring without any provider data access.

**Architecture:** Add guarded `parameters_meta` to the existing immutable review
receipt, generated from the exact current scoped endpoint via the already
public `PaperPlanParameterMeta` projection. Re-attest the full receipt twice.

**Tech Stack:** Python 3.12, pytest, Ruff, Pyright.

**Spec:** `research/autoresearch/core-parameter-review-20261027-design.md`, issue #1791.

## Global Constraints

- No raw provider schemas/annotations or inferred semantics; no data execution.
- Preserve principal-scoped route/field eligibility, source fingerprints and K5.
- Keep plans/engineering notes outside the independently reviewed bilingual `docs` tree.

## Review Focus

- DataScopeRule-hidden output aliases must not appear through input names.
- Mutation of scoped input projection between passes must invalidate the page.
- A wide input-only schema must not evade count or byte budgets.
- The review-only session must not call a model/executor or gain authorization.
- A compiled plan after catalog approval should report the same input shape.

### Task 1: Wire and bound typed input review

**Files:** `src/schemarouter/field_routing_session.py`,
`tests/test_schema_field_routing_session.py`, `README.md`,
`examples/schema_only_field_routing.py`, canonical paper handoff.

**Interfaces:** `SchemaFieldReviewRoute.parameters_meta:
tuple[PaperPlanParameterMeta, ...]`; public
`SchemaFieldRoutingSession.inspect_visible_fields(...)` unchanged.

- [x] Step 1: Add source-input review, hidden alias, overwide, and in-flight
  mutation tests with literal expectations.
- [x] Step 2: Run `python -m pytest tests/test_schema_field_routing_session.py -q`
  and observe RED for the missing input receipt/budget behavior.
- [x] Step 3: Reuse `_paper_public_parameters(scoped)` and include its counts
  and UTF-8 metadata in the existing bounded page calculation.
- [ ] Step 4: Confirm GREEN with the full session test file and adjacent typed
  plan/authorization test files, then Ruff and Pyright, and run project-wide
  pytest to report either success or named unrelated failures.
- [ ] Step 5: Update README, runnable example and canonical handoff; commit
  the verified issue-sized change, publish a stacked Draft PR and track
  exact-head protected CI without claiming release qualification.
