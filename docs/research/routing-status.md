# Routing research status

This page is the **current-state summary**, not the complete experiment log.

For the full research record:

- [Complete experiment index](experiment-index.md) — all **69** machine-readable experiment records;
- [Design and experiment history](design-and-experiment-history.md) — architectural chronology and decisions;
- [0.11 terminal report](operation-routing-v4-terminal-report.md) — the closed-cycle decision;
- [Prior-art roadmap](prior-art-roadmap.md) — cross-session literature/work-item map and experiment-order guardrail;
- [machine-readable prior-art registry](https://github.com/JDeun/SchemaRouter/blob/main/benchmarks/research-prior-art-registry.json) — session bootstrap and canonical workstream state;
- [machine-readable ledger](https://github.com/JDeun/SchemaRouter/blob/main/benchmarks/research-experiment-ledger.json) — exact provenance index.


SchemaRouter publishes routing research evidence separately from the stable library contract.

This page is intentionally conservative: development-set success is not presented as production
validation, and consumed fresh-confirmation corpora are never reused for tuning.

## Standing operation-routing target

The current research target for the multilingual open-set operation-routing work is:

| Metric | Target |
| --- | ---: |
| Supported exact route | >= 85% |
| Near-domain unsupported rejection | >= 97% |
| Ordinary OOD rejection | 100% |
| False-route rate | <= 1% |
| Authority / execution errors | 0 |
| Executable p95 | <= 250 ms |

The canonical v4 development corpus contains 1,800 cases. Its SHA-256 is
`fc085c58ed7c667d71024e60cf9e213e66da8f7b43f6e79551ed810a9e328216`.

## What has actually been demonstrated

The strongest executable development candidate in the closed 0.11 architecture-search cycle
(#324/#325) reached:

| Evidence | Exact | Near reject | OOD | False-route | p95 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Canonical DEV | 85.07% | 99.31% | 100% | 0.62% | 176.94 ms |
| Frozen zero-overlap fresh confirmation | 84.81% | 90.45% | 100% | 8.49% | 278.37 ms |

The second row is decisive. The unchanged candidate failed independent request-surface shift, so it
was **not promoted**. Calibration and blind-final evidence were intentionally left unconsumed.

The closed cycle therefore does **not** claim that SchemaRouter has validated the 85/97/100/1 +
250 ms production target under independent surface shift.

## What the experiments indicate

The frozen BGE-M3 registered-route ranker reaches about **88.45% raw top-1** on canonical DEV. Late
experiments therefore suggest that closed-set ranking is no longer the main blocker.

The harder problem is open-set **capability membership**:

> A request can be topically close to a registered domain while asking for an operation that no
> registered endpoint actually supports.

Embedding similarity, route margins, generic NLI, learned DEV geometry, rerankers, several
Jev/System-One model paths, ColBERT evidence, registry alias envelopes and model-consensus variants
were all insufficient to establish the full independent target.

## Conservative reference

The #259 BGE-M3 reference profile remains useful for safety-oriented comparison:

- supported exact: **83.77%**;
- near-domain unsupported rejection: **98.96%**;
- false-route: **0.93%**;
- planner p95: approximately **134.95 ms**.

It is not a production-target pass because supported exact routing remains below 85%.

## First registry-compiled capability prototype

Experiment #338 tested a provider-neutral registry-compiled capability verifier after the closed
architecture-search cycle.

The infrastructure objective succeeded: the same compiler accepted native `ToolSpec`, OpenAPI and
MCP registrations, preserved typed field/unit metadata, kept raw BGE route authority unchanged and
introduced no authority or execution errors.

The learned synthetic veto, however, was far too conservative:

| Surface | Exact | Near reject | OOD | False-route | Correct raw-winner retention | p95 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Canonical DEV (1,800) | **5.03%** | **100%** | **100%** | **0%** | **5.69%** | **196.93 ms** |
| Registration holdout (228) | **2.08%** | **100%** | **100%** | **0%** | **2.46%** | **192.85 ms** |

The registration holdout contained previously unseen native/OpenAPI/MCP tool identities, opaque
endpoint names, empty operation aliases and variable endpoint counts.

This candidate is therefore **terminally rejected** under its preregistered stopping rule. It may not
be repaired using canonical/holdout labels.

The useful result is architectural rather than a promoted quality method: provider-neutral typed
capability/data-contract compilation remains aligned with SchemaRouter's product model, while this
particular synthetic learned veto does not.

Run: `36393153612`  
Source: `ef75100abc1bb03a80ef2d7cfbd9d463accfb623`  
Artifact: `10957952613`  
Digest: `sha256:2a24d50c563ee872fdad8d498e30ab7a55e6c82e0650bf27ac4bfbadc4fc4269`

## 0.12 query-first typed-frame screen

The first 0.12 successor experiment (#347) changed the representation rather than adding another
endpoint-similarity threshold. It parsed a registry-independent explicit request frame, used frozen
BGE-M3 only to anchor the tool/domain, and then filtered that tool's endpoints by trusted typed
contract contradictions before one bounded ranking decision.

A new 936-case DEV corpus and a separate 1,008-case registration confirmation corpus were generated
and frozen before any scoring. The confirmation surface remains **unscored** because DEV failed.

DEV result:

| Metric | Result |
| --- | ---: |
| Supported exact | **97.22%** |
| Raw supported tool accuracy | **99.54%** |
| Near-domain unsupported rejection | **70.37%** |
| OOD rejection | **95.83%** |
| False-route | **25.99%** |
| p95 | **179.53 ms** |
| Authority / execution errors | **0 / 0** |

The result shows that typed query-side filtering can preserve supported routing and runtime very
well, but a high-precision lexical frame does not cover enough natural-language operation intent to
solve open-set membership. This exact candidate is terminal and is not repaired from DEV rows.

The next successor hypothesis must add a materially broader **query-side semantic operation signal**
without turning endpoint similarity back into capability authority.

## 0.12 semantic ontology screens

Two follow-up experiments tested whether a generic operation ontology could provide that broader
signal without route-specific retraining.

| Experiment | Supported exact | Near reject | OOD | False-route | Raw exact | Raw tool | p95 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| #349 flat semantic action ontology | **44.91%** | **56.48%** | **100%** | **32.64%** | 77.31% | 94.44% | 197.55 ms |
| #354 hierarchical capability ontology | **30.42%** | **68.65%** | **88.89%** | **26.85%** | **85.42%** | **100%** | 164.33 ms |

Both candidates were terminally rejected on their newly frozen DEV surfaces; neither confirmation
corpus was opened.

The strongest architectural lesson comes from #354: the raw BGE ranker already met the supported
exact target and selected the correct tool for every supported DEV request, but hard semantic
ontology filtering destroyed that good signal. The ontology is therefore useful as a structured
representation of registered capability semantics, **not as a noisy positive selector with endpoint
removal authority**.

## 0.12 asymmetric ontology veto

Experiment #358 preserved the raw BGE-M3 top-1 as the sole positive selector and allowed ontology
evidence only to veto to `NO_ROUTE`. It never filtered to another endpoint and never reranked a
positive route.

DEV result:

| Metric | Result |
| --- | ---: |
| Supported exact | **96.05%** |
| Raw supported exact | **96.05%** |
| Raw supported tool accuracy | **99.56%** |
| Raw-correct winners vetoed | **0 / 0%** |
| Near-domain unsupported rejection | **26.59%** |
| OOD rejection | **84.72%** |
| False-route | **60.49%** |
| Veto precision | **99.22%** |
| Veto recall | **39.51%** |
| p95 | **236.02 ms** |
| Authority / execution errors | **0 / 0** |

This is a useful authority result but not a quality pass. Negative-only ontology evidence can preserve
supported routing when it is not allowed to choose another endpoint, but requiring exact same-leaf
agreement across independent signals is far too conservative to provide enough unsupported recall.

The exact #358 rule is terminal. Its frozen confirmation corpus remains **unscored**.

## 0.12 capability-set membership consensus

Experiment #363 relaxed #358's exact unsupported-leaf agreement into a finite-set membership question:
each independent signal only had to agree that the requested capability lay outside the anchored
tool's registered capability set. Raw BGE-M3 remained the sole positive selector; ontology evidence
could only return `NO_ROUTE`.

DEV result:

| Metric | Result |
| --- | ---: |
| Supported exact | **86.40%** |
| Raw supported exact | **94.30%** |
| Raw supported tool accuracy | **99.56%** |
| Near-domain unsupported rejection | **54.76%** |
| OOD rejection | **97.22%** |
| False-route | **35.80%** |
| Veto precision | **91.23%** |
| Veto recall | **64.20%** |
| Raw-correct winners vetoed | **18 / 8.37%** |
| p95 | **249.73 ms** |
| Positive route switches / authority / execution errors | **0 / 0 / 0** |

Set-level consensus materially improved recall over #358 (39.51% -> 64.20%), but still missed the
97% near-domain target and began rejecting correct supported winners. This closes further rule
tuning over the same BGE/MiniLM ontology-projection evidence family on consumed DEV.

The exact #363 rule is terminal. Its separately frozen 552-case confirmation corpus remains
**unscored**. A successor must introduce a materially different semantic membership signal rather
than another threshold or agreement variant over the same projections.


## 0.12 external multilingual zero-shot membership

Experiment #371 replaced the BGE/MiniLM ontology-vote family with an independently pretrained
multilingual zero-shot classifier while keeping frozen BGE-M3 as the sole positive route selector.
For the BGE-anchored tool, registered operation leaves plus one generic
`outside registered capabilities` label were presented as a finite multiclass label set. The
external classifier could only preserve the raw winner or veto to `NO_ROUTE`.

The model was resolved before scoring to immutable revision
`d8c48cf2e7c7640ad5bbb379bdb2f72f5ebde7c4`.

DEV result:

| Metric | Result |
| --- | ---: |
| Supported exact | **93.42%** |
| Raw supported exact | **93.86%** |
| Raw supported tool accuracy | **99.12%** |
| Near-domain unsupported rejection | **1.59%** |
| OOD rejection | **2.78%** |
| False-route | **98.15%** |
| Veto precision | **85.71%** |
| Veto recall | **1.85%** |
| Raw-correct winners vetoed | **1 / 0.47%** |
| External classifier p95 | **93.15 ms** |
| End-to-end p95 | **274.52 ms** |
| Positive route switches / authority / execution errors | **0 / 0 / 0** |

The architecture remained authority-safe, but the generic OUTSIDE catch-all almost never won
multiclass normalization against concrete supported capability labels. The exact formulation is
terminal and its separately frozen confirmation corpus remains **unscored**.

The next candidate must condition the actual registered capability set directly in the membership
question instead of asking one generic OUTSIDE label to compete with concrete positive labels.


## 0.12 set-conditioned binary entailment

Experiment #374 replaced #371's generic OUTSIDE-label competition with one direct NLI pair whose
hypothesis explicitly enumerated the anchored tool's registered capability descriptions. Frozen
BGE-M3 remained the sole positive selector; the NLI model could only preserve that route or veto to
`NO_ROUTE`.

DEV result:

| Metric | Result |
| --- | ---: |
| Supported exact | **0%** |
| Raw supported exact | **92.54%** |
| Raw supported tool accuracy | **99.56%** |
| Near-domain unsupported rejection | **100%** |
| OOD rejection | **100%** |
| False-route | **0%** |
| Entailment / not-entailment decisions | **0 / 552** |
| Raw-correct winners vetoed | **211 / 100%** |
| NLI p95 | **56.16 ms** |
| End-to-end p95 | **254.55 ms** |
| Positive route switches / authority / execution errors | **0 / 0 / 0** |

The single disjunctive hypothesis collapsed to `not_entailment` for every DEV request, including
all supported requests. The exact formulation is terminal, and its separately frozen confirmation
corpus remains **unscored**.

This establishes that finite capability-set membership should not be encoded as one long
set-membership sentence for this NLI model. A successor must use a different contrastive
representation rather than repairing the consumed hypothesis wording.


## 0.12 independent per-capability entailment

Experiment #377 decomposed the membership question into one independent NLI judgment for each
registered capability leaf under the BGE-anchored tool. All judgments for one query were evaluated
in one batch. Frozen BGE-M3 remained the sole positive route selector; NLI could only preserve that
winner or veto to `NO_ROUTE`.

DEV result:

| Metric | Result |
| --- | ---: |
| Supported exact | **45.61%** |
| Raw supported exact | **96.49%** |
| Raw supported tool accuracy | **100%** |
| Near-domain unsupported rejection | **71.03%** |
| OOD rejection | **95.83%** |
| False-route | **23.46%** |
| Veto precision | **66.85%** |
| Veto recall | **76.54%** |
| Raw-correct winners vetoed | **116 / 52.73%** |
| NLI batch p95 | **79.53 ms** |
| End-to-end p95 | **278.09 ms** |
| Positive route switches / authority / execution errors | **0 / 0 / 0** |

Per-capability decomposition was more informative than one aggregate set hypothesis, but binary
argmax still over-vetoed supported requests: more than half of raw-correct winners were rejected.
The exact #377 formulation is terminal and its frozen confirmation corpus remains **unscored**.

The next preregistered experiment (#378) compares the strongest supported-leaf entailment with the
strongest counterfactual-leaf entailment, without adding thresholds or positive reranking.


## 0.12 pairwise supported-vs-counterfactual NLI

Experiment #378 compared the strongest independent NLI entailment among the BGE-anchored tool's
registered capability leaves with the strongest counterfactual tool/non-tool leaf. Counterfactual
evidence could only veto to `NO_ROUTE`; frozen BGE-M3 remained the sole positive selector.

DEV result:

| Metric | Result |
| --- | ---: |
| Supported exact | **67.54%** |
| Raw supported exact | **95.18%** |
| Raw supported tool accuracy | **98.25%** |
| Near-domain unsupported rejection | **55.95%** |
| OOD rejection | **95.83%** |
| False-route | **35.19%** |
| Veto precision | **75.54%** |
| Veto recall | **64.81%** |
| Raw-correct winners vetoed | **63 / 29.03%** |
| NLI batch p95 | **387.87 ms** |
| End-to-end p95 | **539.92 ms** |
| Positive route switches / authority / execution errors | **0 / 0 / 0** |

The exact formulation is terminal and its frozen confirmation corpus remains **unscored**. Together
with #371, #374 and #377, this closes the current Horizon NLI semantic-decomposition family.

Research has moved to #382/#383: schema-derived open-set decision boundaries following the
ADB, hard-negative OOS and energy-based OOD literature.

## Reproducibility

The closed-cycle machine-readable decision is stored at
`benchmarks/operation-routing-v4-terminal-decision.json`.

The full evidence ledger is stored at
`benchmarks/research-experiment-ledger.json`.

The complete design/experiment narrative is stored at
`docs/research/design-and-experiment-history.md`.

The terminal report is available at
[Operation routing v4 terminal report](operation-routing-v4-terminal-report.md).


## 0.13 schema-derived open-set membership sequence

The 0.13 cycle isolates **positive route retrieval** from **open-set capability membership**.
Frozen BGE-M3 remains the sole source of positive endpoint authority. Every 0.13 verifier is
veto-only: it may preserve the raw registered top-1 route or return `NO_ROUTE`, but may never
rerank to another endpoint, use rank-2 fallback, or invent a pseudo-route.

Standing production-oriented gates for this sequence are:

| Metric | Gate |
| --- | ---: |
| Supported exact route accuracy | >= **85%** |
| Near-domain unsupported rejection | >= **97%** |
| OOD rejection | **100%** |
| False-route rate | <= **1%** |
| Query p95 | <= **250 ms** |
| Authority violations / route switches / execution errors | **0 / 0 / 0** |

### V6A — schema-derived spherical ADB (#384)

Positive-only schema-derived spherical regions catastrophically failed to transfer from synthetic
schema surfaces to natural user requests. Raw BGE supported exact remained **91.67%**, but the gate
rejected every supported DEV request and all **209** raw-correct winners. Near-domain and OOD
rejection were both 100% only because every query lay outside every learned region.

**Decision:** terminal. Confirmation remains unopened.

### V6B — hard-negative ellipsoid (#395)

V6B added same-resource unsupported-operation negatives from the registered capability complement
and a low-rank anisotropic ellipsoid. The synthetic evidence separated as intended, but the
synthetic-to-natural surface shift remained: every DEV query still fell outside the boundaries.

| Metric | Result |
| --- | ---: |
| Raw supported exact | **97.37%** |
| Raw supported tool accuracy | **97.81%** |
| Gated supported exact | **0%** |
| Near-domain / OOD rejection | **100% / 100%** |
| Raw-correct winners vetoed | **222 / 100%** |
| p95 | **139.91 ms** |

**Decision:** terminal. The complement-negative evidence remains reusable; the ellipsoid
formulation does not. Confirmation remains unopened.

### V6C — tied-Gaussian density ratio (#397)

Replacing absolute inclusion with a relative positive-vs-complement density score eliminated
catastrophic supported vetoes.

| Metric | Result |
| --- | ---: |
| Supported exact | **93.86%** |
| Raw supported tool accuracy | **100%** |
| Near-domain rejection | **39.29%** |
| OOD rejection | **56.94%** |
| False-route | **56.79%** |
| Raw-correct winner veto | **0%** |
| p95 | **152.15 ms** |

The result established that relative evidence is safer for supported traffic, but one Gaussian per
class collapses multimodal operation structure.

**Decision:** terminal. Confirmation remains unopened.

### V6D — component Gaussian-mixture density ratio (#399)

V6D preserved endpoint-level positive components and complement resource×operation components with
one tied diagonal covariance and a fixed zero log-likelihood-ratio boundary.

| Metric | Result |
| --- | ---: |
| Supported exact | **89.91%** |
| Raw supported tool accuracy | **95.61%** |
| Near-domain rejection | **39.68%** |
| OOD rejection | **5.56%** |
| False-route | **67.90%** |
| Veto precision / recall | **96.30% / 32.10%** |
| Raw-correct winner veto | **0%** |
| p95 | **250.49 ms** |

Component structure preserved supported winners but did not fix the core synthetic-to-natural
membership problem. Natural unsupported/OOD queries were often still more likely under the
registered mixture than under the synthetic complement mixture.

**Decision:** terminal; PR #400 closed without merge. Confirmation remains unopened.

### V6E — non-parametric kNN membership (#401)

V6E removed Gaussian assumptions entirely. For the BGE-anchored tool it compared fixed k=3 cosine
neighborhood distances to three immutable evidence banks: schema positives, same-resource
complement negatives, and the pre-existing #279 16-anchor generic background bank.

| Metric | Result |
| --- | ---: |
| Supported exact | **83.33%** |
| Raw supported exact | **84.21%** |
| Raw supported tool accuracy | **94.30%** |
| Near-domain rejection | **60.71%** |
| OOD rejection | **54.17%** |
| False-route | **40.74%** |
| Veto precision / recall | **95.05% / 59.26%** |
| Raw-correct winner veto | **1.04%** |
| Background / complement vetoes | **6 / 196** |
| p95 | **176.50 ms** |

This is the strongest unsupported recall of the V6C–V6E density/local-geometry sequence while
remaining inside the latency target, but it still misses every open-set quality gate and slightly
damages supported routing. The complement bank supplies most useful veto signal; the generic
background bank is too sparse to cover natural OOD. Positive and complement neighborhoods still
overlap substantially in natural-language embedding space.

**Decision:** terminal; PR #402 closed without merge. Confirmation remains unopened.

### Current 0.13 conclusion

V6A–V6E rule out a progressively broader family of straightforward schema-synthetic geometry:

- absolute spherical and ellipsoidal boundaries fail by synthetic-to-natural radius shift;
- tied single- and multi-component Gaussian density ratios preserve supported traffic but
  under-reject unsupported traffic;
- threshold-free local kNN improves recall but still cannot separate the overlapping natural
  positive/complement manifolds;
- generic background anchors are insufficient as a natural OOD support model.

Therefore the next experiment must introduce a **materially different semantic representation or
membership signal**. It must not be a post-hoc sweep over V6E k, distance thresholds, margins,
neighbor weights, background anchors, or schema/complement wording. All V6A–V6E confirmation
surfaces remain unopened.


## 0.13 post-V6E evidence

The first 0.13 open-set sequence is now terminal with **no active frozen child experiment**.

| Experiment | Tested signal | Supported exact | Near reject | OOD | False-route | p95 | Result |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| #404 | naturalistic MiniLM scope + 18-way operation probes | **75.44%** | **59.52%** | **95.83%** | **32.41%** | **297.36 ms** | terminal |
| #406 | Tool-Embed-0.6B positive selector | **78.07%** | — | — | — | **287.42 ms** | terminal; BGE 86.84% on same surface |
| #408 | multilingual relative cross-encoder membership | **79.39%** | **19.84%** | **59.72%** | **71.30%** | **2992.17 ms** | terminal |
| #409 | frozen GTE multilingual positive selector | **71.49%** | — | — | — | **100.14 ms** | terminal; BGE 88.16% on same surface |
| #412 | multilingual-E5 + fixed alpha=0.01 split conformal | **10.09%** | **99.21%** | **100%** | **0.62%** | **244.24 ms** | terminal |

The key contrast is #412: it is the first method in this sequence to satisfy near-domain rejection,
OOD rejection, false-route, authority and runtime gates simultaneously, but it vetoed **158 of 181**
raw-correct BGE winners. The safety calibration worked; the underlying scalar catalog-membership
score did not separate supported traffic strongly enough.

The retained research conclusion is therefore:

> The unresolved bottleneck is a **surface-invariant executable-capability membership
> representation**, not another threshold or calibration rule over a weak score.

No terminal DEV rows may be used to tune a successor, and all confirmation surfaces above remain
unopened. The canonical continuation point is issue **#388**, then issue **#382**, the
machine-readable prior-art registry, and the experiment ledger.

## 0.14 — typed capability retrieval as agent infrastructure

The active research question moved in #417/#418 from **authoritative single-route
classification** to **end-to-end agent utility**.

This is an architectural reframing, not a deletion of the 0.13 evidence. The terminal 0.13 sequence
showed that forcing one retrieval layer to simultaneously identify one exact endpoint and provide
executor-grade open-set abstention creates a severe coverage/safety trade-off. In the most explicit
case, #412 reached 99.21% near-domain rejection, 100% OOD rejection and 0.62% false-route while
collapsing supported exact routing to 10.09%.

The default 0.14 role is therefore:

```text
OpenAPI / MCP / ToolSpec
        ↓
typed capability compiler / registry
        ↓
SchemaRouter Top-K capability retrieval
        ↓
LLM agent chooses among finite registered candidates
        ↓
schema / argument / permission / destructive-action validation
        ↓
tool execution
        ↓
result evaluation
        ↓
optional corrective candidate expansion
```

SchemaRouter remains responsible for finite registry-backed capability exposure, ranking, typed
metadata, provenance and execution constraints. The downstream agent is responsible for final
selection among the exposed candidates. Irreversible actions remain protected by execution policy;
retrieval confidence is not execution authority.

Primary 0.14 measurements are now:
- required-capability Recall@K / MRR / NDCG;
- downstream deterministic task pass rate;
- valid tool and argument construction;
- tool-schema and total context tokens;
- end-to-end latency, LLM/tool-call counts and cost where observable;
- recovery under progressive retrieval;
- destructive-action policy integrity.

Top-1 exact remains a useful diagnostic but is no longer the sole product objective.

### #418 Phase A

A frozen 23-task benchmark (17 single-tool, 6 multi-tool) was evaluated at 20, 50, 100 and 250
registered endpoints. Before any Phase-B agent inference, two multi-tool output contracts and two
missing task inputs were corrected so every frozen task is actually executable. The corrected
pre-B1 freeze is workflow `36507439562`, artifact `11006614997`, digest
`sha256:5cec1c650bd2a98fc78f7fbb911c0b15d95a39c96a43848b939ba56302658022`.

Corrected Phase-A retrieval coverage is invariant across all four catalog sizes:

| Metric | Result |
| --- | ---: |
| Top-1 required-route recall | **68.97%** |
| Top-3 required-route recall | **96.55%** |
| Top-5 required-route recall | **100%** |
| Top-10 required-route recall | **100%** |
| Top-3 all-required task coverage | **95.65%** |
| Top-5 all-required task coverage | **100%** |
| Top-5 multi-tool coverage | **100%** |
| Required-route MRR | **0.82471** |

At 250 endpoints, Top-5 exposes on average only **2.379%** of the FULL serialized schema context
while retaining every required capability in this benchmark. This is the first direct evidence for
the intended “typed table of contents” role: compact candidate retrieval can be strong even when
single-label Top-1 is not.

### #420 Phase B1

#420 is a reproducibility/sanity baseline using the causal `Qwen/Qwen3-0.6B` model only as the
**downstream tool-using agent**. It is not a revival of #289, which terminally rejected the distinct
`Qwen/Qwen3-Reranker-0.6B` checkpoint as a yes/no capability verifier.

No Qwen score participates in SchemaRouter retrieval in #420. The agent sees lexicographically
ordered candidate sets with no rank scores/positions. A stronger Phase-B2 agent is required before
making a product-level generalization.
