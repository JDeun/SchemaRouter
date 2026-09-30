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
| Energy/density/open-space scoring | #390 / #397 / #399 / #401 | **terminal / no active successor** | V6C/V6D/V6E terminal; do not retune consumed geometry |
| Selective/conformal abstention | #391 / #412 | **terminal tested formulation** | E5 conformal safety passed open-set gates but destroyed supported recall |
| Tool/executable-schema retrieval / agent utility | #392 / #417 / #418 / #420 | **active primary direction** | Phase A/B1 are terminal; B2 strong-agent replication is terminal success; #431 is the active gate before #432/#424 |

Active research parent: **#417**. Historical 0.13 prior-art parent: **#388**.

## 0. Active 0.14 research question: typed capability retrieval for agents

The 0.11–0.13 open-set work is retained as evidence, but it is no longer the primary product
objective. Those cycles repeatedly showed that asking one retrieval layer to provide both positive
route selection and executor-grade abstention creates a severe safety/coverage trade-off.

The active 0.14 architecture is:

```text
registered executable schemas
        ↓
typed capability index
        ↓
high-recall Top-K retrieval
        ↓
downstream LLM agent
        ↓
execution validation / policy
        ↓
tool execution
        ↓
result evaluation and optional candidate expansion
```

Relevant current work:
- #417 — active research parent;
- #418 — FULL vs Top-K vs progressive utility protocol, terminal;
- #420 — B1 local downstream-agent A/B, terminal;
- #423 — stronger-agent B2 replication, terminal success;
- #431 — active execution-state-aware corrective retrieval;
- #432 — gated 780-task held-out generalization benchmark;
- #424 — gated final-answer factual-quality benchmark.

Phase A already establishes the retrieval-side premise on the corrected frozen benchmark:
- Recall@1 **68.97%**;
- Recall@3 **96.55%**;
- Recall@5 / Recall@10 **100% / 100%**;
- at 250 endpoints, Top-5 exposes only **2.38%** of FULL serialized schema context on average.

The corresponding evaluation hierarchy is therefore:
1. **Recall@K / required-tool-set coverage** — did retrieval preserve what the agent needs?
2. **downstream deterministic task success** — can the same agent complete the task?
3. **context/token/latency/cost** — is the candidate reduction operationally useful?
4. **recovery** — can progressive expansion repair an initial miss without hidden ground truth?
5. **execution safety** — can policy prevent unauthorized destructive actions regardless of rank?
6. **final-answer quality** — does context reduction preserve factual completeness, units and provenance?

Top-1 exact remains diagnostic. It is not treated as a proxy for all six outcomes.

Independent literature supporting this framing includes:
- ToolRet, Findings ACL 2025;
- ToolReAGt, KnowLLM 2025;
- GRETEL, arXiv 2025, for execution-grounded retrieval/selection feedback.

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
- **#401 / V6E — terminal non-parametric local membership.** Fixed k=3 cosine-neighborhood comparison reached supported exact **83.33%**, near rejection **60.71%**, OOD rejection **54.17%**, false-route **40.74%**, and p95 **176.50 ms**. Complement neighborhoods were informative but positive/complement manifolds still overlapped; confirmation remains unopened.

V6C showed that relative evidence can preserve supported routes but one Gaussian per class collapses multimodal structure. V6D showed that preserving endpoint-level Gaussian modes still does not solve the synthetic-to-natural membership gap. V6E removed the Gaussian assumption and improved unsupported recall, but remained far below the rejection targets and slightly damaged supported routing. The next experiment therefore must change the semantic signal or representation itself rather than tuning another distance threshold, neighborhood size, or Gaussian parameter from consumed DEV.

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


## Post-V6E terminal sequence

The next preregistered screens changed the semantic evidence source rather than tuning V6E geometry.

| Experiment | Role | Supported exact | Near reject | OOD | False-route | p95 | Decision |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| #404 naturalistic MiniLM probes | veto-only membership | **75.44%** | **59.52%** | **95.83%** | **32.41%** | **297.36 ms** | terminal |
| #406 Tool-Embed-0.6B | positive selector | **78.07%** | — | — | — | **287.42 ms** | terminal; same-surface BGE 86.84% |
| #408 mMARCO cross-encoder | veto-only membership | **79.39%** | **19.84%** | **59.72%** | **71.30%** | **2992.17 ms** | terminal |
| #409 GTE multilingual | positive selector | **71.49%** | — | — | — | **100.14 ms** | terminal; same-surface BGE 88.16% |
| #412 E5 split conformal | veto-only membership | **10.09%** | **99.21%** | **100%** | **0.62%** | **244.24 ms** | terminal |

All associated confirmation surfaces remain unopened.

The aggregate result is more informative than any one failure:

- BGE-M3 remains the strongest tested positive-route reference, but its fresh supported exact rate is surface-sensitive.
- Replacing BGE with a tool-specialized or general multilingual retriever did not generalize.
- Naturalistic generic-operation learning improves broad OOD recognition but does not establish same-domain capability membership.
- Joint relevance cross-encoding does not make counterfactual capability documents a reliable open-set boundary and is too slow on CPU.
- Conservative conformal calibration can satisfy the <=1% false-route target, but not when the underlying scalar membership score overlaps heavily between supported and unsupported requests.

**There is currently no active frozen 0.13 child experiment.** The next experiment must introduce a materially new membership representation or decision structure. It must not be a post-hoc change to V6A-E geometry, #404 training bank/probes, #408 candidate texts/thresholds, #409 GTE weights/fusion, or #412 alpha/E0/model.

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

The current order is now governed by #417/#500:

1. B1 and B2 are terminal and preserved as frozen evidence;
2. complete #431 without changing its frozen task/state/model/scoring semantics;
3. freeze the #432 held-out condition manifest from the preregistered boolean gates;
4. execute #432, then #424 only through the gated conveyor.

The older pre-terminal 0.14 launch plan is superseded by this gated conveyor. Historical
run/protocol provenance remains in Git history, the experiment ledger, and terminal issue comments.

Maintain #392 as the prior-art bridge between executable-schema retrieval and the active 0.14
agent-utility work. Revisit open-set/conformal methods only for a newly preregistered question, never
as a post-hoc repair of consumed DEV.

Historical 0.13 order was:

1. retain **#384 / V6A** as the terminal positive-only spherical ADB reference; its confirmation stays unopened;
2. retain **#395 / V6B** as the terminal hard-negative ellipsoid reference; its confirmation stays unopened;
3. retain **#397 / V6C** and **#399 / V6D** as terminal relative-density controls; both confirmations stay unopened;
4. retain **#401 / V6E** as the terminal non-parametric local-neighborhood reference; its confirmation stays unopened;
5. retain **#404**, **#406**, **#408**, **#409**, and **#412** as terminal post-V6E controls; all confirmations stay unopened;
6. before opening a successor, search prior art and repository history for a materially different membership representation or decision structure;
7. revisit selective/conformal safety from **#391** only after a substantially more discriminative semantic membership score exists;
8. continuously maintain tool-retrieval architectural alignment in **#392** without giving retrieval models execution authority.

This order is not a claim that later methods are superior. It is the governance sequence that avoids
mixing hypotheses and reusing evidence.


## 0.14 staged successors after the fixed-K baseline

These are staged before any accepted B1 aggregate and must not be derived from B1 row-level failures.

- **#428 — public typed Top-K API:** expose retrieval as a first-class composition surface while
  leaving final agent choice and execution authority outside the retriever.
- **#430 — adaptive shortlist depth:** test preregistered per-query K after fixed K=3/5/10 evidence.
  Repantis et al. (arXiv:2605.24660) independently motivates shortlist depth as a first-class
  variable.
- **#431 — execution-state-aware corrective re-retrieval:** compare static widening with retrieval
  conditioned on bounded typed observations/current state. DTDR (Findings ACL 2026) is the main
  external reference.
- **#432 — large independent held-out surface:** required because B1 has only 23 unique semantic
  tasks repeated across catalog sizes.

### Statistical scope correction before B1 aggregate

B1's four catalog-size rows per semantic task are repeated measures, not independent samples.
Therefore the canonical paired bootstrap resamples **task_id clusters**, keeping the four
catalog-size deltas together. The -2pp gate remains a descriptive engineering threshold in B1.
A population-level non-inferiority/generalization claim requires #432 with an independently frozen,
materially larger task population and preregistered precision/sample-size analysis.


### B1 v2 canonical execution status

The accepted B1 path is now v2:
- frozen task SHA: `bc0b78ff2be11b89e6ac54ea0ee336f944f04b3c203fc61da70a46ff48b4e03c`;
- canonical workflow: `36529108855`;
- canonical source: `b9eadefd3cd076f026a54bbc55a949f0424f5dab`;
- exact runtime pins: Python 3.12.14, torch 2.14.0+cpu, transformers 4.57.6,
  tokenizers 0.22.2, safetensors 0.8.0;
- 30 frozen inference jobs aggregate into exactly 552 unique episodes.

Before any accepted aggregate, B1 v2 corrected hidden user-argument requirements and enforces a
tool-observation causality barrier: only one tool call may execute per assistant turn and dependent
calls require the previous observation.

The v2 preflight re-ran Phase A and retained Recall@3 **96.55%**, Recall@5/@10 **100%**, and
mean Top-5 schema context **2.383% of FULL** at 250 endpoints.

Paired uncertainty uses task-cluster bootstrap because catalog sizes are repeated measures of the
same 23 semantic tasks. This prevents pseudoreplication but does not make B1 a population-level
non-inferiority study; #432 remains mandatory for that claim.
