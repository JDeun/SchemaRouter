# Prior-art roadmap for open-set capability routing

This page is the human-readable companion to
[`benchmarks/research-prior-art-registry.json`](https://github.com/JDeun/SchemaRouter/blob/main/benchmarks/research-prior-art-registry.json)
and GitHub issue **#388**.

Its purpose is continuity: a new research session should be able to reconstruct what literature has
already been checked, which SchemaRouter hypotheses it motivated, which experiments are terminal,
and what should be tried next without relying on chat memory.

## Session bootstrap

Before creating a new routing experiment:

1. read issue **#388**;
2. read `benchmarks/research-prior-art-registry.json`;
3. read `benchmarks/research-experiment-ledger.json`;
4. read [Routing research status](routing-status.md);
5. search existing issues and `research/*` branches;
6. resume the first active canonical experiment instead of creating a duplicate.

## Current workstream map

| Workstream | Work item | State | Current SchemaRouter use |
| --- | ---: | --- | --- |
| Adaptive/open decision boundaries | #384 | **terminal** | V6A positive-only spherical ADB rejected every DEV request |
| Hard-negative OOS generation | #389 / #395 | **terminal** | V6B separated synthetic evidence but rejected every natural DEV query |
| Energy/density/open-space scoring | #390 / #397 / #399 / #401 | **active** | V6C/V6D terminal; V6E non-parametric kNN membership active |
| Selective/conformal abstention | #391 | deferred | Calibrate abstention only after a useful semantic membership score exists |
| Tool/executable-schema retrieval | #392 | ongoing | Keep retrieval research aligned with the typed capability architecture |

Parent roadmap: **#388**.

## 1. Adaptive Decision Boundary

Primary reference:

- Hanlei Zhang, Hua Xu, Ting-En Lin, *Deep Open Intent Classification with Adaptive Decision
  Boundary*, AAAI 2021.
- paper: https://ojs.aaai.org/index.php/AAAI/article/view/17690
- code: https://github.com/thuiar/Adaptive-Decision-Boundary

Transferable idea:

- known classes can be represented by learned feature regions;
- unknown/open inputs are rejected when they fall outside class-specific boundaries;
- the decision boundary can be learned without requiring labeled open examples.

SchemaRouter difference:

- intents are not a fixed human-labeled taxonomy;
- capabilities appear dynamically from OpenAPI/MCP/ToolSpec registration;
- therefore positive evidence must be compiled from schema at registration time;
- route authority must remain registry-backed and must not be invented by the boundary model.

Terminal canonical experiment:

- **#384**
- branch: `research/0.13-schema-adb-baseline`
- protocol: V6A
- raw BGE supported exact: **91.67%**
- ADB supported exact: **0%**
- near-domain / OOD rejection: **100% / 100%**
- all **209** raw-correct supported winners were vetoed;
- all 552 DEV queries fell outside every spherical boundary;
- confirmation remains unopened.

The positive-only spherical formulation is terminal. It must not be repaired by rescaling the radius or rewriting the positive views from failed DEV evidence.

Duplicate/superseded research artifacts are explicitly recorded in the machine-readable registry.

## 2. Hard-negative OOS

Primary references:

- Zhijian Li, Stefan Larson, Kevin Leach, *Generating Hard-Negative Out-of-Scope Data with
  ChatGPT for Intent Classification*, LREC-COLING 2024:
  https://aclanthology.org/2024.lrec-main.674/
- Hossam Zawbaa et al., *Improved Out-of-Scope Intent Classification with Dual Encoding and
  Threshold-based Re-Classification*, LREC-COLING 2024:
  https://aclanthology.org/2024.lrec-main.763/

The relevant result is not merely “use synthetic data.” It is that **near-domain OOS inputs are the
hard case**, because they share vocabulary and domain features with supported classes while asking
for unsupported behavior.

SchemaRouter adaptation:

```text
registered tool capabilities
    retrieve
    update
        ↓
generic capability complement
    delete
    cancel
    refund
    export
    translate
    ...
        ↓
schema-derived resource anchor
        ↓
hard-negative OOS examples
```

The generator must remain registry-independent. It must not use benchmark route names or failed DEV
rows to write special negatives.

Work item: **#389**. The concrete experiment **#395 / V6B** is terminal. It combined registry-derived same-resource hard negatives with a low-rank anisotropic ellipsoid boundary while keeping raw BGE-M3 as the only positive route authority.

V6B DEV preserved perfect unsupported rejection but rejected **all supported requests** after every natural query fell outside the learned ellipsoids. Raw BGE supported exact remained **97.37%**. Its confirmation remains unopened. The hard-negative evidence bank remains reusable as schema-derived supervision; the exact ellipsoid formulation does not.

## 3. Energy, density, and open-space scoring

Work item: **#390**.

The question is whether membership can be represented as a scalar or density-like property of the
registered capability space instead of a semantic `OUTSIDE` class.

This family includes comparisons such as:

- energy-style OOD scores;
- prototype/centroid distances;
- class-conditional density;
- Gaussian-mixture style membership;
- open-space risk;
- spherical or ellipsoidal class regions.

It is deliberately separated from positive route selection:

```text
BGE registered-route retrieval
        ↓
raw positive winner
        ↓
open-space membership score
        ├─ inside  -> preserve raw winner
        └─ outside -> NO_ROUTE
```

Earlier threshold/embedding families remain terminal in the experiment ledger and must not be
silently recycled.

Current 0.13 sequence:

- **#397 / V6C — terminal tied-Gaussian density ratio.** Supported exact **93.86%**, near rejection **39.29%**, OOD rejection **56.94%**, false-route **56.79%**, zero raw-correct vetoes.
- **#399 / V6D — terminal component Gaussian-mixture ratio.** Supported exact **89.91%**, near rejection **39.68%**, OOD rejection **5.56%**, false-route **67.90%**, zero raw-correct vetoes, p95 **250.49 ms**.
- **#401 / V6E — active non-parametric local membership.** Fixed k=3 cosine-neighborhood comparison over the unchanged schema-positive bank, unchanged same-resource complement bank, and the pre-existing #279 16-anchor background bank. No threshold, margin, weighting, k sweep, or DEV-selected calibration.

V6C showed that relative evidence can preserve supported routes but one Gaussian per class collapses multimodal structure. V6D showed that simply preserving endpoint-level Gaussian modes still does not solve the synthetic-to-natural membership gap. V6E therefore removes the parametric Gaussian assumption rather than tuning V6D from consumed DEV rows.

## 4. Selective prediction and conformal abstention

Work item: **#391**.

References currently tracked:

- *Conformal Predictive Systems Under Covariate Shift*:
  https://proceedings.mlr.press/v230/jonkers24a.html
- *Not all distributional shifts are equal: Fine-grained robust conformal inference*:
  https://proceedings.mlr.press/v235/ai24a.html

For SchemaRouter, conformal/selective prediction is a **safety layer**, not the semantic detector
itself.

It should be tested only after a membership score already has a credible precision/recall profile.
The protected #198 calibration/blind surfaces must not be consumed merely to rescue a weak detector.

## 5. Tool retrieval and executable-schema retrieval

Work item: **#392**.

Primary references:

- *Retrieval Models Aren't Tool-Savvy: Benchmarking Tool Retrieval for Large Language Models
  (ToolRet)*, Findings ACL 2025:
  https://aclanthology.org/2025.findings-acl.1258/
- *ToolReAGt: Tool Retrieval for LLM-based Complex Task Solution via Retrieval Augmented
  Generation*, KnowLLM 2025:
  https://aclanthology.org/2025.knowllm-1.7/

SchemaRouter's closest RAG analogy remains:

| RAG | SchemaRouter |
| --- | --- |
| PDF / HTML | OpenAPI / MCP / Python Tool |
| parser | source adapter |
| chunk | Tool / Endpoint / Field |
| metadata | schemas, datatype, unit, qualifiers, read/write/destructive |
| index | registry + capability representation |
| retriever | registered-route retrieval |
| relevant text chunk | executable endpoint |
| generator / agent | downstream application, outside SchemaRouter |

This literature informs retrieval architecture and benchmarks. It does **not** justify moving task
decomposition, ReAct loops, or autonomous agent behavior into SchemaRouter.

## Research invariants

The following rules apply across all workstreams:

- only registered schema-backed endpoints have positive execution authority;
- open-set evidence may preserve a route or abstain, never create a route;
- no rank-2 fallback or pseudo-route;
- no per-route retraining for newly registered APIs;
- datatype, `semantic_id`, optional units, normalization, dimension and qualifiers remain first-class
  capability/data-contract facts;
- failed experiments remain terminal unless a new experiment materially changes the method;
- no consumed DEV/fresh/confirmation row may be used to patch a terminal method;
- new experiments must identify the prior-art work item they instantiate.

## Execution order

The current order is:

1. retain **#384 / V6A** as the terminal positive-only spherical ADB reference; its confirmation stays unopened;
2. retain **#395 / V6B** as the terminal hard-negative ellipsoid reference; its confirmation stays unopened;
3. retain **#397 / V6C** and **#399 / V6D** as terminal relative-density controls; both confirmations stay unopened;
4. execute **#401 / V6E**, the preregistered non-parametric kNN membership experiment from **#390**, without using V6D failed rows to tune k, evidence, thresholds, or decision order;
5. if a useful semantic membership score exists, evaluate selective/conformal safety from **#391**;
6. continuously maintain ToolRet/ToolReAGt architectural alignment in **#392**.

This order is not a claim that later methods are superior. It is the governance sequence that avoids
mixing hypotheses and reusing evidence.
