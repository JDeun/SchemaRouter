# Routing research status

This page is the **current-state summary**, not the complete experiment log.

For the full research record:

- [Complete experiment index](experiment-index.md) — all **67** machine-readable experiment records;
- [Design and experiment history](design-and-experiment-history.md) — architectural chronology and decisions;
- [0.11 terminal report](operation-routing-v4-terminal-report.md) — the closed-cycle decision;
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

## Reproducibility

The closed-cycle machine-readable decision is stored at
`benchmarks/operation-routing-v4-terminal-decision.json`.

The full evidence ledger is stored at
`benchmarks/research-experiment-ledger.json`.

The complete design/experiment narrative is stored at
`docs/research/design-and-experiment-history.md`.

The terminal report is available at
[Operation routing v4 terminal report](operation-routing-v4-terminal-report.md).
