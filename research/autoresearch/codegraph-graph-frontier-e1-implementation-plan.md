# CodeGraph Host-Attested Graph Frontier E1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Measure whether a host-attested, stage-specific original native tool menu reduces Qwen3 model tokens/turns while preserving strict verified two-hop correctness.

**Architecture:** A new opt-in research runner obtains the existing `SurgicalEpisode`, revalidates its authorized G5 path at every frontier, exposes only native root definitions initially, then only verified successor definitions after a real original callback. A fifth experimental arm compares this bundled host-frontier treatment with the four unmodified control arms and the current #1733 prompt cue.

**Tech Stack:** Python 3.12, SchemaRouter native graph/materializer/scoped executor, pytest + pytest-asyncio, Ruff, pinned CPU Qwen3 models in GitHub Actions.

**Spec:** `research/autoresearch/codegraph-graph-frontier-e1-design.md` ([Draft #1734](https://github.com/JDeun/SchemaRouter/pull/1734)). Parent #1723; base #1733.

## Global Constraints

- Research-only, opt-in `graph_frontier_g5_e1`, only `condition="joined"`, `catalog_size=4`, strict `k=5`, five model turns; existing unflagged four-arm output preserved.
- Use only original registered read-only tool definitions/callbacks, `capture_surgical_episode`, `materialize_scoped_original_schemas`, `execute_scoped_host_call` and unchanged `parse_one_model_action` grammar. No model action/route/argument repair.
- Model sees the original query and stage-offered original native definitions, **not** `SurgicalEpisode.public_reference` or a synthetic authority token. Host revalidates that reference before/after generation and before callback.
- Final-answer turn offers `[]`; a late native tool call or reserved schema request is denied. Actual source data and private model text/arguments do not enter research reports.
- Positive endpoint is exact two original source callbacks **and** independently correct final JSON. Compare full per-arm `input+output` model tokens, never double-count the tool-schema subset.
- Same pinned Qwen3-0.6B and Qwen3-1.7B source revisions, GitHub Linux CPU, EN/KO/JA, one original owner-authored local task/language. No independent E2, product default or v0.18 promotion; #432, #1346 and #1356 unchanged.
- Research design/plan/results Markdown belongs in `research/autoresearch/`, not the bilingual `docs/` source tree.

## Review Focus

1. Consumer attempted before a successful producer: never offered, no original callback. Covered in Task 1 tests.
2. Principal/source/catalog/index changed during or after generation: abort before execution; not simply reject a later model argument. Covered in Task 2 tests.
3. Hidden or ambiguous first-hop-to-consumer binding and unexpected argument shape: zero additional callback, no repair. Covered in Task 2 tests.
4. Model generates an extra tool call instead of final after a complete path: no tool offered and no third callback. Covered in Task 2 tests.
5. Negative `denied`, `no_fit`, `over_k`, bad flag pairings and the original unflagged four-arm report: no frontier execution/denominator promotion. Covered in Task 3 tests.

---

### Task 1: Verified frontier state machine and positive TDD

**Files:**
- Create: `scripts/research_codegraph_graph_frontier_e1.py`
- Create: `tests/test_research_codegraph_graph_frontier_e1.py`

**Interfaces:**
- Consumes: `SurgicalEpisode`, `SurgicalHostContext`, `materialize_scoped_original_schemas`, `execute_scoped_host_call`, `parse_one_model_action`, and original scoped argument-validation helpers in `scripts/research_codegraph_surgical_agent_e1.py`.
- Produces: `async def run_graph_frontier_model_episode(agent: Any, *, episode: SurgicalEpisode, host_context: SurgicalHostContext, max_turns: int = 5, diagnose_model_actions: bool = False) -> dict[str, Any]`.
- Produces: pure `_frontier_route_ids(episode: SurgicalEpisode, executed_routes: tuple[str, ...]) -> list[str]` selecting distinct next steps of pinned `route_sets`, preserving original G5 order and never exceeding five.

- [ ] **Step 1: Write failing positive tests**: `test_frontier_initially_offers_only_original_roots`; `test_frontier_offers_only_attested_successors_after_verified_original_callback`; `test_frontier_final_turn_offers_empty_tools_and_validates_real_result`. Use `build_local_multiroute_source(language="ko", catalog_size=4)`, a deterministic scripted `agent.generate`, assert per-turn offered *original* tool names, exact original callback log `['contacts.read', 'cases.read']`, full-task success, schema requests zero and no model-visible `requires_source_schema_materialization` / `route_sets`.
- [ ] **Step 2: Run RED**: `python -m pytest -q tests/test_research_codegraph_graph_frontier_e1.py -k 'initially or attested_successors or final_turn'` — expected import/name or behavioral failure for the missing runner.
- [ ] **Step 3: Implement minimal host-only progression**: stage 0 offers all distinct actual roots; stage 1 offers only successors of the observed first route; complete path offers `[]`. Revalidate source/authorization before generation, after generation, and prior to original callback. Parse one strict model action; require current offered route and exact trusted/observed-bound arguments; deny any repeated, late or unoffered route; execute only through the original read-only scoped host invoker. Return source attempt/count, model turns, all receipt/token counts, `frontier_sizes`, `schema_requests=0`, termination category and strict final correctness.
- [ ] **Step 4: Run GREEN**: same `pytest` command, expected 3 passing positive tests and exact original callback receipts.
- [ ] **Step 5: Commit**: `git add scripts/research_codegraph_graph_frontier_e1.py tests/test_research_codegraph_graph_frontier_e1.py` then `git commit -m "research: add attested Graph Frontier runner and positive controls"`.

### Task 2: Fail-closed adversarial frontier tests

**Files:**
- Modify: `tests/test_research_codegraph_graph_frontier_e1.py`
- Modify: `scripts/research_codegraph_graph_frontier_e1.py` only when a new test first demonstrates a gap.

**Interfaces:**
- Consumes: Task 1's `run_graph_frontier_model_episode` and `_frontier_route_ids`.
- Produces: regression proof that a model-generated wrong native call, changed host authority or missing original public binding cannot cause an unapproved callback.

- [ ] **Step 1: Add focused failing regression tests**: `test_frontier_refuses_consumer_before_root`; `test_frontier_refuses_unauthorized_or_mutating_route`; `test_frontier_rejects_missing_extra_and_nonscalar_arguments`; `test_frontier_fails_closed_on_hidden_producer_binding`; `test_frontier_refuses_changed_source_or_principal_after_generate`; `test_frontier_refuses_reserved_schema_request_and_multicall`; `test_frontier_refuses_repeat_native_after_completed_path`. Assert exact original callback count and fixed-only safe report fields, including no raw tool results or argument values.
- [ ] **Step 2: Run RED**: `python -m pytest -q tests/test_research_codegraph_graph_frontier_e1.py` — at least one intended new adversarial case fails the current implementation, not because the test syntax/environment is invalid.
- [ ] **Step 3: Make narrowly scoped repairs** to the new research runner; never modify existing strict parser, materializer, native registry/authorization, source executor or frozen #432 comparison.
- [ ] **Step 4: Run GREEN**: `python -m pytest -q tests/test_research_codegraph_graph_frontier_e1.py tests/test_research_codegraph_scoped_materializer.py tests/test_research_codegraph_surgical_agent_e1.py` and `ruff check scripts/research_codegraph_graph_frontier_e1.py tests/test_research_codegraph_graph_frontier_e1.py`.
- [ ] **Step 5: Commit**: `git add scripts/research_codegraph_graph_frontier_e1.py tests/test_research_codegraph_graph_frontier_e1.py` then `git commit -m "test(research): fail closed at Graph Frontier boundaries"`.

### Task 3: Comparable fifth arm and pinned model entry points

**Files:**
- Modify: `scripts/research_codegraph_local_multiroute_e1.py`
- Modify: `scripts/research_codegraph_qwen17_local_e1.py`
- Modify: `tests/test_research_codegraph_local_multiroute_e1.py`
- Modify: `tests/test_research_codegraph_qwen17_local_e1.py`

**Interfaces:**
- Consumes: Task 1's `run_graph_frontier_model_episode`.
- Produces: opt-in keyword `experimental_graph_frontier: bool = False` for `run_local_multiroute_codegraph_e1` and Qwen3-1.7B `evaluate_candidate`, plus CLI switch `--experimental-graph-frontier` on Qwen3-0.6B/1.7B runners.

- [ ] **Step 1: Write RED tests**: `test_graph_frontier_adds_exactly_one_fifth_arm_preserving_four_controls`, `test_graph_frontier_requires_joined_four_route_paired_path_order_experiment`, `test_graph_frontier_denies_conflicting_treatments`, `test_graph_frontier_negative_preflight_never_executes_source`, `test_qwen17_frontier_cli_is_optin`. Assert `report["arms"] == (*ARMS, "graph_frontier_g5_e1")`, five outcomes, each denominator 1, identical control source digest and unflagged four-arm report shape unchanged.
- [ ] **Step 2: Run RED**: `python -m pytest -q tests/test_research_codegraph_local_multiroute_e1.py tests/test_research_codegraph_qwen17_local_e1.py -k graph_frontier` — failure due to the missing flag/new arm.
- [ ] **Step 3: Implement the bounded flag integration**: enable frontier only for joined/four-route and the paired #1733 surgical one-action + bare-schema + graph-path-order controls; reject incompatible bare-native-JSON or verified-continuation flag combinations. Instantiate a fresh source/episode and same `SurgicalHostContext`/`_strict_final`; run fifth arm separately, normalize the existing `condition`, `status`, `source_receipt_digest`, `full_task_complete` keys and callback counts. Keep `ARMS` frozen for legacy output and add local `active_arms` only when flag is true; Qwen17 runner expects five outcomes only under flag.
- [ ] **Step 4: Run GREEN**: relevant tests above plus `tests/test_research_real_qwen_codegraph_surgical_e1.py`; `ruff check` the four modified scripts/tests and new runner/test.
- [ ] **Step 5: Commit**: `git add scripts/research_codegraph_local_multiroute_e1.py scripts/research_codegraph_qwen17_local_e1.py tests/test_research_codegraph_local_multiroute_e1.py tests/test_research_codegraph_qwen17_local_e1.py` then `git commit -m "research: integrate five-arm pinned Graph Frontier comparison"`.

### Task 4: Preregister reproducible six-cell Linux E1 and assess results

**Files:**
- Create: `research/autoresearch/codegraph-qwen-graph-frontier-e1.md`
- Create: `.github/workflows/codegraph-graph-frontier-e1-dev.yml`
- Modify: `tests/test_research_codegraph_local_multiroute_e1.py` or workflow smoke test only if needed to assert output schema.

**Interfaces:**
- Consumes: Task 3's flag and five-arm report, both pinned Qwen CLIs.
- Produces: six-run matrix artifacts `(qwen06|qwen17) × (en|ko|ja)` with immutable source/model SHA, original callback evidence and explicit E1-only qualification.

- [ ] **Step 1: Preregister** the exact fixed four-route joined source, `k=5`, five turns, prompts, arms, immutable pinned model revisions and metrics in research Markdown *before inspecting any new model cell*. Include old #1733 1.7B surgical 3/3 at 5,359–5,363 tokens and same-run FULL 2/3 at 2,142–2,151 tokens as historical control, not invented thresholds.
- [ ] **Step 2: Add workflow with schema/preflight checks**: copy only the pinned dependency, CPU headroom, source audit and artifact-validation patterns from `.github/workflows/codegraph-g5-path-order-cue-e1-dev.yml`; execute the new `--experimental-graph-frontier` on both language/model CLIs. Assert five outcomes, exact task denominators, no independent E2/release qualification, frontier `schema_requests=0`, <=2 original calls, bounded `frontier_sizes` and valid null-free model token receipts. No fixed expectation of positive task success.
- [ ] **Step 3: Validate locally**: parse workflow YAML, compile scripts, run relevant pytest, full `ruff check .`, and `git diff --check`; fix only demonstrated failures. The full repository pytest can be slow; run it or report explicitly if not completed, and rely on actual GitHub protected CI for final integration evidence.
- [ ] **Step 4: Commit and publish draft PR #1734 updates** after deterministic tests succeed, preserving prior #1733 evidence and the new preregistration SHA. Let GitHub Linux model jobs run; download/reconcile every six result artifacts before adding a separately marked *post-measurement* summary to the research note and issue #1723.
- [ ] **Step 5: Report honestly**: strict full-task EN/KO/JA success, actual original call receipts, `input+output` token totals versus both #1733 surgical and concurrent FULL, turns and host revalidation overhead. Explicitly distinguish correctness recovery, local end-to-end cost win, inconclusive outcome and independently blocked E2.

## Self-review and execution gate

- Spec coverage: host-scoped root/successor/final semantics Task 1; all prohibited calls/authority drift Task 2; matched controls and negative cohorts Task 3; preregistration and real Linux pinned results Task 4.
- Type consistency: all entry points use `experimental_graph_frontier: bool = False`; one new fifth arm `graph_frontier_g5_e1`, without changing global `ARMS` on default paths.
- Review focus: all five classes above have named regression tests in Tasks 1–3.
- No user or developer approval is implied for release promotion or bypassing E2 gates.

**Execution preference:** direct native sequential implementation, consistent with the user's earlier explicit SchemaRouter workflow preference. Request review of this plan before implementation; this design-approved checkpoint must remain auditable.
