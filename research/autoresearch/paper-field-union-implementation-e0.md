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

## P1 adapter integration checkpoint — 2026-10-24

**Measured code HEAD** `d3aac353c034e3bb471b822c583dae91c9cab666` in [Draft PR #1746](https://github.com/JDeun/SchemaRouter/pull/1746).
**Actual [GitHub Actions #40038357211](https://github.com/JDeun/SchemaRouter/actions/runs/40038357211): SUCCESS, Ruff all checks passed, `59 passed in 5.83s`.**
This dedicated workflow validates THREE source-native suites together:
`tests/test_paper_field_retrieval.py`,
`tests/test_paper_field_real_adapters.py`, and
`tests/test_native_graph_shared_root_forks.py`, plus the existing
`tests/test_native_field_group_retrieval.py`.

New concrete adapters and safety controls:
- Actual `tool_from_openapi` and `tool_from_mcp` direct readers, with
  **explicit LOCAL host approval of semantic IDs, source/license,
  read-only access**. Remote MCP `readOnlyHint` and schema alone
  confer **neither** authority nor a paper-complete field group.
- Authorized output `status` + `priority` direct reader proves
  required field union for declared EN/KO/JA aliases.
- Partial OpenAPI alone + field-hidden MCP must **not** be stitched
  into an arbitrary field-complete plan. Full providers become no-fit
  when both priority outputs hidden; incompatible required unit or
  original `source_type` yields zero fit.
- SIX fully authorized source providers trigger `over_k_unranked`
  without truncation to an attractive top five. Mid-request
  replacement of authorization policy fails closed.
- Most importantly the existing **host semantic attestation**
  converter-native test in `tests/test_native_graph_shared_root_forks.py`
  now invokes `retrieve_paper_field_coverage` on its **real
  OpenAPI original ID source → two MCP consumer endpoints**, using
  original *verified* producer field→required MCP parameter bindings.
  Across EN/KO/JA all three source routes and both required semantic
  outputs must be present. If the MCP owner's semantic attestation is
  withheld, field union is **no_proven_hit**, not a guessed join.
  The original typed G5 one-root/two-leaf test stays intact.

**Important qualification:** These are real *converter code paths* on
locally constructed manifests, NOT a remote third-party MCP/OpenAPI
provider's independent task gold or production end-to-end reader.
No source connection/tool call/LLM generation was made.
No feature in this PR is promoted to default.

**Next P1/P2 technical tasks:** distinguish author-accepted
unsupported/ambiguous aliases from noncalibrated `no_proven_hit`;
negative provenance/qualifier/physical unit compatibility tests
on actual schemas; enforce source contract and policy/availability
mutations during joined three-tool selection; domain-neutral
completeness with >2 required fields rather than guessing an
unproved record merge. After the P1 contract is qualified, #1560
should reuse the library's existing `ToolCall` and original
`SchemaPlanner` to build the paper's final plan. Independently
authored #1346 source-disjoint E2 stays **BLOCKED_EXTERNAL**.
The full protected CI/code-scan on the code HEAD had NOT
been declared complete at this checkpoint; check its latest
SHA-specific conclusion before merge/release claims.

## P1 late source-withdrawal regression — 2026-10-24 continuation

Continuation from Draft PR #1746's `30106715b4663c09199ce4ca44b553ad24085650`
head, against the original-paper source-attested opt-in path only.

- **Observed red test before the fix:** after a verified two-consumer fork,
  the final projection's last consumer health/scope callback withdraws its
  previously inspected original producer. `retrieve_paper_field_coverage`
  previously returned `complete`, because the initial per-route projection
  lacked a final whole-menu availability/scope pass. The failing regression
  is `test_shared_root_revoked_during_final_projection_cannot_be_published`.
- **Fix:** reuse one source-visible projection function for every original
  route, then re-evaluate **all** original routes after the first pass,
  comparing exact field projection, typed semantic hits, identifiers,
  fingerprints and route bindings. A later health/scope withdrawal aborts
  with generic `PolicyViolationError`, never a partial menu or private
  provider callback exception. This is an additional observation, **not an
  atomic cross-provider transaction** or revocation guarantee after return.
- **Actual adapter boundary:** added local converter-native OPTIMADE discovery
  cases with host-assigned semantic IDs and EN/KO/JA concept aliases.
  The present P1 API must abstain: native `search_structures` has optional
  query parameters, and `get_structures` requires a bound `id`. These
  cannot be silently converted into an input-free direct `ToolCall`, nor can
  a remote OPTIMADE `x-optimade-unit` extension be taken as a host-approved
  type/unit coercion. A future #1560 explicit host-argument plan is needed.
- **Local focused verification:** 66 tests passed across the four original
  paper/native regression suites, and repository-wide Ruff passed, after
  the red→green cycle. This is local E0 only. Full-suite/CI/published SHA
  must be recorded from their own results; no independent E2 is asserted.

**Next:** close the exact-head CI loop after publishing; add source-owner
reviewed optional/required argument binding and OPTIMADE numeric-unit
canonicalization only under a separately verified trusted contract in
#1560; preserve strict K5, default routing and #1356 release HOLD.

## P2 source-attested ToolCall projection — 2026-10-24 continuation

Draft PR #1746 P1 head was published through the authenticated GitHub
connector as `5a530e6440601a9fcc0083730653d246014deac8`, with
the exact identical tree as local late-revocation fix. The **original-paper
dedicated workflow #40040143726**, native FieldGroup, G5 typed graph,
host evidence, research candidate, retrieval fast path and CodeQL all
reported `success` on that head. The broad `CI` remained `in_progress`
at the last check; never infer entire CI from the dedicated workflow.
Issue #1535 has the exact published checkpoint comment.

Follow-on #1560 is on branch
`feat/1560-paper-field-toolcall-plan-20261024`, published as
[stacked Draft PR #1747](https://github.com/JDeun/SchemaRouter/pull/1747)
at initial source SHA `965234e066e87ab1aa0a9399224567dd187f491a`
based on verified P1 GitHub SHA `5a530e6440601a9fcc0083730653d246014deac8`.
Spec: `docs/superpowers/specs/2026-10-24-paper-algorithm1-toolcall-design.md`;
plan: `docs/superpowers/plans/2026-10-24-paper-algorithm1-toolcall.md`.
New `src/schemarouter/paper_field_plan.py::compile_paper_field_toolcalls`
composes ONLY original P1-complete, source-scoped routes into existing
`ToolCall` descriptors, source-first with separate original typed
`PaperFieldArgumentDependency` receipts. Required consumer ID values
remain deliberately **unbound** and `ToolCall.executable=False`; producer
input-free calls and direct reads have no invented arguments. No calls are
executed; result explicitly carries `executable_authority=False`. All
P1 no-hit/over-K statuses and fixed K5 are preserved with empty output.
The original `SchemaRouter.plan/retrieve/execute` functions are untouched.

**P2 reviewer follow-up:** added genuine `DataScopeRule` hidden-field
and hidden original producer-ID regressions, and actual native
OpenAPI/MCP compiled source visibility checks across three declared
EN/KO/JA query aliases. Qualified G5 `approved_host_roots` can prove a
parameterized producer topology: the compiler now represents such a
root with its original required input names in
`ToolCall.missing_required_arguments` and no invented values, alongside
the consumer's unresolved typed dependency. Source input envelopes
are checked on the original, fingerprint-pinned endpoint: a scoped
read-only view may change empty JSON schema presentation without
altering the original input-free source contract. **No actual concrete
host inputs, execution or OPTIMADE coercion are implemented.**

IMPORTANT observed red→green: mutations to source-owner aliases or
policy after the FIRST complete P1 proof but before final compiler
projection initially slipped through when the selected fields stayed the
same. Tests reproduced both failures. The compiler now freezes principal,
catalog, policy and original source witness BEFORE P1 and compares
the full declaration/proof AFTER the second re-proof. No atomic live
provider transaction is claimed. P2 test matrix includes direct and
one-root/two-consumer fork, actual 5000-route index, hidden/denied and
availability/owner drift, over-K no-public-output, and EN/KO/JA.

Remaining #1560: full source-owner-approved concrete argument binding
for parameterized roots (including authentic OPTIMADE schema quirks),
observation-time dependency materialization through the existing
executor, independently authored #1346 E2. Keep parent issues open,
Draft PRs unmerged and release HOLD. Next session should inspect the
latest stacked P2 PR/checks and continue these remaining acceptance
criteria; see plan ledger and SHA-specific outcomes for exact status.

**CI closure:** P1 #1746 exact-head broad [CI run #40040143730](https://github.com/JDeun/SchemaRouter/actions/runs/40040143730)
subsequently reported **SUCCESS**. Its exact-head dedicated paper
workflow and eleven other listed workflows also reported success.
P2 #1747 Actions were triggered and were **in progress/queued** at
publication; do not infer their result from P1.

**Dedicated P2 CI regression follow-up:** existing
`.github/workflows/original-paper-field-coverage-e0.yml` was originally
triggered only by P1 source/tests and did not execute the P2
`test_paper_field_plan.py` module. Add source and test path triggers,
P2 Ruff checking, and the P2 + approved-native-host-root pytest suites
to the same pinned runner/workflow without changing its protected name.
An explicit unit test now asserts the workflow coverage; it failed
before the workflow fix and passed after. Local integrated suite then
reported **102 passed**, repository Ruff and P2 Pyright green.

## P2 draft CI follow-up: paired Korean documentation — 2026-10-24

The exact PR #1747 head `07206644c1ee9b354d45a4d5a83851cd9ee1ced7`
(tree `3dc19520a0d38106efa6baf869aae7d286a19207`)
triggered GitHub Actions. The **Korean Translation Whole-Corpus Coverage
Report** run `40041770745` failed: one of 69 local-equivalent tests
reported two new English `docs/superpowers/` pages missing from the
protected English/Korean paired semantic-spotcheck ledger. This was a
real CI failure; it was not evidence of an Algorithm 1 compiler defect.

Added equivalent Korean specification and implementation-plan pages under
`docs_ko/superpowers/`, and registered both exact EN/KO Git blob hashes
in `audits/ko-direct-semantic-spotcheck-2026-10-12.json`. The ledger
explicitly identifies the paired reading as **AI-assisted only**;
independent editorial sign-off remains outstanding under #1202. The
full translation-workflow pytest invocation now reports **69 passed**
locally; repository-wide Ruff and `git diff --check` are green. Recheck
the new published exact GitHub head and every Actions conclusion after
this follow-up—do not assume that local results imply green CI.

No changes to the original P2 compiler, live execution, default routing,
independent E2 or the v0.18 release HOLD were made in this follow-up.

## P2 next incremental step: host-owned root input binding — 2026-10-24

After the prior PR #1747 source commit, a **new opt-in, nonexecuting**
`bind_paper_field_host_inputs` function was implemented in the same
`paper_field_plan.py` module. It accepts a previously compiled P2
recipe, chooses one alternative, and requires the host to supply the
**exact complete scalar arguments** of its explicitly approved G5
original source root. It re-derives the entire source-attested P2 proof,
rejects caller-tampered or stale recipes, confirms the original
`approved_host_roots` and closed `_host_source_input_names` contract,
validates concrete values with the original schema under the runtime
JSON-Schema work budget, then re-proves source/authorization stability.
Input copies are checked against late callback mutation; a real RED
regression demonstrated why this is required. The returned selected
root `ToolCall` may have all required inputs populated, but downstream
producer→consumer ID arguments remain **unbound**, and the outer plan's
`executable_authority=False` stays unchanged. No provider invoker or
executor is called, and this is **not** an independent E2 result.

Independent review of this new binding API reproduced TWO Important
failures, with no verified Critical: (1) JSON Schema alone treated
`NaN`, infinity, complex numbers, `Decimal` and `Fraction` as acceptable
`number` inputs, which are not finite JSON-native scalar values; and
(2) a host-valid integer `max_hops=99` exceeded the current principal's
`DataScopeRule(max_hops=2)`, despite being marked bound. Both had genuine
RED regressions; the binder now requires strict JSON-native primitive
types with finite floats and validates the populated root call against
the same current principal-aware `authorization_policy.validate` used
by the protected execution boundary. This does NOT change shared
JSON-Schema validation globally or authorize invocation.

The GitHub exact-head run `40042138308` on prior SHA
`596705b047435815459a5dd3dae750c0eaf6ca32` exposed a second
distinct documentation gate: `scripts/prepare_korean_docs.py` requires
new bilingual pages to be listed in
`docs_ko/translation-manifest.json`, not just the paired audit ledger.
Added both exact EN source blobs. Local `prepare_korean_docs.py`
successfully prepared **158 translated pages and zero fallbacks**;
docs QA + paired ledger pytest and focused P2/native tests passed
locally (**128 tests including the reviewed numeric/data-scope
regressions**); the full translation CI-equivalent suite also reported
**69 passed**. Repository Ruff and P2 Pyright reported clean.
That previous exact-head Korean translation workflow passed, but
Docs Browser and Link QA failed before this manifest change; the broad
CI was still running at observation. The latest *new* head and
individual workflow conclusions MUST be checked after publishing this
step; no unpublished/local outcome should be represented as GitHub CI.

**Next #1560:** owner-approved, observed producer result→consumer
argument value materialization with verified result field contracts;
subsequent executor invocation only via existing host authority;
source-native OPTIMADE accepted argument/unit contracts and truly
independent source-disjoint E2 #1346 still pending. Keep both PRs
Draft, parent issues open and release HOLD.
