# Tool-routing OSS landscape and architectural decision wiki

**Reviewed: 2026-10-16 · Maintainer research knowledge base · NOT a product benchmark or endorsement**

This is the **canonical navigation page** for tool discovery, bounded retrieval, semantic fit, no-route decisions, schema disclosure, and authorization. It does **not** replace the historic [prior-art roadmap](prior-art-roadmap.md), [experiment ledger](experiment-index.md), or the evidence in the original files. Read these links **before repeating framework research or opening a new experiment**. The Git-tracked bilingual MkDocs site is the wiki: version review, protected CI, published navigation and reproducible links matter more than a separate unversioned GitHub Wiki.

## Read this first: it was already investigated

**2026-10-23 — CodeGraph surgical-context E0 (#1711):** [bounded prior-art comparison, preregistration and actual paired byte results](codegraph-surgical-context-e0.md). On a source-attested synthetic two-route G5, the reference-only envelope serialized at 1,028 vs 1,825 UTF-8 JSON bytes (43.67% smaller), with identical verified route/binding receipts. No actual agent, tokenizer, cost or task-success evidence; negative cases did not save bytes. This is **nonexecuting E0, not an implementation of CodeGraph or a default change**.

1. **2026-10-15 — actual local open-source-*inspired* routing trials.** [Preregistered protocol](https://github.com/JDeun/SchemaRouter/blob/main/benchmarks/opensource-routing-patterns-dev-20261015.md), [negative CPU results](https://github.com/JDeun/SchemaRouter/blob/main/benchmarks/opensource-routing-patterns-dev-20261015-results.md), and [implementation](https://github.com/JDeun/SchemaRouter/blob/main/scripts/evaluate_opensource_routing_patterns_dev.py). These were **our reimplementations of ideas**, NOT native Aurelio/LlamaIndex software benchmarks. On an already-visible 54 supported + 18 unsupported EN/KO/JA operation-intent DEV corpus:

   | Historical fixed arm | Supported correct | Unsupported falsely accepted | Consequence |
   | --- | ---: | ---: | --- |
   | A1 multilingual exemplar maximum cosine, forced | 30/54 | 18/18 | No no-fit |
   | A2 same, raw score >= 0.65 and margin >= 0.03 | 9/54 | 7/18 | 32/54 supported false refusals |
   | B1 MiniLM Top-3 + multilingual cross-encoder, forced | 33/54 | 18/18 | Candidate Top-3 recall 52/54 but final selection only 33/54 |
   | B2 same with raw cosine cutoff | 1/54 | 0/18 | Catastrophic 53/54 supported false refusals |

   All four arms were **NOT PROMOTABLE**. A modern calibrated confidence model (such as the current Aurelio v1 API below) is a **different, untested** formulation; historical hard-coded raw cosine thresholds must not be presented as its evaluation.

2. **Pydantic AI integration already exists.** [#644 PydanticAI ToolSearch validation](../project/external-validation-pydanticai.md) uses a pinned installed wheel, native PydanticAI ToolSearch integration and a 12/50/100/250-tool *maintainer-owned* catalog. Required tool retained in all four supported synthetic cases and the one unsupported case rejected at each scale; this is **E0, five fixed tasks**, not a broad generalization result. The original evaluation specifically found `score > 0` is *not* an abstention probability.
3. **OpenAI Agents SDK already exists.** [#645 dynamic MCP tool filter evaluation](../project/external-validation-openai-agents.md) preserves downstream SDK approval/guardrails and demonstrates exposure without invocation. It is **integration fidelity, not task completion**.
4. **Real native provider model evidence is contradictory.** [ServiceNow publisher-visible K5 audit](https://github.com/JDeun/SchemaRouter/blob/main/research/autoresearch/servicenow-native-e5-dev.md): lexical **17/20**, E5 **15/20** (EN visible DEV). [Open-Meteo fixed-K5 CPU study](https://github.com/JDeun/SchemaRouter/blob/main/research/autoresearch/open-meteo-native-fixed-k5-semantic-dev.md): lexical **18/27**, E5 **26/27** (EN/KO/JA visible DEV). In Open-Meteo the two approaches disagree on ten tasks (nine rescues, one E5 regression). All **9/9** unsupported Open-Meteo and **4/4** unsupported ServiceNow queries still got nonempty K5 lists. Same-author, already-exposed tasks are not disjoint evaluation. No universal E5 promotion follows.
5. The [historical prior-art research](prior-art-roadmap.md) already tested adaptive decision boundaries, hard-negative OOS, energy/density and conformal gates; many **rejected legitimate requests**. The [0.14 frozen 780-task agent study](large-heldout-agent-utility.md) gave negative generalization, including old KO/JA coverage failures. Later DEV successes do not invalidate frozen historical evidence.

## External frameworks: contract and transfer, not a winner table

| External design | What its documented API actually contributes | What SchemaRouter should / should not do | Local evidence |
| --- | --- | --- | --- |
| [Pydantic AI ToolSearch / Toolsets](https://pydantic.dev/docs/ai/capabilities/tool-search/) and [Toolsets](https://pydantic.dev/docs/ai/tools-toolsets/toolsets/) | Retrieve from deferred tool definitions; compose filtering, lifecycle, approval | **Compose** with the SDK's native deferred/approval boundary; do not replace its invoker or infer authorization from similarity | **Native E0 integration measured**, #644 |
| [LangChain middleware](https://docs.langchain.com/oss/python/langchain/middleware/built-in) / LangGraph | Pre-model selection and dynamic tool exposure can be delegated to middleware/orchestrator | SchemaRouter supplies source-attested typed candidates and validator; never become the general agent loop | LangChain adapter exists; no like-for-like independent tool-selection win established |
| [LlamaIndex RouterRetriever](https://developers.llamaindex.ai/python/framework-api-reference/retrievers/router/) | Select retriever(s) from metadata; tool/object retrieval can be staged before agent decisions | Use as discovery/selection design inspiration, keep route/parameter/output contract separate | **Inspired local variants tested**, *not* native LlamaIndex benchmark |
| [Aurelio Semantic Router v1](https://docs.aurelio.ai/docs/semantic-router/v1/user-guide/features/calibration) | `IndexedRouter` supports dense and optional sparse; `fit` calibrates confidence on separate labeled examples, including `None`; threshold can decline to route | Treat calibrated no-route as a **distinct supervised decision**, not raw positive lexical score or one fixed cosine; still require schema/policy guard | Historical exemplar/RAW-threshold ablations **failed**; **v1 calibrated** method **not tested** here |
| [Claude Tool Search](https://platform.claude.com/docs/en/agents-and-tools/tool-use/tool-search-tool) | BM25/regex discovery and deferred tool-reference expansion | Separate candidate discovery from materializing full schemas; **platform-specific behavior, not a local CPU benchmark** | No direct parity benchmark |
| [Semantic Kernel function choice](https://learn.microsoft.com/en-us/semantic-kernel/frameworks/agent/agent-functions) and [filters](https://learn.microsoft.com/en-us/semantic-kernel/concepts/enterprise-readiness/filters) | Configure function exposure/selection and function invocation filters separately | Model may propose a function; host/policy must validate execution again | Architecture reference only |
| [Haystack](https://docs.haystack.deepset.ai/docs/routers), [RouteLLM](https://github.com/lm-sys/RouteLLM) | Route pipeline branches or **models**, respectively | Do not mistake *model-cost routing* for registered **tool/field selection** | Prior category scan, not direct functional parity |

Links above are **documentation snapshots accessed 2026-10-16**, subject to upstream version drift. Third-party README metrics are *their* self-reported performance, not SchemaRouter evidence. Product implementation always needs an upstream version/revision, API contract, source privilege model and license check before incorporation.

## Decision record for the next integrated pipeline (PROPOSAL, not acceptance)

`query EN/KO/JA → authenticate principal → source-visible eligible catalog → lexical/BM25 + separately opt-in multilingual dense retrieval → source-ID-only fusion under fixed K and schema/token cap → typed operation/input/output-field coverage check → independent no-fit/insufficient/ambiguous decision → disclose bounded schemas → revalidate current source authority, parameters, approval and execution policy → downstream agent task`.

This is **not** permission to ship any new default, ignore hidden fields, increase K to improve recall, or claim no-fit from a nonempty shortlist. Concretely:

- **Retain:** immutable source tool/endpoint fingerprints, RBAC+ABAC+data-scope eligibility before external modeling, typed input/output contracts, fail-closed source identity, independent execution authorization.
- **Investigate only:** lexical plus dense retrieval fusion with **fixed K** and comparable *serialized output schema/token* budgets; the model input's bytes and final exposed tool schemas are **different denominators**. Source group/field/operation fit should gate actionability rather than similarity scores alone.
- **Separate four dispositions:** `candidate_present_unverified`, `verified_supported`, `unsupported_after_calibration`, `insufficient_information_or_ambiguous`. Never call abstention or low similarity a calibrated unsupported answer without a new disjoint labeled calibration set.
- **Reject promotion based on:** hand-picked DEV thresholds, same-author case-gold, comparing unequal widths, mere reduction in context bytes, synthetic language strings, or score-only no-fit. A **real agent** that finishes a task is different from Top-K candidate recall.

## Reuse / terminate / next gate

| Decision | Status on 2026-10-16 | Follow-up rule |
| --- | --- | --- |
| Pydantic AI ToolSearch composition | **Implemented, E0** | Reuse #644, do not rerun the same 5 tasks as a new discovery |
| OpenAI Agents SDK MCP dynamic filtering | **Implemented, E0** | Reuse #645, never claim approvals were replaced |
| Raw cosine/threshold exemplar or generic CrossEncoder no-route classifier | **Previously tested, NOT PROMOTABLE** | Do not hand-tune to already-visible failed rows |
| Pinned real E5 | **Provider-dependent DEV**, no-fit negative | Retain both ServiceNow loss and Open-Meteo win, no global default |
| BM25+dense+source-typed compatibility / calibrated independent no-route | **Architecture candidate only** | One integrated, preregistered experiment, not another unconnected series |
| Independent EN/KO/JA source-authored task + OOD + genuine multi-step agent success | **BLOCKED / NOT DEMONSTRATED** | #1339 and #1346 remain open; no v0.18 #1356 release decision |

**Release gate:** compare lexical, dense, hybrid and hybrid+typed/no-fit on **the same auth-visible genuine native source inventory** with fixed K=5, serialized schema/token budgets, explicit no-call refusals, field validity, language breakdown, 100/250/500 scaling, end-to-end local CPU p50/p95, downstream agent final-task correctness, and independently written *disjoint* provider/task splits. Preserve negative outcomes, preregistration, original provider source hashes, run IDs and wheel provenance. Neither a synthetic no-fit test nor a remembered conversation qualifies.

## Session bootstrap and upkeep

Before **any future external routing-framework study**, do this in order:

1. Read **this page**, [prior-art roadmap](prior-art-roadmap.md), [design/experiment lineage](design-and-experiment-history.md) and the [research status](routing-status.md).
2. Search [prior-art registry](https://github.com/JDeun/SchemaRouter/blob/main/benchmarks/research-prior-art-registry.json), [experiment ledger](https://github.com/JDeun/SchemaRouter/blob/main/benchmarks/research-experiment-ledger.json), [experiment index](experiment-index.md), issues [#200](https://github.com/JDeun/SchemaRouter/issues/200), [#1339](https://github.com/JDeun/SchemaRouter/issues/1339), [#1346](https://github.com/JDeun/SchemaRouter/issues/1346), and [#1450](https://github.com/JDeun/SchemaRouter/issues/1450).
3. For every newly found framework technique append **upstream link + version/commit + date checked + exact claimed boundary + existing local study + support/negative evidence + next falsifiable question**. If upstream changed, do not silently overwrite historical outcomes.
4. Distinguish **official API documentation**, **third-party self-reported results**, **our synthetic E0 controls**, **our author-visible DEV experiments**, **source-verified real CPU experiments**, and **independent disjoint E2 agent evaluation**. Never merge these evidence classes.
5. Prefer **one updated comparison decision** over another isolated paper, PR or script. Change defaults or release gates only after protected CI, source/privacy review, explicit no-fit/agent evidence and a separately tracked decision.

This wiki is intentionally **not** a registry of GitHub stars, popularity ranks, or unsupported “commercial-level” claims. It is a research memory and decision boundary.
