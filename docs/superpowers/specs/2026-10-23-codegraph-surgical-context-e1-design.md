# CodeGraph-style surgical G5 context: executable E1 design

**Date:** 2026-10-23

**Status:** In-chat direction approved; this written design requires maintainer review before an implementation plan.

**Tracking:** [#1711](https://github.com/JDeun/SchemaRouter/issues/1711), M5.

**Dependencies:** [native G5 integration PR #1714](https://github.com/JDeun/SchemaRouter/pull/1714), [nonexecuting surgical E0 PR #1715](https://github.com/JDeun/SchemaRouter/pull/1715).
**Research baseline:** [CodeGraph E0 study](../../research/codegraph-surgical-context-e0.md).

## 1. Intent and decision

The user wants **complete, testable product increments and actual task/cost evidence**, not another round of isolated serialization micro-tuning. The approved direction is to make the existing source-attested G5 **reference-only** context usable by an external research agent via a separately authorized, on-demand original tool-schema disclosure step. The target is to learn whether any saved initial context offsets the extra schema request and model turns, **without creating a new execution authority**.

The E0 finding is strictly 1,028 versus 1,825 UTF-8 JSON bytes (43.67% smaller) on an authorized synthetic two-route complete case; it says nothing about actual tokenizer receipts, task success or money. The frozen #432 task-outcome regression (FULL 49.62%, SR-5 29.19%) still prevents product-default promotion. Independent publisher-disjoint E2 remains blocked at [#1346](https://github.com/JDeun/SchemaRouter/issues/1346), and [#1356](https://github.com/JDeun/SchemaRouter/pull/1356) remains a release HARD HOLD.

### Alternatives

1. **Selected — source-revalidated lazy materialization in the existing E1 research harness.** The model first sees a verified route-reference graph plus one fixed, minimal schema-request action. A trusted host rechecks the source and returns only the requested original, scoped schemas; actual native tool calls still use existing invocation. This measures a real trade-off, including extra round trips.
2. **Reference prompt plus unchanged full tool menu.** Safest to wire but duplicates initial schemas; it cannot demonstrate surgical-context savings. Rejected as the primary experiment.
3. **Tokenizer-only projection.** Cheap and valid as a separately labeled E0 control, but not an executable agent outcome. Insufficient to advance the milestone by itself.

No CodeGraph AST index, graph database, alternate graph ranking, new native provider adapter, general-purpose agent orchestrator or API default is required.

## 2. Responsibilities and boundaries

| Component | Existing boundary | E1 change |
| --- | --- | --- |
| Source/graph selection | `retrieve_authorized_concept_graph`, `NativeSchemaGraphIndex`, `NativeConceptCatalog` | Reuse original route IDs, typed producer→consumer bindings, strict `k=5`, source fingerprints and complete-path disposition; no inferred edge |
| Principal-scoped schema | `capture_authorized_agent_tool_surface` and its guarded `tool_definitions` | Create a **research-only** materialization service that accepts at most selected route IDs and returns current, genuinely visible original definitions |
| Authority continuity | Registry/source witness, policy-content receipt, canonical principal claim snapshot | Verify at selection, materialization, model-response boundary and execution; invalidate materialized definitions on any drift |
| Source execution | `execute_scoped_host_call`, existing registered read-only native adapters | Reuse unmodified invocation checks and projection; no materializer-borne permission |
| Model/measurement | Existing pinned local Qwen agent and paired E1 strict task scorer | Add a separate fourth named arm, record real tokens and intermediate host request costs, preserve actual final-task oracle |

**Non-negotiable trust rule:** a graph route ID, model-supplied route ID, saved reference or successful materialization response is **never** an execution permit. No model-visible or persisted policy secrets, raw source metadata, credentials, hidden fields, unauthorized route counts or private input values. The separate schema-request action may expose only an opaque authorized route reference plus minimal operation description; it cannot enumerate the source registry.

## 3. Proposed E1 protocol

1. At episode entry, pin original source registry/index fingerprints, approved concept catalog, explicit `PrincipalContext`, policy-content digest and original query. The host obtains a complete authorized G5 route-set result using strict `k=5`; statuses other than `complete` result in a **no-call** refusal. A requested path cannot be silently shortened or enlarged to meet K.
2. **FULL** exposes all principal-visible original source definitions; **lexical SR-5** exposes its authorized fixed-5 original definitions; **typed G5** exposes original definitions for a complete authorized G5 path, unchanged. **Surgical G5** instead exposes precisely the same selected path identities, visible original output names, typed bindings, source/version receipts and one small fixed `request_scoped_source_schema` host action. It exposes **zero executable source tools** initially.
3. The model can request materialization for **one or more explicitly selected route IDs**, never a wildcard or global discovery. The host rejects unknown, denied, duplicate, over-K or unselected IDs. Each request independently re-captures a fresh principal-scoped source view and compares selection witness, complete path bindings, route/tool/endpoint fingerprints, data visibility, policy content and principal claims. Failure aborts the episode without source calls. Response contains only freshly generated original tool definitions for the approved requested subset.
4. The experimental agent may subsequently choose only a materialized original route. The existing scoped host invocation revalidates authorization, arguments and the original native source and performs the read-only call; the schema-request action **never** executes a source operation. Materialization is an agent turn and may add more input/output tokens even when successful. Caching may avoid redundant host computations **within an unchanged witness only**, never bypass an authorization recheck or omit its measured context cost.
5. In a multi-operation path, the producer's validated **public** observation and complete typed output→input bindings must remain available for the consumer. A source result cannot be synthesized, copied from another principal or inferred from task gold. An attempted consumer call with missing validated bindings is refused.
6. Finish through the existing strictly source-grounded answer oracle. Same task query, underlying provider, permitted source schema, model ID/revision, decoding settings, K5 routing constraint, principal and per-arm attempt budget. No model rescues, unauthorized retries, automatic source execution or hidden prompt repair is introduced. Rotate arm order to reduce time bias.

The materializer is **research-only** and opt-in; stable `SchemaRouter` APIs and the default agent tool surface remain unchanged. A later product adoption would require a separate threat review and explicit API design.

## 4. Cohorts and source qualification

**Cohort A — actual native two-call correctness:** reuse the documented non-commercial original Open-Meteo geocoding→weather EN/KO/JA cases and pinned Qwen scorer from #1714. This has **only two registered routes**, so it tests materialization, authorization, model call order and strict task completion, **not** a convincing large-menu cost advantage. The research harness respects Open-Meteo's free non-commercial terms; downstream commercial hosts must independently obtain a qualifying provider contract. No credentials enter model-visible context.

**Cohort B — controlled menu-size scaling:** source-register an owner-reviewed, read-only, deterministic multi-route fixture (at least 10 route definitions) with native typed field contracts, real executable host callbacks and fully specified expected outputs. Use the pinned real model for agent turns and actual tool invocations. Label outcomes **E1_LOCAL_SOURCE_CONTROL**, never original remote-provider or independent E2 evidence. Construct supported EN/KO/JA and denied/no-fit/over-K cases with frozen, independently reviewed task/input fixtures. No fake third-party API observations.

The two cohorts remain separately reported; no cross-cohort aggregation or cross-window causal cost claim. Do not expand K, hidden context, attempts or prompt budget to make one arm win. Source drift or an original provider connection failure yields `INCOMPARABLE_SOURCE_DRIFT` / `INCOMPARABLE_SOURCE_FAILURE` with **null success-rate denominators**, while a source-available agent wrong call or premature final remains a real task failure. Missing model runtime is `BLOCKED_MODEL_RUNTIME` (no calls, no fabricated zero results).

## 5. Measured outcomes and reproducibility

For every arm, language and task, record sanitized: source revision/fingerprint and model ID/revision, route-set parity, authorization/refusal disposition, strict task result, model turns, **schema-request calls**, executed native tool calls, original provider HTTP attempts/verified responses, model input tokens, tool-schema tokens, model output tokens, aggregate processed tokens, generated latency/CPU or wall time where measured, and trusted failure-stage enum.

Token receipts must come from the actual pinned model's generation envelope at **every** turn, including generic schema-request definition, materializer responses and subsequent original tool definitions. Incomplete receipts are `null`, not zero. Materialized JSON bytes and tokenizer counts are kept as different measurements. No financial-dollar reduction is asserted without a valid declared price and an actual comparable usage denominator. A higher number of host tool calls is reported honestly, even if initial context shrinks.

Preserve one immutable sanitized run artifact and a version-controlled English/Korean research narrative with source/code/model revisions, cohort limits, workflow run ID, exact commands and negative cases. Do not persist raw provider bodies, person-specific arguments, hidden policy details, credentials, token-bearing URLs or private model context. Historic E0 or #432 evidence remains unchanged.

## 6. Acceptance and rollout gates

1. **Security/functional:** TDD tests prove source identity and policy-content drift, principal substitution, in-place scope narrowing, hidden producer binding, unselected-route requests, denied/no-fit and strict over-K abort before schema disclosure or source invocation. Valid typed two-route cases execute via real registered callbacks and the original scoped invoker with exact final-source parity.
2. **Agent behavior:** actual pinned-model E1 records the fourth surgical condition and compares it with FULL, lexical SR-5 and typed G5 on the same tasks. An unavailable model or original remote source produces a precise inconclusive/blocker artifact; fixtures alone cannot be described as provider-backed task success.
3. **Economics:** report net accumulated actual model tokens, model/tool turns, provider calls and latency rather than inferring benefit from serialized bytes. A loss or negative result is a valid milestone experiment; do not micro-tune to a target.
4. **Compatibility:** explicit research opt-in only, no product default, no new mandatory dependency, no widened route K, no source/schema invention, no general LLM graph authority, no license entitlement. Existing public API, policy and authorization tests must continue passing.
5. **Release:** full GitHub Actions/translation/docs gates before PR review; merge separately approved. #1711 M5 remains open through the E1 verdict, #1346 E2 stays independent and #1356 stays on HOLD.

## 7. Deferred decisions and known risks

- **Materialization overhead may exceed context savings**, especially for only two Open-Meteo routes; this is the hypothesis under test rather than an implementation defect.
- Generic host schema requests could become a route-enumeration oracle. Permit only positively selected, principal-visible route IDs; return the same sanitized refusal for denied, absent, stale or unselected requests.
- Graph and host-scoped source views are distinct reads. Preserve the E0 continuous authority/source witness checks through **both** retrieval and materialization and immediately before every actual provider call.
- Original Open-Meteo availability has historically made earlier nine-episode runs incomparable. Preserve the existing transport taxonomy; do not call source failures model failures or retry until results look favorable.
- A synthetic ten-route fixture proves only local protocol behavior and model interaction, **not** external provider coverage or independent quality. A real wider catalog and publisher-disjoint E2 are future gates, not silent substitutes.

**Maintainer design decision (2026-10-23 conversation):** approved the sequence *reference → revalidated schema request → original scoped tool call → four-arm E1*, with separate native two-route correctness and larger-menu cost cohorts. This document does not itself authorize implementation before its written review and implementation-plan review.
