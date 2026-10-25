# Original-paper Algorithm 1 continuation — P2 source-typed ToolCall E0

**2026-10-24 · E0 source-authored diagnostic, not a shipped/default executor.**

## ACTIVE CROSS-SESSION RESUME — 2026-10-25 (supersedes older next-step notes below)

**Canonical continuation:** Original-paper Algorithm 1 is now beyond the P2
typed plan and observed-execution slice described in this historical handoff.
Do **not** restart at P1/P2 or open another parallel agent/executor. The active
stack is **Draft #1754** (native indexed direct FieldGroup → existing fixed-K
agent) followed by **Draft #1755** (structured paper `Understand` hints →
intent-required field union → exact named-tool direct receipts → host-owned
empty-menu terminal), on top of the earlier paper work (#1745–#1753).

| Current surface | Exact resume evidence | Limit |
| --- | --- | --- |
| Source-bound typed direct plan | `src/schemarouter/paper_understood_direct_plan.py`; [Draft #1755](https://github.com/JDeun/SchemaRouter/pull/1755) | Untrusted structured hints are already parsed externally; not a validated LLM parser |
| Original named tool before K | `NativeSchemaPostingIndex.lookup(..., allowed_tool_keys=...)` | Unknown/denied/hidden/unlicensed tools produce `no_proven_hit`; owner schema and principal permissions are still mandatory |
| Existing agent E0 adapter | `scripts/research_authorized_concept_fixed5_agent_bridge.py::AuthorizedPaperUnderstoodDirectFixed5Selector` | The original captured principal-visible lexical menu may still exclude an otherwise index-eligible route |
| Host-owned no-offered-tool refusal | `run_generated_episode(..., experimental_host_empty_menu_terminal=True)` | Exactly zero model generations and tool attempts on **empty verified menu**, with `REQUEST_MORE_TOOLS` generic benchmark terminal; default off; not global no-fit |
| Outcome taxonomy | `ready`, `requires_arguments`, `no_proven_hit`, `over_k_unranked`, `budget_unsatisfied` | Missing tool proof, K overflow, missing input and semantic absence remain different outcomes |

**Exact checkpoint:** local branch
`feat/1560-paper-understood-direct-e0-20261025`, local Git commit
`e917341` and Git tree `d53b2cb80c516470bcd693520cfbdd77820fbd87`.
Published [Draft #1755](https://github.com/JDeun/SchemaRouter/pull/1755)
head `669c4577c45af5e6ac8cb251da72bfb0c54c2cde` has **the exact same
Git tree**, despite different local/remote commit metadata. Keep it **Draft**;
do not merge into the stacked parent or release. Source-proven predecessor
[Draft #1754](https://github.com/JDeun/SchemaRouter/pull/1754) already passed
its protected workflow suite before #1755's continuation.

**Tests and protected workflows (latest observed 2026-10-25):** seven related
paper/agent/posting suites **210 passed**, repository-wide Ruff passed,
changed research selector Pyright 0 errors. The **entire** local `pytest`
command still times out at ~12% (85-second cap, exit 124); full local
Pyright reported 85 environment-wide errors/8 warnings with optional
imports unresolved, so neither entire local suite is claimed green.
For the exact remote head `669c4577`, **21/22 GitHub Actions workflows
were successful and the remaining Python 3.12 full-suite CI run was still
in progress** when recorded; no final all-green assertion until a new read.
Remote Actions/CodeQL and exact SHA remain the authority after changes.

**Mandatory immediate next steps, in order:**

1. Check #1755's **exact remote HEAD and remaining protected CI**, fixing any
   failure by test-first changes; do not infer success from ancestor PRs.
2. Read [direct source design](paper-understood-direct-e0-design.md),
   [direct implementation plan](paper-understood-direct-e0-plan.md),
   [new host refusal design](paper-host-empty-menu-refusal-e0-design.md), and
   [host refusal implementation checkpoint](paper-host-empty-menu-refusal-e0-plan.md).
   These internal, English-only research notes stay out of reviewed bilingual
   `docs/**/*.md` and **must be cited here** on each continuation.
3. Prioritize **major remaining Algorithm 1 behaviors**, not minute selector
   tuning: genuine bounded EN/KO/JA `Understand(q)` evidence; an
   independently justified ranking decision when >K; original source-safe
   one-/two-hop explicit tool override and host-attested parameter semantics.
   Preserve both supported **false refusal** and unsupported **false accept**
   measurements. For missing-tool refusals distinguish a currently unproved
   *authorized* capability from a globally nonexistent tool. #1291 owns
   prospective calibrated no-fit and #1477 owns paired independent agent E2.
4. Continue updating **this canonical handoff**, issue #1560, stacked Draft
   PR description and exact results after material changes. Independent
   publisher-authored #1346 and paired #1477 remain `BLOCKED_EXTERNAL`, while
   [release #1356](https://github.com/JDeun/SchemaRouter/pull/1356) remains
   **HARD HOLD**. No frozen #432 benchmark rewriting or default promotion.

The sections below record P2 history and remain useful as implementation
evidence; their older PR heads and next-step instructions are **not** the
current resumption point.

## Source of truth, predecessors and gates

- The research objective is the original [SchemaRouter paper §4 Algorithm 1](https://github.com/JDeun/paper_SchemaRouter/blob/main/paper/schemarouter.tex): query understanding, original graph/field selection, explicit `(tool, params, fields, meta)` plan. Source-grounded parity map: [Draft #1745](https://github.com/JDeun/SchemaRouter/pull/1745).
- P1 source-visible required field **AND** before K5: [Draft #1746](https://github.com/JDeun/SchemaRouter/pull/1746), [canonical P1 handoff](paper-field-union-implementation-e0.md), issue [#1535](https://github.com/JDeun/SchemaRouter/issues/1535). Exact GitHub commit `472122bd2d97ed073baaeb7dd576e97c64f6e04b` has **13 successful Actions workflows**, including full CI, CodeQL, and Original Paper Required Field Coverage E0.
- This P2 implementation is scoped to issue [#1560](https://github.com/JDeun/SchemaRouter/issues/1560), now published in [Draft PR #1748](https://github.com/JDeun/SchemaRouter/pull/1748) on **stacked branch** `feat/1560-paper-toolcall-plan-e0-20261024` based on P1 commit `472122bd2...`. The PR's live **head SHA** is authoritative; do not infer it from the local Git SHA because connector-authored commits have different metadata but verified-identical trees.
- The independently source-authored E2 [#1346](https://github.com/JDeun/SchemaRouter/issues/1346) is **BLOCKED_EXTERNAL**; live reader/agent E2 [#1477](https://github.com/JDeun/SchemaRouter/issues/1477) is not completed. v0.18 release [#1356](https://github.com/JDeun/SchemaRouter/pull/1356) remains **HOLD**.

## Implemented bounded P2: `compile_paper_typed_tool_plan`

Entry point: `src/schemarouter/paper_typed_tool_plan.py` (also explicit public exports in `src/schemarouter/__init__.py`). Tests: `tests/test_paper_typed_tool_plan.py`, plus real OpenAPI-producer → host-attested MCP-consumers assertions in `tests/test_native_graph_shared_root_forks.py`, and host-parameterized producer → consumer validation in `tests/test_native_graph_host_root.py`. Focused workflow: `.github/workflows/original-paper-toolcall-plan-e0.yml`.

**New P2 executor-observation slice (Draft #1748 continuation):** `src/schemarouter/paper_observed_binding.py::observe_and_bind_paper_plan` is a separate **explicit async** API. Only after an exact complete P1/P2 source proof and fully supplied host-root inputs, it invokes **one read-only producer** once via the existing `SchemaRouter.execute(ExecutionPlan, RunConfig(max_tool_calls=1,max_attempts=1,max_remote_attempts=1))`. It uses the executor-produced `ToolResult`, not an arbitrary caller-supplied observation. For each P1 child, it obtains a fresh, *same original root + consumer + exact binding* G5 proof over the source-owner's relevant required FieldGroup, then reuses G5's internal scalar/field-contract checks to validate actual projected ID type, field presence, source schema and consumer input schema. It re-compiles P2 after the producer and after binding, and rechecks current principal data scope on **all concrete calls**. The return is `PaperObservedBinding(producer, plan)` with fully bound but **UNEXECUTED** consumers, `executable_authority=False`, `provider_provenance_verified=False`, `independent_e2=False`. It never runs leaves or accepts a fake caller-supplied `ToolResult` as authentic; fresh executor policy checks remain mandatory for any eventual consumer invocation.

**New explicit actual-consumer slice (2026-10-24):** `src/schemarouter/paper_consumer_execution.py::observe_and_execute_paper_plan` executes **producer + original consumers**, but only in this opt-in async call (not the default planner, `observe_and_bind_paper_plan`, or normal batch API). It owns the prior real executor observation *internally*; it does **not** accept a forgeable caller-constructed binding receipt. It pins the original `PrincipalContext` claims using a deep executor copy and rejects original or pinned claim mutation after every awaited source/consumer operation and immediately before publishing; `observe_and_bind_paper_plan` also rejects principal swaps during source observation. It re-compiles the same P1/P2 proof and verifies current caller scope before **and after each consumer**, executing the next leaf only after those checks. Each read-only original leaf uses a separate `ExecutionPlan` and existing executor principal authorization with `ExecutionBudget(max_tool_calls=1,max_attempts=1,max_remote_attempts=1)`. At most K-1 leaves execute sequentially, and any revocation, changed typed shape or transient failure halts without publishing a partial combined result. The API rejects source-required consumer fields absent from actual executor data using existing `ToolResult.field_contracts`, including **nested/wildcard `FieldSpec.result_path`** instead of assuming every selected field is a top-level key; object payloads and lists of objects are accepted, an empty list means no matching records. An explicitly present `null` can carry field metadata but `has_observed_value=False`; invocation success is not a claim of non-null factual evidence. Result: `PaperExecutedToolSequence(producer, consumers, plan)` explicitly `executable_authority=False`, `provider_provenance_verified=False`, `independent_e2=False`. This is measured **local E0** tool execution, not source-authenticated live E2 or paper answer quality. See [internal consumer execution plan](paper-consumer-execution-e0-plan.md).

**Review-driven K5 correction:** the original P1 shared-root fork can remain complete even when individual, *unrestricted* G5 one-hop result sets exceed K5 due to unrelated native roots. A review found that the first observed-binding implementation did an unrestricted per-leaf G5 lookup and could execute the root unnecessarily before failing `over_k_unranked`. A failing regression now proves one attested three-route P1 fork alongside **six unrelated status one-hop paths**. The corrected implementation preflights each **P1-pinned exact root+consumer pair before execution**, using the existing G5 `_lookup_native_paths` internal fork-arm **root and target filters**, which still perform source, type, scope, policy, health and fingerprint checks. The public K5 limit is NOT changed. To reuse G5's strict scalar/field-contract validator without forcing another unrelated public K5 menu, `native_graph_observation.py` now shares its internal `_materialize_original_observed_edge` between public observation (which retains BOTH normal unrestricted authorization lookups) and the paper path (which proves the selected exact pair before and after scalar materialization). No private candidate/count leaks into the result. The new regression is RED before and GREEN after the fix. Additional negative tests: missing/null/wrong/oversized original ID, revoked consumer authorization/availability after producer, exactly one producer attempt on transient failure, and no-fit host-parameterized 1:N fork.

The source-native **1:N shared-root fork proof deliberately excludes roots requiring host input** (`native_fork_index.py` rejects `source_root_parameters`). A host-approved parameterized original producer can be observed only in already proven **1:1 G5** shape. A separate source-owner-reviewed fork-root contract would be needed before lifting this constraint; do not manufacture a P1 proof for 1:N by repeating the root or inferring a join. The new observed binding test runs bound local invokers with one root + two leaves (zero consumer invocations) and a separate approved 1:1 host-parameterized root case. All of these are development-local E0; a registered invoker execution does not authenticate independent provider identity or establish answer quality.

Input: same **trusted** principal, owner-reviewed `NativeConceptCatalog`, source-native `NativeSchemaGraphIndex` and **exact** K5 as P1. First require `retrieve_paper_field_coverage` to prove a **complete** selected alternative. No tool/field inferred from text or untrusted metadata; no independent ranker/index/agent/LLM call. Then compile *only original source-attested routes* into standard `ToolCall` models:

- `.tool`, `.endpoint`, `.schema_fingerprint`, `.tool_fingerprint` from the original registry/index proof;
- `.fields` from the exact source-visible projection, `.evidence` from standard `available_evidence`, and projected `unit`, `qualifiers`, source/license per original field in `PaperPlanFieldMeta`;
- `.arguments={}` until **validated** host values or observed results are actually available; required inputs listed under `ToolCall.missing_required_arguments`;
- optionally `host_source_arguments={"original.approved_root": {"required_scalar": value}}` to supply an **exact complete** 1–4 scalar input envelope for an **already approved original G5 host source root only**. This reuses `_host_source_input_names` and exact JSON-schema validation, strict primitive types and bounds, and never accepts partial/default/unknown/consumer inputs. Only the source call's missing-input list is cleared; dependent consumer arguments remain deferred. No input values are inferred from the query or retrieved from a provider here;
- for an original record producer and up to four typed consumer branches, explicit `PaperPlanBinding(consumer_call_index, parameter, producer_call_index, producer_field)` with *no synthetic customer IDs*.

`PaperTypedToolPlan` has `status` = `ready` (only the call shape contains no missing required inputs), `requires_arguments`, `requires_observation`, or the source abstention (`no_proven_hit`/`over_k_unranked`/`budget_unsatisfied`). It is **not** `ExecutionPlan`, and sets `executable_authority=False` even for `ready`. Never feed dependent partial calls to the normal executor in one batch: that would be misleading because a producer might execute before a consumer's missing input fails. Actual invocation stays behind the existing per-call executor/authorization/evidence boundaries after runtime observation. No default `retrieve`, `plan`, or `execute` code was modified.

Two checks bound compilation: each route's original fingerprint/read-only/authorization/availability/scope and output projection is checked again, then the **entire** P1 result is recomputed and compared. For **argument-bearing calls**, the existing executor's `AuthorizationPolicy.validate_data_scope` and current **scoped input schema** are checked *before and after* the final P1 observation. For example, a scalar `max_hops=999` is **rejected** if the current principal's `DataScopeRule` caps it at `2`, although the original unscoped source schema allows integers. Original registry/index, principal, catalog, policy digest and retrieval witness must remain the same. Host callback errors during compilation are sanitized to generic `PolicyViolationError` without leaking private exception text. This is **two observations, not a linearizable provider transaction** and not a guarantee against revocation after the returned receipt.

Safety regression expectations:

1. Direct source complete: typed schema/projection/evidence, explicit IDs, no irrelevant fields and no execution.
2. 500-original-route mixed-scope fork: original root ID, one typed deferred consumer per required field, exact parameter/field bindings, no invented arguments; hidden/denied/unlicensed decoys excluded.
3. Missing leaf or unapproved required input: **no partial tool plan**.
4. Wrong K5, invalid alternative, stale original registry, revocation while compiling: fail closed.
5. Converter-native OpenAPI + MCP fixture: cannot publish a fork without the owner-reviewed input/output semantic attestation; EN/KO/JA aliases cover same original field contract.
6. Host-approved required producer input (`post_id`) stays explicitly *missing*, downstream `user_id` remains dependent on observed `userId`. An unapproved host root is `no_proven_hit`; no bound local test invoker is called.
7. When the caller explicitly provides `posts.by_id.post_id=42`, the source's typed call carries precisely `{post_id: 42}` but its consumer still awaits `userId`. Absent, wrong-typed, unbounded, extra, unknown-route, or consumer-prebound host arguments are rejected; three owner-declared languages are covered and nothing executes.
8. Call-level data scope: max-hops host scalar must satisfy the *scoped* principal-specific maximum before any typed receipt is returned. A real code review found and reproduced this missing scope validation; the new negative test was red before the fix and green after both scoped-schema and executor data-scope checks were added.
9. Mid-compilation policy shrink: an initially permitted `max_hops=2` is rejected if the authorized limit drops to `1` before the final source proof. No partial typed call, execution or private output is produced.

## Remaining acceptance work (do not mislabel as finished)

- **P2 domain-specific host input semantics:** bounded, validated **original G5 source-root scalars are now supported** via explicit caller arguments, but owner-reviewed semantic value sourcing (including OPTIMADE `get_structures(id)`, complex enum/date domains and numeric unit canonicalization) is **not** yet implemented. No argument values are parsed from language; an explicit separate observed-execution API can now obtain a producer's ID, but only through the existing execution authority and without running leaves.
- **Paper Understand(q):** bounded small-model (intent/concept/parameter/source/tool) contract and explicit host-review/provenance of parameter binding; current P1 uses exact owner-approved aliases only.
- **Paper meta and data:** source-visible field descriptors are metadata *declarations*. Opt-in observed binding and separately authorized consumer execution can now return actual locally registered executor `ToolResult` data, but this is **not** independently authenticated publisher provenance or source-owner canonicalization, nor a complete multi-tool answer/quality assessment.
- **Full E2:** independent dataset, actual data reader, retrieved **data-context** tokens vs schema/input/output tokens, answer/provenance/license correctness, same K5 and same hardware. Source-authored E0 tests are **not** E2.
- **PR gates:** inspect new remote P2 exact-head Actions/CodeQL and review, keep P2 Draft and stacked on #1746 until P1 can safely merge. No production or release promotion.

## Cross-session resume procedure

1. Read this file, the [internal observed-binding implementation plan](paper-observed-binding-implementation-plan-20261024.md), the [consumer execution continuation](paper-consumer-execution-e0-plan.md), the P1 handoff and paper Algorithm 1; inspect issues #1535/#1560, Drafts #1745/#1746 and any P2 Draft; inspect their **current exact head SHAs**. These plans are intentionally outside `docs/**/*.md` so unreviewed internal engineering pages cannot masquerade as part of the independently reviewed bilingual public-documentation corpus.
2. Check working tree, branch and CI results. For test execution use `uv run --offline --no-project --with-editable '.[mcp]' --with 'pytest>=8,<10' --with 'pytest-asyncio>=0.23,<2' --with 'hypothesis>=6.130,<7' --with 'ruff>=0.9,<1' python -m pytest -q` with `UV_CACHE_DIR=/tmp/sr-uv-cache` or equivalent resolved dependencies.
3. Begin next implementation from a **failing test** for source-owner attestations covering actual OPTIMADE host values and canonical physical units, or bounded original-paper `Understand(q)` semantics. The earlier `observe_and_bind_paper_plan` API still only populates consumer `ToolCall` arguments; actual consumer I/O requires the **separate explicit** `observe_and_execute_paper_plan` API and its current authorization, data and one-attempt constraints.
4. Update this handoff after any measured change with local/full test counts, exact remote commit, GitHub workflow conclusions and outstanding gates. Do not close #1346/#1477 or promote #1356 based on E0 alone.

**Local verification checkpoint (2026-10-24):** focused original-paper/native observed binding/consumer execution/native host-root/real-converter/public-API regression **172 passed**; repository-wide Ruff **green**. Independent whole-slice review found two Important defects: source A → leaves B after mutable principal swap, and incorrect denial of valid nested `result_path` consumer outputs. All three added regression scenarios (source/leaf principal mutation, nested output) were **RED before / GREEN after** correction, and the original observed-only receipt gained a separately RED→GREEN principal swap guard. The whole repo local pytest ran with a **240-second cap and timed out at about 12%**, no overall pass claim. Prior GitHub head `7de59e8` had **14/14 successful Actions workflows**; the new consumer-execution head must be checked separately once published. The Korean whole-corpus exact-review-ledger audit remains unchanged: internal plans live in `research/autoresearch/`, with no fabricated translation review. Independent live E2 and #1356 release remain blocked.


## OPTIMADE source-attestation follow-up (E0, 2026-10-24)

- Added an explicit host-review API for one original OPTIMADE entry type. It pins the discovery fingerprint, versioned base URL, source identity, source license, field semantic IDs, source-unit declarations, and host-authored conversion factors. It returns a new single-entry-type ToolSpec without mutating discovery or inferring a conversion from provider unit strings.
- The reviewed GET endpoint has a closed required scalar ID schema. Runtime GET responses must echo the requested entry ID and entry type; a mismatched HTTP 200 is rejected before field projection.
- Paper field planning may select a host-approved, parameterized root only when the complete owner-declared semantic/unit contract is visible. The plan remains non-executable; absent host ID yields requires_arguments. Plan metadata distinguishes source unit from canonical unit.
- This remains E0. It does not authenticate a provider independently, certify licensing beyond the host declaration, establish actual-materials answer quality, or clear independent E2 / release HOLD.
