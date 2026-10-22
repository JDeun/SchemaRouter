# G5 source-native concept graph → fixed-K agent outcome vertical slice

**Status:** Maintainer-approved direction, detailed design pending review

**Date:** 2026-10-22

**Primary issues:** [#1535](https://github.com/JDeun/SchemaRouter/issues/1535), [#1560](https://github.com/JDeun/SchemaRouter/issues/1560), [#1477](https://github.com/JDeun/SchemaRouter/issues/1477)

**Safety dependencies:** [#1532](https://github.com/JDeun/SchemaRouter/issues/1532), [#1450](https://github.com/JDeun/SchemaRouter/issues/1450)
**Language / external dependencies:** [#1339](https://github.com/JDeun/SchemaRouter/issues/1339), [#1346](https://github.com/JDeun/SchemaRouter/issues/1346)

## 1. Intent and evidence boundary

The next development increment must deliver **one connected, testable user-facing capability and its real-task evidence**, instead of another series of isolated E0 retrieval, CPU, or prompt tweaks. SchemaRouter discovers registered source-native tools and typed fields for an external agent; it must not become an agent orchestrator, an LLM-generated authority source, or a graph-database project.

The existing default and release state are intentionally unchanged. The frozen #432 task study found SR-5 29.19% success versus FULL 49.62% and diagnostic ORACLE 70.98%; no amount of synthetic Top-K or token improvement reverses that result. Existing public Open-Meteo EN/KO/JA local-Qwen E1 tests exercise real source calls but have often completed only zero or one of three strict tasks; these disclosed cases cannot become an independent E2 holdout. An independently authored, source-permitted publisher/task gold cohort remains blocked under #1346. The v0.18 release PR #1356 is **HARD HOLD**.

User success in this slice means that, for an authorized, registered native source and a host-reviewed declared concept, an external agent receives only bounded **complete source-attested route/field contracts** and can attempt the required real operation sequence. The experiment must tell whether the task truly finished and, when it did not, which stage failed. A negative result is valid and does not trigger automatic micro-tuning.

## 2. Decision and considered alternatives

**Selected: compose existing APIs and graph index behind one opt-in selection surface, then run an end-to-end paired E1 study.** This creates a product-relevant integration increment without modifying stable public defaults. Its cost is that strict independent promotion and parent-issue closure remain gated by #1346.

Alternatives deliberately deferred:

1. **Finish graph/CPU micro-optimizations first.** Easier local throughput, but no evidence the agent can use the graph; #1700 receives no further isolated optimizations without a measured integrated bottleneck.
2. **Build a new agent harness, graph DB, or CodeGraph-style evidence engine.** Duplicates already implemented components and does not directly address frozen task failure. #1711 remains a non-blocking M5 investigation.

## 3. Existing components: reuse, do not rebuild

| Responsibility | Existing module or surface | Treatment |
| --- | --- | --- |
| Trusted concept aliases and conjunctive typed demand | `concept_retrieval.py`: `NativeConceptCatalog`, `resolve_native_concepts`, `retrieve_authorized_concepts` | Reuse source/alias conflict checks; never infer undeclared aliases or fields |
| Single-endpoint complete FieldGroup coverage | `field_group_retrieval.py`: `retrieve_authorized_field_group` | Reuse pre-K scoped typed completeness and native candidate projection |
| Catalog-wide semantic postings and G5 joins | `native_semantic_index.py`, `native_graph_index.py`: `NativeSchemaPostingIndex`, `NativeSchemaGraphIndex.lookup`, `lookup_two_hop` | Reuse source snapshot, producer→consumer typed binding, current authorization and drift checks; initial integration includes **direct + one-hop**, not automatic two-hop chaining |
| Candidate exposure to an agent | `scripts/agent_utility_generated_common.py`: existing `EVAL-FIXED5-OPTIN` / `experimental_candidate_selector`, existing `AuthorizedAgentToolSurface` | Reuse existing callback and model-visible scoped tool definitions; never add a duplicate executor or call permission |
| Source/native real-task verification | Existing `research_real_qwen_open_meteo_two_hop_e1.py`, Open-Meteo host, `FrozenCorpusExecutor`, paired agent metrics | Reuse actual native calls, final factual scorer, source/argument proof and failure classification; disclose E1 separately from simulated fixture replays |

The `NativeSchemaGraphIndex` has route/source fingerprints but is not an authorization capability by itself. A source graph snapshot or candidate reference cannot be passed to a host invoker as permission.

## 4. Proposed first product integration

### 4.1 Interface and responsibility

Extend the existing concept retrieval surface with **one explicitly opt-in composition** (working name `retrieve_authorized_concept_graph`), not a replacement `SchemaRouter` instance or a second lookup engine. Inputs are:

- Existing `SchemaRouter` with an explicit authorization policy and current registered source-native OpenAPI/MCP/OPTIMADE/custom tools;
- original query, explicit `PrincipalContext`, host-reviewed `NativeConceptCatalog` and a `NativeSchemaGraphIndex` built from the **same registry version**;
- strict `k=5` and the existing bounded source/field metadata rules.

The result is a nonexecuting, serializable selection with an explicit disposition, current source fingerprint/snapshot identifier, and either fully specified exposed route sets (including every required source route), or **no exposed routes** on overflow/ambiguity/failed authority. For each selected route set, retain the exact registered route identities, required semantic output fields, complete typed producer→consumer parameter bindings where applicable, and source/endpoint fingerprints. An exposed one-hop path consumes two K slots unless routes are identical and already counted once; K limits **distinct model-visible source routes**, not just number of graph paths.

Disposition vocabulary must clearly separate: `complete`, `no_proven_hit`, `over_k_unranked`, and `budget_unsatisfied`. A missing or conflicting declared concept remains a safe explicit input error, not a calibrated general-purpose semantic `NO_FIT`. Hidden or denied source identities/counts, secret field labels, and private policy evidence must never appear in user/model-visible output. Trusted diagnostics may retain sanitized stage enums, but not raw query text or hidden field counts.

### 4.2 Resolution and selection sequence

1. Validate a **host-supplied** concept catalog and its version/aliases; resolve only original-query mentions. Unknown, overlapping or conflicting concepts fail closed. Compose all required typed semantic fields conjunctively, including type/unit/qualifier/source/license restrictions.
2. Validate graph/registry snapshot identity and principal-scoped policy/availability witness. Only current authorized output fields can satisfy demand. Never use a global graph hit to prove access.
3. Get complete **direct** endpoint candidates through existing `retrieve_authorized_field_group`. Separately, get source-proven **one-hop** root→consumer candidates via `NativeSchemaGraphIndex.lookup` with the same resolved FieldGroup. Do not invent identifier joins or accept unknown source-root input. Parameterized roots require existing explicit host review and complete trusted request inputs.
4. Prefer a complete single-endpoint option when available because it needs fewer independent tool calls; otherwise consider complete one-hop paths. This is a *predeclared conservative policy*, not learned relevance, an oracle, or a proof of task-level superiority. If equally supported choices cannot fit the fixed public budget, return `over_k_unranked` without picking arbitrary alphabetic Top-5 or leaking hidden count. A selected path may contain only fully registered, principal-visible route IDs with complete verified required bindings.
5. Recheck registry fingerprints, live policy/data scope/availability and the original input declaration **after** candidate computation and again when building the external agent's scoped tool menu. Abort on drift. No candidate result triggers `plan`, `execute`, a provider HTTP call, or model invocation.

An alternative direct route is not assumed semantically equivalent to a multi-step path if its required field/operation contract differs; the composer must show the typed reason. A single complete FieldGroup describes *field retrieval*, not necessarily a multi-intent or destructive workflow.

### 4.3 Exposed tool budget and failures

- Both `k` and actual serialized schema/token budgets are recorded and enforced. `k=5` must not silently become K6 for two-step paths.
- The trusted host owns the source bindings, argument values, invocation/approval, and final agent turns. Index, aliases and model output confer **zero** new rights.
- For over-K source-proven alternatives, do not select the first K; an explicit unranked/unsatisfied disposition is preferable until independent ranking evidence exists.
- Do not expose raw input/output schema annotations that reference fields hidden by principal data scope. Where safe projection is unprovable, omit the metadata rather than manufacture an output schema guarantee.
- A source drift, revoked route, untrusted health callback or invalid declaration fails closed. Denied and simply absent sources must not be distinguishable through private route names/counts in model output.

## 5. One integrated acceptance and experimental study

### 5.1 Verification strata (code and existing E0 fixtures)

Use existing tests and add a small number of **integrated, behavior-level tests**, not a separate case for each implementation helper:

1. Two sibling source routes with A only / B only, plus a real A+B candidate: only complete typed FieldGroup wins before strict K.
2. Same-named field with wrong datatype/unit/qualifier, denied route, hidden nested/ref metadata, revoked availability, changed source fingerprint, unsupported query and missing required input: no unsafe exposure or attempted invocation.
3. A host-approved source root plus typed consumer requiring all original output→input bindings: expose both routes and the verified binding; no partial join.
4. Six or more equally proven paths under strict K5: correct no-candidate overflow disposition, including when multiple paths share one root.
5. Declared EN/KO/JA aliases to the same source-reviewed semantic IDs, plus unsupported/ambiguous query controls. No translation model promoted as semantic authority.
6. Version-changed native catalog or principal changing mid-selection: abort consistently and never reuse stale cached permission proof.

### 5.2 End-to-end task and cost measurement

Use an existing real, source-attested, read-only Open-Meteo two-operation cohort for the **first E1 development measurement**. Reuse the installed/pinned actual model, host source, and final-answer checker where available. Use the existing isolated fixed5 evaluation interface to compare **FULL vs lexical SR-5 vs opt-in typed-G5** with the same model, principal, source configuration, query, decoding parameters, strict task final validation and reproducible run identity. Count original provider calls and actual validated arguments. Unavailable model weights, API/network restrictions or changing live source outputs must be recorded as execution blockers, not fabricated results.

For every supported case, report selected complete route set, actual tool-call sequence and arguments, provider success/failure, final answer correctness, model turn count, schema/total input tokens, CPU p50/p95/p99, RSS where measured, plus failure-stage classification. Include supported false refusals and genuine unsupported/forbidden no-call controls; absence of independently authored OOD gold is explicitly stated. Do not optimize thresholds using the same exposed DEV rows and present the result as confirmation.

**Success condition for the first integration PR:** behavior-level tests prove that a complete registered concept/FieldGroup requirement leads to the minimal authorized real native route set (or a safe explicit refusal); a reproducible end-to-end E1 run either completes at least one previously failing task without policy regression **or precisely reports a negative with the observed limiting stage and missing execution prerequisites**. No claim of deployed/default or independent E2 improvement follows automatically.

**Independent gate:** before default enablement, parent issue closure requiring independent evidence, or release action, obtain legitimate source-authorized **publisher/task-author-disjoint** E2 data through #1346, preregister comparisons and success/safety margins, run paired full-task evaluation under #1477, and verify no security regressions. Until then, #1535/#1560/#1477 may have substantial engineering implementation but remain open where their exact E2 exit criteria are unmet.

## 6. Scope exclusions and program sequencing

Out of scope for this first slice: changing `retrieve_authorized` defaults; production learned graph ranking; claiming calibrated cross-provider no-fit; two-hop/three-hop orchestration; credential or approval proxying; new graph DB; new LLM or model-hyperparameter sweeps; reinterpretation of frozen #432; unapproved live destructive source calls; CodeGraph adoption (#1711); and additional G5 dense CPU micro-tuning (#1700) absent a measured integrated bottleneck.

The next slice, if this one exposes an evidence-backed deficiency, expands through #1339/#1403 to multilingual fit/no-fit with separately authored cases. The release gate and v0.18 PR #1356 remain untouched. The already-applied live milestone assignments for #1700→M1 and #1711→M5 should be reconciled with the stale 2026-10-19 milestone manifest **in the same substantive reviewed integration change**, preserving the one-time initialization blob guard and avoiding an independent bookkeeping-only PR.

## 7. Review risks and decision record

| Risk | Response |
| --- | --- |
| Existing concept→FieldGroup and G5 graph utilities have partially overlapping candidate result types | Compose their verified evidence; define a single bounded external result and test parity instead of forking two query engines |
| One-hop path is source-typed but its root requires a city/request argument | Only explicitly host-reviewed roots and concrete trusted request inputs; no execution-ready claim from graph evidence alone |
| Multiple valid alternatives exceed K, reducing recall | Visible `over_k_unranked` negative, not arbitrary selection, hidden backfill or K escalation; record actual agent impact |
| Model's final answer remains wrong after correct routing | Report an agent/final-grounding failure; do not grow a new chat/orchestration subsystem inside SchemaRouter |
| E1 native source is live and the original queries are disclosed | Freeze observable run identity, report drift/transport separately; require independent gold for E2 claims |
| Open P0 hidden-field/authority edge cases | Security acceptance is a precondition to any externally surfaced schema result; incomplete proof blocks public promotion |

**Maintainer decisions already approved (2026-10-22 conversation):** prioritize end-to-end capability and task-outcome evidence over E0 micro-PR throughput; keep CodeGraph M5 non-blocking, preserve release hold, and reuse current graph/agent evaluation infrastructure. **This document requests review of the detailed interface, source-root assumption, strict-K overflow semantics, and E1 acceptance before an implementation plan is authorized.**
