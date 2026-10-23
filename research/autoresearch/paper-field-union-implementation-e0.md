# Original paper Algorithm 1 recovery — P1 FieldGroup union, source-attested E0

**Canonical user request:** Prioritize original paper's query→intent/concept→required response FieldGroup→typed and source-safe tool/field plan instead of becoming an unrelated producer-only graph or agent project. **Primary source:** [JDeun/paper_SchemaRouter paper §4 Algorithm 1](https://github.com/JDeun/paper_SchemaRouter/blob/main/paper/schemarouter.tex). Decision: [paper parity Draft #1745](https://github.com/JDeun/SchemaRouter/pull/1745), [architecture crosswalk](https://github.com/JDeun/SchemaRouter/blob/docs/paper-algorithm1-product-parity-20261024/docs/research/original-paper-algorithm1-parity.md). Work owners: [#1535](https://github.com/JDeun/SchemaRouter/issues/1535) P1 pre-K field correctness; [#1560](https://github.com/JDeun/SchemaRouter/issues/1560) P2 paper-complete plans; [#1339](https://github.com/JDeun/SchemaRouter/issues/1339) languages; [#1346](https://github.com/JDeun/SchemaRouter/issues/1346) independent E2; [#1477](https://github.com/JDeun/SchemaRouter/issues/1477) real agent/reader; [#1356](https://github.com/JDeun/SchemaRouter/pull/1356) v0.18 HOLD.

## P1 code started (2026-10-24, opt-in not default)

Branch `feat/1535-paper-field-union-before-k-20261024`, based on `main` to avoid implicit release/default change. New `src/schemarouter/paper_field_retrieval.py::retrieve_paper_field_coverage` composes **existing**, source-attested methods. Host-approved query → concept → typed `FieldGroup` through `resolve_native_concepts`; source-scoped, complete *direct* and *one-hop* routes through `retrieve_authorized_concept_graph`; if these have no proven complete hit and exactly two required fields, candidate **shared-root fork** through `NativeSchemaGraphIndex.lookup_shared_root_forks`. No new graph/index/catalog/ranker/agent/executor.

Output is frozen `PaperFieldCoverage`: complete / no_proven_hit / over_k_unranked / budget_unsatisfied; `PaperFieldAlternative` per fully proved route set with `PaperFieldRoute` per original route. Each route lists **only needed source-visible field names** (all required semantic outputs, identifiers, typed bound producer-ID fields) and explicit `(consumer_parameter, producer_route_id, producer_field)` joins, plus original source fingerprints. Union across the complete alternative MUST cover all host-declared semantic fields **before K=5**. No arbitrary multi-source row merge; only a prior G5-verified common original identifier root. The result is **not** a `ToolCall`/execution grant.

Strict protections: explicit trusted principal/authorization; source data-scope view, source/license and typed-field qualification in reused primitives, source revision/index/fingerprint, live availability, policy digest, immutability of reviewed concept catalog/principal; exactly K5; never return partial fields, denied routes or private counts. The original `SchemaRouter.retrieve_authorized` and `plan/execute` remain entirely unchanged. No model calls required.

Code: `src/schemarouter/paper_field_retrieval.py`, exported via `__init__.py`; tests: `tests/test_paper_field_retrieval.py` covering owner-declared EN/KO/JA, 500 original-route catalog with same-root fork, hidden/denied/wrong-type traps, direct single-endpoint field completeness/projection, source revocation, stale original index, unmatched alias, invalid K and unchanged default. GitHub Actions: `.github/workflows/original-paper-field-coverage-e0.yml`.

## Exact continuation procedure across ChatGPT sessions

1. Fetch **this file**, PR #1745, issue #1535 and current native code. Do NOT rely on chat summary or reinterpret original paper from recent producer/consumer experiments.
2. Inspect **latest issue-linked implementation PR and its exact SHA/Actions runs**. Fix any failed pytest/Ruff/CI, investigate returned source-qualified receipts; preserve all negative evidence. Never infer green while workflow is running.
3. P1 next acceptance: mixed first-hop direct/one-hop/two-consumer fork across real OpenAPI+MCP+OPTIMADE adapter-native contracts, negative hidden-field + wrong unit/source/license/qualifier, alternative-over-K, no-fit/unknown alias, schema-policy-availability mutation during selection; explicit recall comparison with baseline under equal K5. Existing E0 tests are not publisher-independent E2.
4. P2 **after** P1 is green: compose source-verified `ToolCall(tool, endpoint, arguments, fields, evidence)` under host explicit input constraints using original `SchemaPlanner`/executor; no new autonomous agent loop and no unbound synthetic arguments.
5. P3: source-/author-independent field and reader gold, same actual data reader, measure *retrieved DATA-context* tokens, full answer quality, provenance and license claims, separate from source JSON schema token and agent input+output tokens. #1346 BLOCKED_EXTERNAL until provenance exists.
6. Keep all implementation opt-in pending independent qualification. Do not merge/change production `retrieve[_authorized]`/security or merge #1356 release HOLD without gates.

**Evidence status at creation:** implementation changes submitted, CI outcome must be inspected. This note documents procedure, not passing tests or full original-paper parity. Update this exact file after each measured fix with branch/PR/head SHA, failed/passed jobs, remaining acceptance blockers and next code entry point so the next session can continue without context loss.

## Verified engineering checkpoint (2026-10-24)

**Measured code head:** `aec34cb255f8dd04ca523a1b1d6c591bf310d234`
on [Draft PR #1746](https://github.com/JDeun/SchemaRouter/pull/1746)
stacked **conceptually** on paper-first architecture
[Draft PR #1745](https://github.com/JDeun/SchemaRouter/pull/1745),
but branched from untouched product `main` for safe independent review.

[Dedicated source-native field coverage GitHub Actions #40037124349](https://github.com/JDeun/SchemaRouter/actions/runs/40037124349):
**SUCCESS — Ruff all checks passed and pytest 28 passed** (`tests/test_paper_field_retrieval.py` and existing
`tests/test_native_field_group_retrieval.py`). New P1 source-owned
tests include 6 EN/KO/JA × normal/mixed split-field fork cases,
full direct-projected case, unavailable/hidden typed source,
unchanged default retrieval and source revision fail-closed.
Existing native FieldGroup Pre-K, indexed typed G5, source postings,
source attestation and concept composition workflows also passed on
this code head. The initial prior-head static import error and public
ABI list mismatch were FIXED; `tests/test_public_api.py` now
explicitly lists the four opt-in exported receipt names. Full CI
[run #40037124414](https://github.com/JDeun/SchemaRouter/actions/runs/40037124414)
was at last inspection **10 passed jobs, 5 in progress, 1 queued,
4 skipped, 0 failures**; check its **final status**, do not claim all
green before completion.

**Current implemented P1 scope:**
- EXACT host-approved aliases+fully conjunctive FieldGroup after source
  authorization, before K5 route disclosure, over 1 direct endpoint,
  1 existing G5 one-hop (inherited), or strictly original shared-root
  TWO consumer fork; returns required per-route source-visible output
  field projection, typed input source binding, immutable fingerprint
  receipts. All alternatives complete before publication.
- This does NOT solve arbitrary fields split across *unrelated*
  providers, unknown multi-field inference, actual small-LLM
  `Understand`, full paper `ToolCall` or general mixed schema
  consumer group algebra. Do not promote as full #1535 completion
  until negative and real-adapter cases in the steps above qualify.
- No product default, host execution authority, source policy, data
  scope, frozen research scores or release was changed.

**Next exact step for another session:** inspect current PR #1746
checks; add native OpenAPI + MCP + OPTIMADE actual adapter
contract regression that proves direct + valid common-ID split field
path without exposing hidden/denied fields. Then enforce
more negative unit/qualifier, >K alternatives, source-health
mid-request mutation and source owner-change checks. Only
after P1 source-attested tests green, begin P2 #1560 using
original `SchemaPlanner/ToolCall` to assemble the paper-complete
non-agent plan. Independently authored #1346 E2 remains blocked.
