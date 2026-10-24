# Original-paper Algorithm 1 continuation — P2 source-typed ToolCall E0

**2026-10-24 · E0 source-authored diagnostic, not a shipped/default executor.**

## Source of truth, predecessors and gates

- The research objective is the original [SchemaRouter paper §4 Algorithm 1](https://github.com/JDeun/paper_SchemaRouter/blob/main/paper/schemarouter.tex): query understanding, original graph/field selection, explicit `(tool, params, fields, meta)` plan. Source-grounded parity map: [Draft #1745](https://github.com/JDeun/SchemaRouter/pull/1745).
- P1 source-visible required field **AND** before K5: [Draft #1746](https://github.com/JDeun/SchemaRouter/pull/1746), [canonical P1 handoff](paper-field-union-implementation-e0.md), issue [#1535](https://github.com/JDeun/SchemaRouter/issues/1535). Exact GitHub commit `472122bd2d97ed073baaeb7dd576e97c64f6e04b` has **13 successful Actions workflows**, including full CI, CodeQL, and Original Paper Required Field Coverage E0.
- This P2 implementation is scoped to issue [#1560](https://github.com/JDeun/SchemaRouter/issues/1560) on **stacked branch** `feat/1560-paper-toolcall-plan-e0-20261024` based on P1 commit `472122bd2...`. The P2-specific head SHA/PR must be recorded **after remote publication**, not inferred from the branch name.
- The independently source-authored E2 [#1346](https://github.com/JDeun/SchemaRouter/issues/1346) is **BLOCKED_EXTERNAL**; live reader/agent E2 [#1477](https://github.com/JDeun/SchemaRouter/issues/1477) is not completed. v0.18 release [#1356](https://github.com/JDeun/SchemaRouter/pull/1356) remains **HOLD**.

## Implemented bounded P2: `compile_paper_typed_tool_plan`

Entry point: `src/schemarouter/paper_typed_tool_plan.py` (also explicit public exports in `src/schemarouter/__init__.py`). Tests: `tests/test_paper_typed_tool_plan.py`, plus real OpenAPI-producer → host-attested MCP-consumers assertions in `tests/test_native_graph_shared_root_forks.py`, and host-parameterized producer → consumer validation in `tests/test_native_graph_host_root.py`. Focused workflow: `.github/workflows/original-paper-toolcall-plan-e0.yml`.

Input: same **trusted** principal, owner-reviewed `NativeConceptCatalog`, source-native `NativeSchemaGraphIndex` and **exact** K5 as P1. First require `retrieve_paper_field_coverage` to prove a **complete** selected alternative. No tool/field inferred from text or untrusted metadata; no independent ranker/index/agent/LLM call. Then compile *only original source-attested routes* into standard `ToolCall` models:

- `.tool`, `.endpoint`, `.schema_fingerprint`, `.tool_fingerprint` from the original registry/index proof;
- `.fields` from the exact source-visible projection, `.evidence` from standard `available_evidence`, and projected `unit`, `qualifiers`, source/license per original field in `PaperPlanFieldMeta`;
- `.arguments={}` until **validated** host values or observed results are actually available; required inputs listed under `ToolCall.missing_required_arguments`;
- optionally `host_source_arguments={"original.approved_root": {"required_scalar": value}}` to supply an **exact complete** 1–4 scalar input envelope for an **already approved original G5 host source root only**. This reuses `_host_source_input_names` and exact JSON-schema validation, strict primitive types and bounds, and never accepts partial/default/unknown/consumer inputs. Only the source call's missing-input list is cleared; dependent consumer arguments remain deferred. No input values are inferred from the query or retrieved from a provider here;
- for an original record producer and up to four typed consumer branches, explicit `PaperPlanBinding(consumer_call_index, parameter, producer_call_index, producer_field)` with *no synthetic customer IDs*.

`PaperTypedToolPlan` has `status` = `ready` (only the call shape contains no missing required inputs), `requires_arguments`, `requires_observation`, or the source abstention (`no_proven_hit`/`over_k_unranked`/`budget_unsatisfied`). It is **not** `ExecutionPlan`, and sets `executable_authority=False` even for `ready`. Never feed dependent partial calls to the normal executor in one batch: that would be misleading because a producer might execute before a consumer's missing input fails. Actual invocation stays behind the existing per-call executor/authorization/evidence boundaries after runtime observation. No default `retrieve`, `plan`, or `execute` code was modified.

Two checks bound compilation: each route's original fingerprint/read-only/authorization/availability/scope and output projection is checked again, then the **entire** P1 result is recomputed and compared. Original registry/index, principal, catalog, policy digest and retrieval witness must remain the same. Host callback errors during compilation are sanitized to generic `PolicyViolationError` without leaking private exception text. This is **two observations, not a linearizable provider transaction** and not a guarantee against revocation after the returned receipt.

Safety regression expectations:

1. Direct source complete: typed schema/projection/evidence, explicit IDs, no irrelevant fields and no execution.
2. 500-original-route mixed-scope fork: original root ID, one typed deferred consumer per required field, exact parameter/field bindings, no invented arguments; hidden/denied/unlicensed decoys excluded.
3. Missing leaf or unapproved required input: **no partial tool plan**.
4. Wrong K5, invalid alternative, stale original registry, revocation while compiling: fail closed.
5. Converter-native OpenAPI + MCP fixture: cannot publish a fork without the owner-reviewed input/output semantic attestation; EN/KO/JA aliases cover same original field contract.
6. Host-approved required producer input (`post_id`) stays explicitly *missing*, downstream `user_id` remains dependent on observed `userId`. An unapproved host root is `no_proven_hit`; no bound local test invoker is called.
7. When the caller explicitly provides `posts.by_id.post_id=42`, the source's typed call carries precisely `{post_id: 42}` but its consumer still awaits `userId`. Absent, wrong-typed, unbounded, extra, unknown-route, or consumer-prebound host arguments are rejected; three owner-declared languages are covered and nothing executes.

## Remaining acceptance work (do not mislabel as finished)

- **P2 domain-specific host input semantics:** bounded, validated **original G5 source-root scalars are now supported** via explicit caller arguments, but owner-reviewed semantic value sourcing (including OPTIMADE `get_structures(id)`, complex enum/date domains and numeric unit canonicalization) is **not** yet implemented. This receipt intentionally does not parse values from language and does not execute tools to obtain missing values.
- **Paper Understand(q):** bounded small-model (intent/concept/parameter/source/tool) contract and explicit host-review/provenance of parameter binding; current P1 uses exact owner-approved aliases only.
- **Paper meta and data:** source-visible field descriptors are metadata *declarations*, not actual provenance-bearing source records; no executed output/result-side evidence, source-owner canonicalization or independent answer quality.
- **Full E2:** independent dataset, actual data reader, retrieved **data-context** tokens vs schema/input/output tokens, answer/provenance/license correctness, same K5 and same hardware. Source-authored E0 tests are **not** E2.
- **PR gates:** inspect new remote P2 exact-head Actions/CodeQL and review, keep P2 Draft and stacked on #1746 until P1 can safely merge. No production or release promotion.

## Cross-session resume procedure

1. Read this file, the P1 handoff and paper Algorithm 1; inspect issues #1535/#1560, Drafts #1745/#1746 and any P2 Draft; inspect their **current exact head SHAs**.
2. Check working tree, branch and CI results. For test execution use `uv run --offline --no-project --with-editable '.[mcp]' --with 'pytest>=8,<10' --with 'pytest-asyncio>=0.23,<2' --with 'hypothesis>=6.130,<7' --with 'ruff>=0.9,<1' python -m pytest -q` with `UV_CACHE_DIR=/tmp/sr-uv-cache` or equivalent resolved dependencies.
3. Begin next implementation from a **failing test** for source-owner attestations covering actual OPTIMADE host values and canonical physical units, plus actual observation-time consumer binding. The existing optional G5 scalar host parameter support must not be widened into inference or implicit provider execution.
4. Update this handoff after any measured change with local/full test counts, exact remote commit, GitHub workflow conclusions and outstanding gates. Do not close #1346/#1477 or promote #1356 based on E0 alone.

**Local verification checkpoint:** focused original-paper/native-host-root/real-converter/public-API regression passed **127 tests**, and repository-wide Ruff passed. Full-suite verification is still in progress. Claim final totals only when processes finish.
