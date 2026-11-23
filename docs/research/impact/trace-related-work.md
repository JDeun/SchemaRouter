# TRACE vs SchemaRouter — related-work assessment (2026-11-23)

**Public paper:** [TRACE: Business Rule-Grounded Reasoning Curriculum for Knowledge-Preserving Parametric Tool Retrieval in Enterprise LLMs](https://arxiv.org/html/2607.22639v1), Sai Shruthi Sistla, Ashutosh Hathidara et al., SAP Labs, arXiv:2607.22639v1 (22 June 2026).

**Decision:** Include as a **relevant alternative in a future Related Work revision**, subject to available space and the scope of the manuscript. Do **not** describe TRACE as a baseline evaluated by SchemaRouter or as an independent validation of SchemaRouter.

| Axis | TRACE (source paper) | SchemaRouter (current public README and project scope) |
| --- | --- | --- |
| Retrieval representation | Model learns virtual tool tokens in parameters | Explicit typed capability catalog and bounded candidate retrieval |
| Adaptation | Two-stage LoRA/SFT with reasoning traces and expert-rule-generated queries | Schema/adapter registration, runtime constraints, policy and schema checks; no model fine-tuning required by the documented core workflow |
| Enterprise rules | Training-time reasoning and parametric retrieval selection | Runtime source/field, policy, access and execution validation |
| Output | JSON list of tool tokens; greedy single beam | Typed endpoint, parameters, output fields, validated executable plan |
| Change management | Knowledge encoded in trained weights; updates may require refresh (inference, not experimentally established here) | Explicit versioned capability/schema metadata, runtime checks |
| Evidence | Proprietary enterprise 8,283-tool catalog, per-domain retrieval and probing | Separate paper/benchmark settings; metrics cannot be directly compared |

TRACE abstract reports Domain A ~86% and Domain B ~60% retrieval recall under greedy reasoning; embedding baseline ~27%/~52% **R@10**. These are *different retrieval cutoffs*; do not present as a controlled apples-to-apples comparison. TRACE Table 2 reports same-decoder comparisons, and Table 3 reports R@gen for reasoning variants. Expert-rule coverage differs by domain, and Table 3's Domain B result is lower with rules than without them (60.2% vs 67.5%). The paper does not demonstrate that its tool-token output enforces SchemaRouter's runtime field-level access or execution constraints.

**Recommended manuscript placement:** Related Work > Tool retrieval / rule-aware routing. TRACE demonstrates an alternative approach that internalizes domain rules in a parametric tool retriever, whereas SchemaRouter externalizes typed schema and execution constraints. This is a distinction of architecture, **not** evidence that one outperforms the other.

**Suggested English paragraph (adapt to actual manuscript claims):**

> TRACE (Sistla et al., 2026) studies parametric tool retrieval using a two-stage reasoning curriculum and domain-expert business rules, generating tool tokens with greedy decoding. In contrast, SchemaRouter focuses on explicit typed capability descriptions and runtime validation of endpoint, parameter, output-field, and policy constraints. These approaches address overlapping enterprise tool-selection challenges but differ in whether routing knowledge is primarily learned in model parameters or represented in inspectable execution-time contracts. Their reported retrieval metrics are not directly comparable because the catalogs, evaluation settings, and outputs differ.

**Research questions, not claims:** Could TRACE-style rule-targeted query synthesis improve candidate selection for SchemaRouter? Would trained retrieval remain correct under catalog changes and revoked access? Compare under identical catalog, permissions, Top-K, field F1, end-task accuracy, latency, update cost, and policy-violation rates. No integration or experiment has been performed.

**Provenance:** [TRACE arXiv abstract](https://arxiv.org/abs/2607.22639); [TRACE HTML sections 3–4](https://arxiv.org/html/2607.22639v1); [SchemaRouter README](https://github.com/JDeun/SchemaRouter/blob/main/README.md). This document deliberately omits private email details and does not count a related-work suggestion as a citation of SchemaRouter.
