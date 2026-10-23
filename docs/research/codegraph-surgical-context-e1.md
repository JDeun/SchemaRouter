# CodeGraph-style surgical G5 E1: original-schema execution and evidence

**2026-10-23 · [#1711](https://github.com/JDeun/SchemaRouter/issues/1711) · M5 · research-only opt-in · no default/release change**

## Verdict and honest measurement boundary

**The implementation works on registered local read-only callbacks, but there is no qualified actual-Qwen four-arm cost or quality comparison yet.** E1 adds a bounded, model-selected `research__request_scoped_source_schema` action, then reveals only selected **original** tool definitions after a fresh authorization check. The model separately selects and supplies each original native call. The existing `SchemaRouter` planner, authorization boundary and `RegistryExecutor` remain the only execution route. The adapter neither creates a parallel executor nor makes a model-visible route reference into a grant.

The explicit original Open-Meteo and local-source CPU attempts both returned `BLOCKED_MODEL_RUNTIME` because the pinned local Qwen runtime/weights were not available. No actual model requests or external Open-Meteo HTTP calls occurred in these blocked attempts. Accordingly, both studies report `task_success_rate: null`, `qualified_task_denominator: null`, and no real-model token-saving percentage. **E0 bytes are not model tokens or dollars.** The E0 synthetic UTF-8 serialization difference cannot establish a prompt, throughput, task-success or cost advantage for this E1 path.

## Protocol and authority checks

1. A host captures one `complete` original typed G5 selection with strict `K=5`, its full original field bindings, source/endpoint fingerprints, principal claim receipt, authorization-policy **content** receipt and host-private integrity receipt. An incomplete, denied, stale or `over_k_unranked` result cannot disclose schemas.
2. The initial model menu contains only the fixed research meta-action `research__request_scoped_source_schema`. A reference advertises `tool_call_ready=false`; no original provider call appears before successful model-requested materialization.
3. The model must supply unique selected route IDs; unknown, forged, duplicate, wildcard and over-K IDs fail closed. The host reselects from the original registry and rechecks principal, policy content, producer-visible field bindings and route fingerprints. A schema response is a measured model turn, **not** a provider invocation or an authorization token.
4. Each subsequent model-selected original route must match the complete source path and exclusively trusted host inputs or preceding actual public observations. The existing `execute_scoped_host_call` compiles and verifies the original native plan. Hidden producer fields, principal changes, source changes and unbound consumer arguments abort before another invocation.
5. Every model generation contributes its reported `model_input_tokens`, `tool_schema_tokens`, `model_output_tokens` and latency, including the schema-request round trip. One missing token receipt changes that cohort's total to `null`, never zero. Source HTTP attempts, validated original responses, host-invocation attempts and schema requests are separate counters. Raw arguments, source outputs, private policy and HMAC material are not persisted in experiment reports.

One pre-existing source-boundary caveat surfaced during validation: a provider field literally named `status` conflicts with the existing host's reserved success key `status`. The E1 local control therefore declares the provider result as `case_state` while preserving the same semantic contract `crm.status`. The older E0 fixture and existing host interface were not silently changed; resolving the reserved-name API collision remains a separate compatibility decision.

## Cohort A — original Open-Meteo HTTPS provider

| Attribute | Result |
| --- | --- |
| Source | Original source-bound geocoding → current-weather adapters, fixed public source contracts |
| Cases | Original owner-authored EN/KO/JA task prompts, same principal and source conditions |
| Arms | `all_visible`, `lexical_k5`, `concept_graph_optin`, `surgical_g5_e1` |
| Pinned model | `Qwen/Qwen3-0.6B`, revision `c1899de289a04d12100db370d81485cdf75e47ca` |
| Common budgets | `K=5`, five model turns, zero evidence reprompts and zero transport retries by default |
| 2026-10-23 genuine CPU attempt | `BLOCKED_MODEL_RUNTIME` (pinned model unavailable offline) |
| Success numerator/denominator | `null` / `null`; no valid measured comparison |
| `model_input_tokens` / `tool_schema_tokens` / `model_output_tokens` | `null` / `null` / `null` for blocked run |
| Original HTTP attempts | Zero; no source accessed because the model preflight failed |
| Security/contract tests | MockTransport and scripted-model route order, source failure, forged coordinates and final-value checks passed; **not** live-provider success |

The independent native-source semantics gate remains mandatory. An unattested catalog or source-root contract reports `BLOCKED_SOURCE_SEMANTICS` without opening the provider. Mismatched source receipts or verified weather readings across arms report `INCOMPARABLE_SOURCE_DRIFT`. An actual geocoding/forecast HTTP transport failure reports `INCOMPARABLE_SOURCE_FAILURE`, leaves the denominator `null` and does not count as an agent mistake. A missing model reports `BLOCKED_MODEL_RUNTIME`, not an artificial 0% task-success rate. The original three-arm `compare_graph_native_e1` result schema and default are preserved.

**Open-Meteo commercial-use boundary:** [official free API terms](https://open-meteo.com/en/terms) restrict its free access to **non-commercial** use. [Commercial API access](https://open-meteo.com/en/pricing) is a separate subscription and licence. An open-source SchemaRouter integration does **not** sublicense the Open-Meteo free endpoint for downstream commercial businesses; each operator must establish appropriate provider rights and data attribution. This research flag denotes the non-commercial original source, not a general production/commercial permission.

## Cohort B — actual registered local-source scaling control

This independently labelled control registers **12 separately bound, read-only original tool endpoints**: one two-field `contacts.read` producer, one fully typed `cases.read` consumer and ten unrelated inventory endpoints. The registry, principal, policy and source contract are shared by EN/KO/JA fixtures. The host calls real registered local callbacks via `SchemaRouter.execute`, not hardcoded evaluator answers or remote provider responses. An over-K negative source adds five competing consumers; denied principals and an incomplete two-field producer are also tested.

| Local condition | Result | Measurement claim |
| --- | --- | --- |
| EN/KO/JA joined task, source callback tests | Both real registered callbacks executed in order; strictly source-grounded final checked | Scripted-model **test** only, not actual Qwen quality |
| `lexical_k5` and `concept_graph_optin`, one EN scripted test | Each: two original callbacks, three scripted model turns, 207 fixed-stub input+output tokens | Illustrates plumbing; fixture-defined token envelopes are **not actual model tokens** |
| `surgical_g5_e1`, same EN scripted test | Two callbacks, one schema request, four scripted turns, 276 fixed-stub input+output tokens | Extra model turn costs are included; no savings claim |
| `all_visible` with 12 registered routes | `BLOCKED_MENU_CAP` | Existing principal-scoped disclosure has a hard maximum of five definitions; no batching workaround |
| Four-way scaling comparison | `INCOMPARABLE_FULL_MENU_CAP`; `task_success_rate: null` | A 12-tool FULL denominator and fair comparison do **not** exist under this cap |
| Denied / no-fit / over-K | `BLOCKED_AUTHORIZATION` / `BLOCKED_NO_PROVEN_HIT` / `BLOCKED_OVER_K_UNRANKED` | Zero original source callbacks and no model disclosure |
| Genuine pinned-Qwen local attempt | `BLOCKED_MODEL_RUNTIME`; 12 tool definitions registered | No real-model result, token count or success denominator |

In particular, repeatedly requesting batches of five to simulate a twelve-tool FULL menu would circumvent the existing model-disclosure limit and distort the comparison; this implementation explicitly refuses it. Source registration at scale is verified, but the requested **comparable ≥10-visible-tool cost benefit remains unmeasured**. Cohort B is always `E1_LOCAL_SOURCE_CONTROL`, never original live-provider evidence or independent E2.

## Reproduction and revision receipts

Research implementation commits on the dedicated E1 feature branch:

- `02a7bee`: fail-closed selected original schema materializer.
- `484cbee`: measured model-driven schema request and native scoped call protocol.
- `4a527dd`: named four-arm Open-Meteo comparison, old comparator unchanged.
- `9a0e2b4`: 12-route original registry/callback local control and negative cases.

Exact repository-root commands (use the documented project Python environment):

```bash
python -m pytest -q tests/test_research_codegraph_scoped_materializer.py tests/test_research_codegraph_surgical_agent_e1.py
python -m pytest -q tests/test_research_real_qwen_codegraph_surgical_e1.py tests/test_research_codegraph_local_multiroute_e1.py
python -m scripts.research_real_qwen_open_meteo_two_hop_e1 --compare-surgical --documented-noncommercial-e1 --out /tmp/schemarouter-codegraph-surgical-e1-open-meteo.json
python -m scripts.research_codegraph_local_multiroute_e1 --cohort local-source --language en --out /tmp/schemarouter-codegraph-surgical-e1-local.json
```

The named CPU entry points first perform original source-contract and principal checks, then try only the locally available pinned model in offline mode. They do not download model weights or convert unavailable inference into scripted success. Local test callbacks and Open-Meteo HTTP mocks are synthetic validation infrastructure; they must never be described as genuine original-provider/model outcomes. The sanitized `/tmp` attempt files are local ephemeral evidence, not versioned measured results or proof of external provider availability. Code revision IDs identify implementation checkpoints; exact environment, model and source revision from any future qualified live experiment must be recorded separately.

Related documents: [E0 control](codegraph-surgical-context-e0.md), [E1 design](../superpowers/specs/2026-10-23-codegraph-surgical-context-e1-design.md), [approved A-option implementation plan](../superpowers/plans/2026-10-23-codegraph-surgical-context-e1.md). The work stays research-only; [#1711](https://github.com/JDeun/SchemaRouter/issues/1711) remains open pending actual-model evidence, [#1346](https://github.com/JDeun/SchemaRouter/issues/1346) independent publisher-disjoint E2 remains blocked, and [#1356](https://github.com/JDeun/SchemaRouter/issues/1356) release stays **HARD HOLD**. No automatic issue close, model-default promotion, merge or release is justified by this E1 engineering checkpoint.
