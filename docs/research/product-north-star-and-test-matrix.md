# Product north star, architecture boundaries and unified test matrix

**Canonical engineering alignment · 2026-10-16 · Architectural decision proposal (NOT a released feature or empirical proof).** This is a synthesis of existing [architecture](../architecture.md), [design principles](../concepts/design-principles.md), [product identity](../concepts/schema-router.md), [design lineage](design-and-experiment-history.md), [OSS landscape](tool-routing-landscape.md), [frozen agent evaluation](large-heldout-agent-utility.md), and [external qualification tracker #1346](https://github.com/JDeun/SchemaRouter/issues/1346). It does not supersede frozen preregistration, replace task gold, or make new performance claims.

## 1. Purpose and product boundary

**Purpose:** Connect an AI agent's information/action need to real authorized APIs, tools and data systems by compiling **registered typed capabilities** into a bounded, auditable plan, validating the plan against original schema, local host policy and current execution bindings, then returning validated, minimal and provenance-preserving results.

**Not the product:** a general conversation/agent loop, chat memory/graph/checkpointing, an LLM/model cost router, an embedding ranking leaderboard, a general RAG answer generator, an MCP transport replacement, a credential proxy, or a classifier that confers permission.

**Core promise, expressed as observable outcomes:**
- A legitimate task should retain the **complete required set of operations/fields**, not simply a high-scoring single tool, and the surrounding agent should be able to **finish** the requested task.
- A request that is forbidden, impossible with registered capabilities, underspecified, ambiguous or affected by schema/authority drift must **not trigger an unauthorized invocation**. These states are distinct and need distinguishable responses.
- The small exposed schema/field surface should reduce agent context and total execution cost **without a hidden task-success loss**.
- Different languages (at least EN/KO/JA), registered providers and protocol adapters should preserve this same source-grounded contract. Models aid semantic discovery but never invent source capabilities or permission.
- The surrounding framework owns model conversations, agent loops and checkpoints. SchemaRouter owns typed routing, field/parameter semantics, schema identity and local validated execution; trusted invokers/providers own their transport and factual outputs.

### Non-negotiable invariants

1. **Registered source authority:** no hallucinated tool/endpoint/field, permission, action effect, invoker binding, credential, provider identity or user approval.
2. **Fields before routes when the need is known:** canonical semantic IDs, type, units, qualifiers and provenance govern equivalence; ambiguous field intent may preserve recall, never create execution permission.
3. **Least privilege before discovery and at execution:** RBAC/ABAC, data visibility, availability, side-effect policy and current fingerprints remain authoritative. Retrieval/decision outputs are **untrusted proposals** and must not become host receipts.
4. **Bounded discovery ≠ silent capability removal:** K/call/schema/token budgets are explicit. If needed operations do not fit K, report budget unsatisfied; never claim a two-tool chain was supported by a one-tool success.
5. **No-fit ≠ missing information ≠ forbidden:** no matching capability, a parameter clarification requirement, ambiguous operation and unauthorized request must be distinct internal states; externally disclosed reason must not leak hidden routes.
6. **Frozen research stays frozen:** no DEV-informed post-hoc threshold on original #432 or already-consumed ServiceNow/Open-Meteo tasks, no variable-K results described as strict K5, no metric from synthetic strings described as multilingual competence.
7. **Fail-closed and auditability:** schema drift, stale authorization or incompatible scientific units fail closed; decisions expose observable reason codes and complete tool-call/field/result provenance without chain-of-thought, credentials or hidden catalog leaks.

## 2. Evidence triage: what exists versus what is merely hoped

| Workstream | Current demonstrated state | Claim explicitly NOT supported | Anchor |
| --- | --- | --- | --- |
| Typed registry, adapters, field-first planning, schema validation and policy | Implemented and heavily covered by product contracts | Every external API dialect and dynamic source is fully verified | [Architecture](../architecture.md), [design principles](../concepts/design-principles.md) |
| Framework composition | Pydantic AI ToolSearch and OpenAI Agents SDK dynamic MCP integration E0; LangChain/LangGraph/LlamaIndex adapters | Native third-party *agent* success, replacement of their approvals, external adoption | [ToolSearch validation](../project/external-validation-pydanticai.md), [Agents SDK filter](../project/external-validation-openai-agents.md) |
| Authority/source correctness | Trusted source fingerprints, authorized field contracts, pre-Top-K scoped counts and observable source-swap failure controls introduced in #1466, #1470, #1472 | Atomic isolation from concurrent ABA/in-place authority mutation, independently confirmed real attacker resistance | [#1450](https://github.com/JDeun/SchemaRouter/issues/1450) |
| Open-set/no-fit controls | Opt-in abstention mechanisms and synthetic fail-closed tests exist; historic ADB/density/conformal and fixed raw cosine DEV tests mostly unsuccessful | Calibrated cross-provider no-fit, low false refusal for genuine tasks, universal safe abstention | [Prior-art](prior-art-roadmap.md), [local four-arm negative](https://github.com/JDeun/SchemaRouter/blob/main/benchmarks/opensource-routing-patterns-dev-20261015-results.md) |
| Multilingual discovery | Open-Meteo native DEV E5 K5 26/27 vs lexical 18/27; ServiceNow native EN DEV E5 15/20 vs lexical 17/20. Both DEV and both OOD negative | Uniform EN/KO/JA provider transfer, global E5 default, correct tool input parameters | [OSS landscape](tool-routing-landscape.md), [#1339](https://github.com/JDeun/SchemaRouter/issues/1339) |
| Real agent outcome | Frozen 780-task evaluation: SR-5 29.19%, FULL 49.62%, ORACLE 70.98%; historical KO/JA initial required-route recall 0/160 in cited strata | SR-5 task-level noninferiority, reliable end-to-end output, broad commercial success | [#432](https://github.com/JDeun/SchemaRouter/issues/432), [#1339](https://github.com/JDeun/SchemaRouter/issues/1339) |
| Independent third-party external qualification | Provider source capture/DEV and task intake/preflight infrastructure exists | Independently authored publisher-disjoint gold, signed/approved real agent E2, release readiness | [#1346](https://github.com/JDeun/SchemaRouter/issues/1346), [#1228](https://github.com/JDeun/SchemaRouter/issues/1228) |

**Known causal ambiguity:** The #432 result establishes deployable condition failure, but not that all downstream agent failures were caused by initial retrieval. ORACLE <100% and progressive history recall far above initial recall demonstrate substantial downstream limitations. Do not optimize Recall@5 alone as if it were the objective. The public roadmap and archival prior-art pages include historical “active” claims; this document's as-of date and live GitHub issue state govern current work, never archive timestamps.

## 3. One proposed integrated flow (opt-in until independently qualified)

`Trusted principal and original query
    → registry/source-version snapshot and eligible scoped capability set
    → lexical/BM25 and (explicit opt-in) multilingual dense discovery
    → only source-ID candidate fusion, bounded K and schema/token budgets
    → typed operation / required-input / output-field / unit / effect fit
    → separate disposition: verified-supported | ambiguous | needs-input |
                           unsupported-after-independent-calibration | forbidden
    → disclose only principal-visible bounded source-native schema
    → agent decides valid arguments / possible multi-step sequencing
    → runtime rechecks fingerprints, source/host policies, required args,
      approval, side effects and output schema before trusted invocation
    → validated projected result + provenance → actual agent task evaluation`

This is an **architecture proposal, not a claim that such a classifier, hybrid selector or atomic source snapshot currently exists**. It does not authorize turning on a new default or changing the frozen #432 scorer. When a task needs >K distinct tools, explicit expansion/budget failure must be included in the comparison rather than increasing K in only one experimental arm.

## 4. Unified test inventory — evaluate the whole pipeline

**Priority meanings:** P0 = prerequisite/safety or source correctness; P1 = comparative product-quality blocker; P2 = scale/ecosystem extension. These are not separate requests to create one PR or research script per row. Prefer a **single versioned integrated qualification harness** with multiple strata and one decision record.

| ID / priority | Task/attack stratum and required control | Measure / pass condition |
| --- | --- | --- |
| G01 P0 | Genuine native publisher sources, license/allowed use, pinned bytes + Git blob/endpoint/field fingerprints, wheel installed from commit | Reproduce exact inputs/artifacts; refuse changed source or missing gold |
| G02 P0 | Split by **provider AND task author**, with disjoint train/dev/calibration/confirm; original EN, KO, JA requests (not auto-translations counted independently) | Proof of independence and no leakage before scoring |
| S01 P0 | Viewer/admin/denied principals, field masking, fully hidden routes, forged trusted source fields | Zero unauthorized route/field exposure; no hidden counts leaked |
| S02 P0 | Changed registry/schema/endpoint/protocol signature, revoked policy, lost availability before and after model inference | Fail closed with no stale execution or host receipts |
| S03 P0 | Read/write and destructive sibling tools; forged choice IDs/args, prompt injection in tool descriptions, approval denied, internal policy mutation/concurrent ABA | Zero observed unauthorized calls; uncovered concurrency explicitly tracked #1450 |
| R01 P1 | English query→English catalog, KO/JA→English catalog, reverse translation direction and multilingual identifiers | Required-**tool-set** Recall@K, complete-set coverage and language-specific misses |
| R02 P1 | Same-source sibling operations: read vs list vs update vs delete, search vs detail, confusing output labels | Native **operation correctness**, no unsafe sibling substitution |
| R03 P1 | Fields with same name but different datatype, units, qualifiers, semantic IDs, required request params | Required-input coverage, required-output-field and unit/qualifier validity **separately** |
| R04 P1 | Unsupported near-domain requests, truly OOD, missing capability, forbidden-but-similar tool | Unsupported false acceptance, denied-call count, proper no-call behavior |
| R05 P1 | Missing required parameter, ambiguous referent, multi-intent request and contradictory constraints | False refusal on supported vs accurate `needs-input`/`ambiguous` disposition |
| R06 P1 | Separate calibration corpus and locked independent confirmation for no-fit and task-fit model | Joint supported false refusal / unsupported false accept with preregistered operating point, **not** raw similarity threshold |
| A01 P1 | One-step exact and wrong-sibling operations, proper typed arguments | Final task pass, function + args correctness, error classification |
| A02 P1 | Two-/three-step state-dependent chains, ID propagation, real sequential execution in controlled sandbox | Completed state transition and correct final answer; no credit for candidate-only recall |
| A03 P1 | Recoverable failure, provider fallback, tool retry, progressive retrieval | Correct recovery without hindsight/oracle/gold routing; additional calls and side-effects tracked |
| A04 P1 | Factual and numerical responses: field values, units, provenance, hidden output scopes | Factual final answer, units, provenance and policy compliance |
| E01 P1 | FULL vs lexical SR-5 vs dense SR-5 vs hybrid fixed SR-5 vs typed+no-fit pipeline vs diagnostic ORACLE | **Paired task-level success deltas and CI**; same agent/task/source/cost budgets; ORACLE not runtime option |
| E02 P1 | Strict public **K=5**, source tool input/output schema bytes vs model-input bytes vs actual token count, 100/250/500 catalog sizes | Actual exposed tools/fields, schema/total tokens, p50/p95/p99 warm CPU routing and E2E wall time, RSS |
| I01 P2 | Native Pydantic AI, OpenAI Agents, LangChain/LangGraph/LlamaIndex and representative MCP/OpenAPI adapters | Exposure/approval/guardrail/execution parity; do not rerun existing #644/#645 five-case controls as a new win |
| I02 P2 | Catalog changes, 1,000 tools, hot registration/unregistration, index cache invalidation, concurrent principals | Indexed/exhaustive parity and absence of cross-principal leakage; scale bottlenecks isolated |

**Mandatory matrix dimensions:** at least native EN/KO/JA originals; public tool descriptions primarily in other languages; supported/OOD/near-OOD/ambiguous/missing-input/forbidden; tools and fields; read vs mutation; 1/2/3+ required calls; 100/250/500 endpoints with 1,000 retrieval-only stress if feasible. Not every cross-product cell needs a new task: preregister representativeness and independence, and report missing cells.

## 5. Evaluation and promotion contract

- **Primary:** paired semantic-*task* final completion, reported per language and task stratum; use stable identical agent, fixed frozen prompts, actual controlled tool execution, source/host policy. The 780-task #432 gate required a task-clustered 95% CI lower bound at least **-2 pp versus FULL**, ≥97% required-tool-set retrieval, ≤40% of FULL tool-schema tokens, total input tokens below FULL and zero unauthorized destructive executions. This was **NOT passed**. Do not rewrite the old threshold after outcomes. New integrated study must explicitly preregister its target margin, paired population and precision *before* scoring; cite the old gate as historical, not an automatically passing criterion.
- **Secondaries:** full required tool set; native operation; input parameters; output fields and units; supported false refusals / unsupported false accepts; context bytes **and** tokenizer-counted schema + total tokens; warm/cold CPU p50/p95/p99, RSS, cache; provider/model calls; final factuality and provenance.
- **Baselines:** source-scoped deterministic lexical, real pinned dense, constant-K hybrid, typed fit + separately calibrated disposition; FULL and diagnostic ORACLE for agent analysis. Baselines must see the **same authorization-visible source routes** and use the **same exposed K/schema/token constraints** in comparable shortlists. Report budget violations explicitly.
- **No promotion on a win in visible DEV:** immutable split gold/source permissions, frozen pre-scoring conditions, independent case authorship, held-out paired agent traces, negative rows, regression CI and separate approval are needed before production default or a release-gate change.
- **Safety first:** any privacy/unauthorized-execution regression vetoes promotion; do not treat OOD rejection by refusing every supported task as success. Host approval/permission cannot originate from model similarity.

## 6. Sequence and stop/reuse rules

**Milestone 0 — consolidate (now):** read this document, [prior-art](prior-art-roadmap.md), [OSS wiki](tool-routing-landscape.md), and live issues #200/#1339/#1346/#1450; make one current state ledger. Stop repeating four already-rejected 2026-10-15 cosine/reranking DEV arms, already-tested Pydantic ToolSearch integration, and same-author Open-Meteo/ServiceNow DEV as “new evidence.”

**Milestone 1 — establish independent qualification cases (critical dependency):** obtain permissible source-native examples plus a different author/reviewer for accurate required operation, fields, permissions and unsupported labels. Freeze splits, original source fingerprints, model versions, metrics and acceptable error budgets **before** new runs. If unavailable, explicitly record **BLOCKED_EXTERNAL** rather than minting artificial independence.

**Milestone 2 — one integrated opt-in prototype (not multiple loose scripts):** implement the proposed staged source-visible lexical/dense→fixed-K→typed-fit→disposition path behind a separate experimental surface. Write the G/S/R focused tests and hard safety gates; retain normal stable default unchanged.

**Milestone 3 — one paired experiment and one decision:** run G/S/R/A/E strata together. Analyze failure taxonomy **retrieval miss vs wrong operation vs missing parameter/field vs unsafe/failed execution vs agent reasoning/final answer**. Include ServiceNow loss and Open-Meteo win as historical context only. Do not chase a better DEV aggregate.

**Milestone 4 — qualify or reject:** promote only if independent, task-level, safe, measured under actual CPU budget; otherwise mark which stage failed and stop, without silently raising K or lowering acceptance thresholds. Release #1356 remains HARD HOLD; #1339/#1346/#1450 remain open until their actual independent evidence and authority conditions are satisfied.

**Definition of progress:** one previously failing **real task** now completes correctly, with exact source/field/permission proof and no new unsafe or unsupported calls. A new script, PR count, model leaderboard or synthetic pass is supporting infrastructure, **not the product success criterion**.

## 7. Qualification checklist and proof gates

The [generated qualification checklist](../project/qualification-control.md) is the **current per-ID evidence status** for this unchanged 19-row canonical inventory. Update its source JSON at `benchmarks/qualification-control-v1.json`; the script and Actions validate exact matrix coverage and prevent unreviewed E0/DEV-only promotion. The v0.18 release gate (#1345/#1346) is distinct from independent integrated E2/default promotion (#1477).
