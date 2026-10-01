# SchemaRouter design and experiment history

> Active research/session roadmap: GitHub issue #417  
> Historical 0.13 prior-art roadmap: GitHub issue #388  
> Prior-art roadmap: `docs/research/prior-art-roadmap.md`  
> Machine-readable prior-art registry: `benchmarks/research-prior-art-registry.json`  
> Historical session-resume tracker: GitHub issue #200  
> Machine-readable evidence ledger: `benchmarks/research-experiment-ledger.json`

This document reconstructs the material design and research lineage of SchemaRouter from the initial repository implementation onward. It is broader than release notes: it records architectural intent, empirical questions, rejected alternatives, data-consumption rules, and why the project moved from one routing design to the next.

Routine bugfixes that do not change an architectural invariant, evaluation contract, or empirical conclusion remain available in Git history but are not promoted to independent research events here.

## 1. Origin: schema-aware execution boundary

### Initial commit → v0.1 framework core

Source revision: `55e2563966b7c656a59f6fe1862ff7d01ef87bee`

The original design established the core thesis that still governs the project:

```text
natural-language intent
        ↓
registered typed schema
        ↓
bounded plan
        ↓
policy + validation
        ↓
execution
```

The model/orchestrator is not the execution authority. The registered schema and local runtime are.

Initial material decisions included:

- typed tool/endpoint/parameter/field/plan/result contracts;
- schema-aware planning and field projection;
- argument and raw-result JSON Schema validation;
- fail-closed handling for mutation, destructive and unclassified remote operations;
- schema/invoker drift protection;
- credential separation from model-visible arguments;
- OpenAPI, MCP and Python callable ingestion;
- LangChain integration without making SchemaRouter a general agent framework.

This is the project invariant against which later experiments must be interpreted.

## 2. v0.2: adapter ecosystem and OPTIMADE

Source revision: `1de6b4e14f4bb6607f58e6fc73b6b62d21e9473d`

The second architectural phase generalized source ingestion behind explicit adapter contracts.

Important additions:

- `SourceAdapter` / `AdapterRegistry`;
- first-class OPTIMADE discovery;
- field-aware `response_fields` projection;
- call-aware protocol invokers;
- live compatibility smoke evidence;
- explicit transport/credential boundaries.

This shifted SchemaRouter from a fixed integration set toward a capability-schema substrate.

## 3. v0.3: bounded decision backends

Key source revisions:

- `7c25ae95439a9cc07a5ab7b6d81db50dea791d89`
- `dfe4b85f12ae7356e085d93897b56f73272088db`
- `ac7833feceef21a1949fb70308ba86159037db21`

Research/design question:

> Can semantic/model assistance improve routing while remaining unable to invent executable authority?

The answer was encoded as `DecisionBackend`: a model sees only a finite set of locally authorized option IDs and can choose or abstain, but cannot create new executable destinations.

This phase added:

- provider-neutral bounded decisions;
- deterministic fallback;
- opt-in granular `DecisionPolicy`;
- Jev/TypeSafe integration;
- LlamaIndex integration;
- approvals, budgets, telemetry and plugin contracts;
- the first checked-in multilingual/adversarial benchmark corpus.

### decision-routing-v1

- 144 cases;
- multilingual/adversarial coverage;
- JSON/CSV benchmark reporting;
- accuracy, abstention, invalid-plan and latency metrics.

Historical workflow-level provenance for the earliest runs is being fully backfilled under issue #196. The corpus and commit history are retained.

## 4. v0.4: persistence, local decisions and evidence surfaces

The v0.4 line added several architectural layers that later routing research relied on:

- LangGraph `StateGraph` bridge;
- provider-neutral embedding decision backend;
- local Ollama bounded backend;
- transactional SQLite registry;
- replayable run traces;
- bounded output-field selection;
- explicit nested projection paths;
- conservative evidence sufficiency;
- exact-recall candidate indexing;
- bounded same-origin OpenAPI external refs;
- trusted before/after execution hooks.

The significant design progression was from “select a route” toward “select a route while retaining explicit evidence, output-field and execution-state contracts.”

### Historical negative experiment: generic no-route sentinel

Before the later operation-routing cycles, empty lexical recall could optionally expose the entire registered catalog to a bounded decision backend. An explicit `none_of_the_above` option was tested as a generic no-route sentinel.

The first PR #85 experiment on the 144-case corpus found 56.25% overall / 29.09% Korean accuracy with recall-on-empty plus the sentinel. A 0.25 confidence + no-route configuration reached 54.17% overall / 25.45% Korean and 50% OOD/adversarial accuracy.

The follow-up run showed why the mechanism was wrong: 16 explicit no-route selections contained 13 valid Korean in-domain requests and only 3 true no-route cases. PR #87 / commit `e41f57a0` removed the sentinel.

Without the sentinel, recall-on-empty reached 61.81% overall and 43.64% Korean accuracy; adding the same 0.25 confidence/no-route policy reached 60.42% overall, 38.18% Korean and 50% OOD/adversarial accuracy. The project retained empty-recall expansion, confidence gating, candidate abstention and offline threshold calibration instead.

For the current 0.11 research: a generic catch-all sentinel should not simply be reintroduced under a new name. Negative capability evidence must instead be represented as a distinct typed boundary signal and remain non-authoritative.

## 5. v0.5: runtime/OpenAPI correctness

This phase primarily hardened execution semantics:

- transient-aware retry classification;
- wall-clock bounded retry/approval/hook execution;
- OpenAPI operation parameter override correctness;
- collision-safe endpoint names;
- required body preservation;
- protocol/auth header isolation;
- multiple success-response contract handling.

These changes matter to later experiments because benchmarked plans must correspond to executable, contract-valid behavior rather than a planning-only abstraction.

## 6. v0.6: operational observability and local inference

The project added:

- read-only inspection API and CLI;
- self-contained HTML dashboard;
- Laya local decision backend;
- expanded OpenAPI composition and serialization fidelity.

This established the operational principle that routing decisions and runtime state should be inspectable without granting UI or model surfaces mutation authority.

## 7. v0.7: field-first, route-second

This was a major architectural shift.

The routing question became:

> What data fields are actually required, and which currently valid provider/access path can satisfy them?

Material changes:

- provider/access identity;
- bounded read-only fallback;
- server-side projection;
- typed scientific datatype/unit/qualifier contracts;
- trusted parameter aliases;
- schema-drift classification;
- operation-scoped policy rules;
- structured `PlanExplanation`;
- bounded parallel read fan-out;
- recoverable access-path health state.

The design kept unit metadata optional because not every source is scientific/numeric; text sources such as papers and web/document search are valid unitless capabilities.

### Benchmark/reproducibility methodology added during the 0.7 line

The project also formalized how empirical evidence is retained:

- multi-run benchmark history and machine-readable compatibility artifacts (#83);
- an on-demand full-corpus research workflow with retained JSON/CSV/HTML artifacts (#84);
- opt-in empty lexical recall recovery plus candidate-abstention and offline threshold-calibration tooling (#85);
- exact source revision, corpus SHA-256, repeat count and case-limit metadata in benchmark reports (#89).

These changes are methodologically important: later routing claims can be traced to an exact source/data configuration rather than screenshots or chat notes.

## 8. v0.8: semantic routing stages and holdout discipline

This phase introduced the routing stages that became the main research subject:

```text
lexical recall
    ↓
semantic candidate recall
    ↓
candidate-fit / no-route gate
    ↓
operation-fit inside leading tool domain
    ↓
endpoint disambiguation
    ↓
validated plan
```

Important boundaries:

- semantic candidate recall can add only registered candidates;
- candidate-fit can suppress but not create authority;
- operation-fit is bounded to sibling operations;
- endpoint disambiguation stays inside the authorized tool domain;
- operation aliases are explicit trusted schema, never model-authored.

### Corpus lineage

The benchmark protocol evolved to avoid repeatedly tuning on the same evidence:

- v2 — 1,200-case multilingual stress corpus with fixed splits;
- v3 — separate 600-case untouched capability-fit holdout;
- v4 — operation-fit holdout;
- v5 — operation development/calibration source;
- v6 — 600-case operation regression holdout;
- v7 — fresh post-change holdout;
- v8 — alias-aware holdout later found to have been accidentally consumed by a diagnostic path;
- v9 — replacement fresh alias-aware one-shot holdout;
- v10 — fresh operation-generalization holdout.

Known v9 result:

- overall 51.167%;
- supported exact route 38.281%;
- near-domain unsupported rejection 70.833%;
- OOD rejection 100%.

Known v10 result:

- overall 55.667%;
- supported exact route 42.188%;
- near-domain unsupported rejection 77.083%;
- OOD rejection 100%.

The v8 incident is retained as methodology evidence: a holdout touched by diagnostic tuning is not “reset”; it remains consumed and is replaced.

The same line also added explicit routing error taxonomy and failure-stage attribution, allowing later studies to separate candidate recall, capability-fit, operation-fit, wrong-tool and wrong-endpoint failures. The operation-fit semantic representation itself was simplified using v5 development/calibration only before the one-shot v10 generalization run.

## 9. v0.9: bounded pairwise reranking

Source revision: `880451eb0e4adadd5e96290c8c576820614fbc7a`

A cross-encoder/reranker-style `PairwiseDecisionBackend` was introduced.

The scorer receives only authorized `(query, option)` pairs. Scores are mapped back locally to opaque option IDs.

### v11 generalization holdout

Frozen BGE pairwise candidate:

- overall accuracy: 51.667%;
- supported exact route: 25.781%;
- near-domain unsupported rejection: 97.396%;
- OOD rejection: 100%.

Post-consumption MiniLM diagnostic:

- supported exact route: 40.625%;
- near-domain unsupported rejection: 77.604%.

Interpretation:

BGE substantially improved unsupported-operation rejection but harmed supported recall and latency. It was retained as an optional primitive, not promoted as the unconditional routing default.

This established a recurring theme of the follow-up research: selection quality and rejection quality are not the same objective.

## 10. v0.10 contrastive BGE cycle

Cycle: `0.10-operation-contrastive-v1`

Research question:

> Can sibling-contrastive pairwise scoring improve the supported/rejection balance?

Development selection used v5 development only. The selected candidate was frozen before confirmation:

- BGE reranker;
- sibling-contrastive transform;
- beta = 1.0;
- operation-fit min score = 0.01;
- min margin = 0.0.

Development:

- supported: 65.625%;
- near-domain unsupported rejection: 95.833%.

Calibration confirmation:

- supported: 62.5%;
- rejection: 97.917%.

### v12 hygiene classification

v12 had been inspected before architecture selection, so it was classified as design-known stress evidence, not blind evidence.

### v13 blind-final

Generated only after full candidate freeze.

Result:

- 600 cases;
- supported: 61.719%;
- near-domain unsupported rejection: 98.438%;
- OOD rejection: 100%;
- false routes: 3;
- invalid plans/errors: 0.

Decision:

The exact frozen profile passed its blind-final preregistered floors as an optional profile. v13 is permanently consumed and cannot be used for retuning.

## 11. v0.10 cheap-first cascade

Cycle: `0.10-operation-cascade-v2`

Question:

> Can cheap MiniLM decisions handle easy cases and selectively escalate to BGE while preserving quality?

The selected development candidate reduced mean latency by about 10.47% and passed development floors.

Fresh same-job calibration:

- supported: 61.458%;
- near-domain rejection: 94.792%;
- mean latency reduction vs full BGE: 14.983%.

The preregistered rejection floor was 95%.

Decision:

Rejected, by one case, without calibration retuning.

This negative result is important paper evidence: the project followed the confirmation-only calibration rule even when the performance miss was small.

## 12. v0.10 graph-projection cycle

Cycle: `0.10-operation-graph-projection-v3`

Question:

> Can graph topology own routing authority while semantic models attach only bounded soft evidence?

Architecture explored:

- hard schema graph paths;
- semantic graph seed;
- bounded propagation;
- selective pairwise escalation;
- graph corroboration;
- static option embedding cache.

A major measurement correction also occurred: early sequential baseline/candidate timing was recognized as vulnerable to warm-cache/order bias. Later latency evidence used warmup + counterbalanced paired execution.

Frozen development candidate:

- 1,200 cases;
- supported: 63.281%;
- near-domain rejection: 95.313%;
- OOD: 100%;
- false routes: 18;
- paired correctness +47 / -5;
- mean/p95 latency materially improved;
- all preregistered development gates passed.

### Invalidated calibration attempt

Workflow run `36285424108` generated a corpus but was cancelled before metric inspection because a structural audit found unsupported-family reuse from development.

The attempt is retained as an integrity event but excluded from empirical evidence.

### Fresh calibration

Frozen candidate:

- supported: 68.75%;
- near-domain rejection: 91.667%;
- false routes: 16;
- mean/p95 latency improved strongly;
- +14 / -2 paired correctness.

Decision:

Rejected because unsupported rejection missed the 95% confirmation floor. Calibration was consumed and not used for retuning.

This failure directly motivated a new cycle rather than threshold modification on confirmation data.

## 13. v0.11 routing-quality cycle

Cycle: `0.11-operation-routing-quality-v4`

The new research question is:

> Can typed multi-view evidence with explicit unknown handling improve exact routing and unsupported-operation rejection simultaneously?

Standing development gates:

- supported exact route >= 70%;
- near-domain unsupported rejection >= 96%;
- false-route <= 2%;
- invalid plan / authority violation / execution error = 0;
- paired mean and p95 latency non-regression.

Standing production target:

- supported exact route >= 85%;
- unsupported rejection 97–99%;
- false-route <= 1%.

### Fresh v4 development corpus

- 1,800 cases;
- 1,152 supported;
- 576 near-domain unsupported;
- 72 OOD;
- six language groups;
- 16 supported routes;
- corpus SHA: `fc085c58ed7c667d71024e60cf9e213e66da8f7b43f6e79551ed810a9e328216`.

Baseline:

- supported exact route: 44.01%;
- near-domain rejection: 94.10%;
- false-route: 5.25%;
- wrong tool: 3;
- wrong endpoint: 130.

### Typed evidence infrastructure

PRs #185 / #186 introduced:

- typed `DecisionEvidence`;
- explicit `score_kind`;
- `match / no_match / unknown`;
- `EvidenceProjector`;
- no arithmetic across incompatible score kinds;
- explicit on-unknown policy.

This is infrastructure, not itself a performance claim.

### Hierarchical tool → operation ablation

PR #189.

Hypothesis:

Separating tool-domain selection from operation selection would reduce routing confusion.

Result:

- supported exact route: 42.62%;
- rejection unchanged at 94.10%;
- false routes unchanged at 34;
- wrong tool unchanged at 3;
- wrong endpoint increased 130 → 166;
- paired +91 / -107.

Decision: rejected.

Interpretation: tool-domain selection was not the dominant error source; the implementation worsened within-tool operation choice.

### Accepted operation-fit selector ablation

PR #190.

Observation before the experiment:

operation-fit frequently identified a better registered endpoint but the planner used the decision only as a gate and discarded the accepted route ID.

A preregistered opt-in selector was implemented.

Result:

- supported exact route: 44.01% → 54.08%;
- wrong endpoint: 130 → 14;
- wrong tool remains 3;
- paired +129 / -13;
- all 151 route changes were driven by the accepted operation-fit top route;
- rejection: unchanged 94.10%;
- false-route: unchanged 5.25%;
- invalid plans/errors: 0.

Decision:

Standalone candidate rejected, selector primitive retained.

Interpretation:

endpoint selection can be improved independently of unsupported-operation rejection.

### Stage signal diagnostics

Behavior-preserving diagnostics measured candidate-fit geometry.

Key observations:

- 365 total candidate-fit abstentions;
- 94 supported requests abstained;
- in 43 of those supported abstentions, candidate-fit top route was already the expected route;
- at similarity 0.25, supported gate pass rate was 91.84%;
- but near-domain gate rejection was only 35.07%.

Interpretation:

A single global similarity threshold cannot be both a high-recall positive selector and a strong unsupported-capability boundary.

### Bounded retrieve → rerank diagnostic

PR #205 / work item #204 tested the preregistered architecture that removed the generic candidate-fit gate and let the existing contrastive BGE reranker score all already-authorized semantic-recall candidates.

The zero-threshold run was a ranking-ceiling diagnostic, not a promotable router.

Result on the same fresh 1,800-case v4 development corpus:

- raw supported top-route exactness: 90.71% (1045 / 1152);
- invalid plans / execution errors: 0 / 0;
- mean / p95 latency: 1014 / 1916 ms on the GitHub CPU runner.

The raw score distributions showed strong separation between most supported-correct winners and no-route requests, although route-specific tails remained.

Using the preregistered **winner-first** semantics (rank first, then apply only the raw winner's route-local threshold, and abstain instead of falling through), the following development-only score frontier resulted:

| canonical false-route budget | supported exact-route | false-route rate | actual near-domain rejection | actual OOD rejection |
| ---: | ---: | ---: | ---: | ---: |
| 0 / 648 | 70.57% | 0.00% | 100.00% | 100.00% |
| 6 / 648 | 74.05% | 0.93% | 99.13% | 98.61% |
| 12 / 648 | **75.78%** | **1.85%** | **98.09%** | **98.61%** |

This changed the immediate research conclusion:

- an additional NLI/negative model is not required to cross the current accuracy/rejection/false-route development gates;
- threshold application order was a major safety variable;
- the remaining primary gate is latency, because scoring four BGE candidates for every request is too expensive.

Artifact provenance:

- workflow: `36310955824`
- artifact: `10929374346`
- artifact digest: `47a1d7a5716b100edd654607816a6cceeb630be09091348fcc788928a73fdb09`
- source revision: `f43535b6ef0acbc5492b9791e6757e28a343d9fa`
- corpus SHA-256: `fc085c58ed7c667d71024e60cf9e213e66da8f7b43f6e79551ed810a9e328216`

### Winner-only threshold mechanism and evidence infrastructure

PR #208 added opt-in `rank_then_gate` semantics to `PairwiseDecisionBackend` and was merged into the active #195 research stack. The default historical `filter_then_rank` behavior remains unchanged.

PR #210 then ported the score-kind-safe `EvidenceProjector` from #186 into the same stack without wiring it into planner behavior. This keeps explicit `match / no_match / unknown` evidence available for later robustness work without prematurely adding a second decision signal.

### Recall-width latency ablation

Work item #214 / PR #216 preregistered a width-only development ablation.

The selection rule was fixed before execution:

1. evaluate recall widths 2 and 3;
2. derive the same winner-only false-budget-12 frontier;
3. choose the smallest width that preserves >=70% supported exact-route, <=2% canonical false-route, >=96% near-domain rejection lower bound, and zero invalid plans/errors;
4. if neither passes, retain width 4.

The chosen width must still pass a separately executed paired latency gate before the candidate is frozen.

## 14. Current research direction

Tracked in issue #197.

The next candidate must combine:

1. accepted operation-fit selector;
2. route/boundary-local calibration where justified only by fresh development;
3. typed score-kind-safe evidence;
4. explicit negative-capability evidence;
5. explicit unknown handling;
6. reranking only inside authorized schema candidates.

The architectural principle remains unchanged:

> Semantic evidence can rank, veto or abstain over registered authority. It cannot create authority.

## 15. Research governance and session continuity

Canonical tracker: #200

Related work items:

- #196 — historical design/experiment backfill;
- #197 — active 0.11 composite candidate;
- #198 — freeze/calibration/blind confirmation;
- #199 — follow-up paper evidence package.

At the start of a new session:

1. read #200;
2. read the active child issue;
3. read `benchmarks/research-experiment-ledger.json`;
4. read the current preregistration/result manifests;
5. inspect active PR/workflow state;
6. continue the first incomplete task whose prerequisites are satisfied.

Chat history is not a required source of project state.

## 16. Evidence policy for the follow-up paper

Every empirical result should preserve, where available:

- source revision;
- dataset role;
- tuning eligibility;
- preregistration/freeze state;
- workflow run ID;
- artifact ID;
- artifact SHA-256;
- corpus SHA-256;
- exact configuration;
- result metrics;
- decision: accept/reject/diagnostic-only;
- failure reason;
- whether the evidence is permanently consumed.

Rejected and invalidated experiments remain part of the record.

The machine-readable ledger is the canonical source for generating future paper tables and reproducibility appendices.


## 17. Complete repository-history audit

The mainline history has been enumerated from the initial commit through the research-cycle baseline used for this reconstruction.

Canonical audit manifest:

- `benchmarks/repository-history-audit.json`
- mainline commits enumerated: 140
- initial revision: `5691c3c922f0209231f112c06096fe8744681fc5`
- audited main head: `526d0c588bbec053fba54c55d982cc67d2a74d56`

Subject-index counts at the audit point:

- 42 feature commits
- 21 fixes
- 14 research commits
- 10 releases
- 10 documentation commits
- 9 test commits
- 7 CI commits
- 4 security commits
- 4 benchmark commits
- 3 performance commits
- 15 chores
- 1 initial/other commit

This enumeration is broader than the narrative above, so the research record does not silently exclude early implementation work just because it predated the formal 0.10/0.11 experiment manifests.

Rejected and unmerged research branches are not expected to appear in mainline history. They remain represented independently in `benchmarks/research-experiment-ledger.json` through PR, branch, workflow-run, artifact, and decision provenance.

The audit has two complementary axes:

1. mainline history completeness — every commit from repository inception is enumerated;
2. research evidence completeness — material unmerged/rejected experiments remain in the experiment ledger instead of disappearing when their PR is closed.


## 18. Width-2 frozen winner-gate executable result

Work item #227 / PR #228 executed the preregistered width-2, score-only, route-local `rank_then_gate` candidate on the fresh 1,800-case v4 development corpus. The threshold map was frozen before execution from canonical width-selection artifact `10930665000`; no calibration or blind evidence was used.

Quality/safety result:

- supported exact-route: 72.57% (gate >=70%);
- near-domain unsupported rejection: 98.09% (gate >=96%);
- canonical false routes: 12/648 = 1.85% (gate <=2%);
- OOD rejection: 98.61%;
- invalid plans / execution errors: 0 / 0.

The quality gates passed. The paired same-runner latency gate did not:

- baseline mean/p50/p95: 531.031 / 605.144 / 697.912 ms;
- candidate mean/p50/p95: 765.187 / 582.750 / 1836.868 ms;
- mean latency: +44.09%;
- p95 latency: +163.19%.

Decision: rejected on the development latency gate. This candidate is not frozen for confirmation and must not advance to #198 calibration/blind evaluation. The result is important negative evidence: winner-only route-local gating can cross the current quality/safety frontier at width 2, but unconditional BGE invocation still produces unacceptable CPU mean/tail latency.

Provenance:

- source revision: `fdaf3f77e95b504e81739c69cd1d9889d36afabb`;
- workflow run: `36315784179`;
- artifact: `10931078672`;
- artifact SHA-256: `00517181c286197fe61156d04348eb9519bc8dab3681d20650216bfb923b37e1`;
- corpus SHA-256: `fc085c58ed7c667d71024e60cf9e213e66da8f7b43f6e79551ed810a9e328216`.

The next development-only evidence task was #226: measure a cheap multilingual action-only signal built solely from endpoint action names and trusted `operation_aliases`. Any behavior-changing fast path, veto, or evidence projection remained subject to separate preregistration.

## 19. Cheap action-only evidence diagnostic

Work item #226 / PR #230 tested a behavior-preserving evidence surface using the existing multilingual MiniLM. The representation included only the normalized endpoint action name and trusted `operation_aliases`; tool descriptions, endpoint descriptions, fields, parameters, corpus templates, and unsupported-operation labels were excluded.

DEV result:

- supported raw top-route exact: 73.00%;
- English / Spanish / mixed / Japanese / German / Korean raw exact: 86.46 / 80.73 / 76.56 / 73.96 / 64.06 / 56.25%;
- query embedding + cosine mean/p50/p95: 13.836 / 13.604 / 15.515 ms;
- static 16-option embedding cost: 68.724 ms, cacheable.

The high-precision direct-accept frontier was narrow:

- score >=0.50 and margin >=0.10: 155/1800 accepted, 98.06% precision, 8.61% overall coverage;
- score >=0.55 and margin >=0.15: 67/1800 accepted, 100% observed precision, 3.72% overall coverage.

Decision: retain the signal as a cheap bounded selector/supporting evidence surface, but do not promote it as a global direct fast path. Its high-precision coverage is too small to remove the BGE p95 bottleneck.

Provenance:

- source revision: `521dcc65e0269d68c76a372606f8d22b2ac57aa1`;
- workflow run: `36319105106`;
- artifact: `10932010750`;
- artifact SHA-256: `ae12b6a9abb3f6d7bc2d53792ce75b12bcb853971c8f6367f97a8f949c499011`;
- corpus SHA-256: `fc085c58ed7c667d71024e60cf9e213e66da8f7b43f6e79551ed810a9e328216`.

PR #230 was merged into the active v4 research integration branch because it adds diagnostic instrumentation only; it does not change default routing behavior.

## 20. Action-guided single-pair BGE diagnostic

Work item #231 / PR #232 tested whether the cheap action-only signal could choose one candidate from the already-authorized width-2 recall set before invoking BGE on only one query-route pair.

Result:

- raw supported exact-route: 74.48%;
- mean / p95 latency: 445.96 / 476.42 ms;
- strict 6/648 false-route frontier:
  - supported exact: 62.15%;
  - false-route: 0.93%;
  - near-domain rejection lower bound: 98.96%;
- canonical 12/648 frontier:
  - supported exact: 65.36%;
  - false-route: 1.85%;
  - near-domain rejection lower bound: 97.92%;
- invalid plans / execution errors: 0 / 0.

Decision: rejected. Single-pair BGE solved much of the CPU latency problem but did not preserve enough supported recall.

Provenance:

- workflow: `36319879567`;
- artifact: `10932093354`;
- artifact SHA-256: `47f1a8dcab2f1956a939df995c0f19137e96d92b8a4451753abdf039598934aa`.

## 21. Cheap embedding architecture diagnostics

### Bounded action embedding

Work item #233 / PR #236 tested cached multilingual MiniLM action-only evidence inside the bounded width-2 set.

Valid revision-2 result:

- raw supported top-route exact: 73.35%;
- canonical 12/648 supported exact: 47.92%;
- near-domain rejection: 97.92%;
- false-route: 1.85%;
- mean / p95 latency: 44.29 / 47.98 ms.

An earlier run was invalidated before result inspection because projected metrics could have used only scored rows rather than the fixed 1,800-case denominator.

Decision: rejected. The architecture was fast, but score/margin open-set gating collapsed supported recall.

### Single-query MiniLM dual view

Work item #240 / PR #241 scored two cached route representations from one query embedding:

- schema/domain view;
- action/alias view.

The best raw strategy was schema/action 0.25/0.75 at 75.00% supported exact. The best canonical 12/648 point reached only 54.77% exact at 97.92% near-domain rejection and 1.85% false-route, while latency fell to about 14.02 / 15.31 ms mean/p95.

Decision: rejected for quality, retained as evidence that representation capacity rather than runtime had become the limiting factor.

## 22. Multilingual embedding backbone screen

Work item #242 / PR #243 kept the dual-view architecture fixed and changed only the multilingual embedding backbone.

### E5-base

- best raw exact: 84.46%;
- best canonical 12/648 exact: 62.41%;
- latency: 50.19 / 56.20 ms mean/p95.

### GTE multilingual base

- best raw exact: 89.15% using schema/action 0.25/0.75;
- best canonical 12/648 exact: 63.11%;
- latency: 69.37 / 76.58 ms mean/p95.

GTE proved that >=85% ranking capacity was available, but its native score geometry was not a sufficient open-set boundary.

### BGE-M3 embedding

BGE-M3 was the first embedding-only architecture to combine high ranking quality with a strong open-set frontier:

- best raw exact: 88.45%;
- at 12/648 false routes:
  - supported exact: 83.85%;
  - near-domain rejection: 97.92%;
  - false-route: 1.85%;
- at 6/648 false routes:
  - supported exact: 83.33%;
  - near-domain rejection: 98.96%;
  - false-route: 0.93%;
- p95 latency: approximately 168 ms.

Decision: BGE-M3 selected as the main strict open-set optimization line.

## 23. GTE winner + BGE rejector

Work item #244 / PR #249 tested a factorized architecture:

1. GTE 0.25/0.75 dual-view selects one registered route;
2. BGE reranker scores only that winner;
3. BGE may accept/reject but may not switch routes.

All four preregistered action/capability × max-length variants preserved raw GTE ranking at 89.15%, but the best canonical open-set result was only:

- supported exact: 76.13%;
- near-domain rejection: 97.92%;
- false-route: 1.85%;
- best end-to-end mean / p95 latency: 293.89 / 328.11 ms.

Decision: rejected. A cross-encoder winner relevance score was not a clean enough open-set separator to preserve GTE's ranking headroom.

## 24. Frozen BGE-M3 candidate and numerical-stability finding

Work item #245 / PR #247 froze the BGE-M3 50/50, budget-6 profile and executed it through the actual `SchemaPlanner`.

Safety and authority behavior reproduced exactly:

- planner/direct parity mismatches: 0 / 1800;
- invalid plans: 0;
- execution errors: 0;
- rank-2 fallthroughs: 0;
- false-route: 6/648 = 0.93%;
- near-domain rejection: 98.96%;
- OOD rejection: 100%;
- planner mean / p95 latency: 188.73 / 206.00 ms.

However, the frozen projection expected 960 supported-correct cases and executable confirmation produced 959/1152 = 83.25%.

Artifact inspection localized the single-case drift:

- case: `v4-dev-papers-citations-ko-08`;
- route: `papers.citations`;
- frozen min score: `0.46308739913552904`;
- rerun score: `0.4630872644672503`;
- difference: approximately -1.35e-7.

The route winner and planner/direct behavior did not change; only the accept/reject boundary flipped.

Decision: not promoted.

This established an additional operational requirement: a frozen threshold must not be an observed floating-point sample boundary. Later candidates must define explicit numerical-stability semantics such as midpoint thresholds, conservative quantization/guard bands, and perturbation checks.

Provenance:

- workflow: `36323685913`;
- artifact: `10933122169`;
- artifact SHA-256: `a63e6954d8cf44db21bc89b336ca8f67bacc77af933fe870c33bc9298bf6a1a1`.

## 25. BGE-M3 fine global fusion

Work item #246 / PR #248 preregistered schema weights 0.30–0.60 with no post-run interpolation.

Best strict 6/648 result:

- schema/action fusion: 0.55 / 0.45;
- supported exact: 965/1152 = 83.77%;
- near-domain rejection: 98.96%;
- false-route: 0.93%;
- wrong-supported accepted: 62;
- mean / p95 latency: 180.34 / 195.97 ms.

Best secondary 12/648 result:

- supported exact: 970/1152 = 84.20%;
- near-domain rejection: 97.92%;
- false-route: 1.85%.

The final >=85% strict target requires at least 980/1152 correct cases, so the best global fusion was 15 cases short.

Decision: global fine-fusion search exhausted without passing the production target.

Provenance:

- workflow: `36324755106`;
- artifact: `10934145256`;
- artifact SHA-256: `60dfbb1d32f1f27873bd8fad4aa4888af80856365196e3ab6fb5be6b1e7f0af7`.

## 26. Current active optimization: recover the final 15 cases

Route-level analysis of #246 found that different routes prefer different schema/action weights. Holding the global 0.55 weight produced 1,019 raw supported-correct cases, while independently choosing the best preregistered grid weight for each route yields a diagnostic raw ceiling of **1,046**, a +27-case headroom.

The largest examples include:

- `inventory.search`: 50.00% raw exact at global 0.55 versus 69.44% at route-local 0.35;
- `papers.search`: 81.94% versus 90.28% at route-local 0.30.

### #256 route-local stable fusion

Work item #256 / PR #257 is the lower-cost active line.

It freezes the route-local weight map before execution and changes boundary construction so that:

- an observed sample score is never used directly as a threshold;
- candidate thresholds are midpoints between adjacent unique winner scores;
- selected score thresholds are conservatively rounded upward to six decimals;
- final metrics are stress-tested at ±1e-6 and ±1e-5 score/margin perturbations.

Primary gate:

- supported exact >=85%;
- near-domain rejection >=97%;
- false-route <=1%;
- OOD rejection 100%;
- p95 <=250 ms;
- the same primary quality/safety gates must survive ±1e-6 perturbation.

### #255 conditional zero-false rescue

Work item #255 / PR #258 runs in parallel as a more expensive fallback.

It keeps the immutable #246 strict 0.55/0.45 base and invokes a pinned BGE cross-encoder only on base abstentions, with a primary rescue budget of zero additional false routes.

The validator may only rescue the same raw rank-1 winner; it cannot switch to rank 2 or create execution authority.

Both lines remain DEV-only. Calibration/blind evidence remains blocked until a fully frozen candidate passes the complete development, numerical-stability, and runtime gates.


## 27. Parallel numerical-stability experiment

Work item #256 / PR #257 runs in parallel with the rejected-winner rescue line.

Motivation:

The global 0.55/0.45 BGE-M3 base is close to the final target, but #246 also showed that different routes prefer different schema/action fusion weights. Selecting each route's weight from the already-preregistered #246 grid gives a raw supported-ranking ceiling of **1046/1152**, compared with 1019/1152 for the global 0.55 ranker.

The route-local fusion map was frozen before execution. To avoid repeating the #245 numerical-boundary failure, its threshold protocol is stability-oriented:

- score thresholds are midpoints between adjacent observed winner scores, never an observed sample score itself;
- selected minimum scores are rounded upward to 6 decimal places;
- final full-population metrics are recomputed after rounding;
- the strict profile must survive an adversarial ±1e-6 score/margin perturbation while keeping >=85% exact, >=97% near-domain rejection and <=1% false-route;
- ±1e-5 is retained as a secondary stress diagnostic.

This experiment is diagnostic only. Even a passing map requires a separate frozen executable confirmation before any calibration or blind evaluation.


## 28. Late-stage strict-base, stability, and rescue results

Sections 26–27 described #255/#256 while they were still active. Their terminal results, and the numerically robust successor base, are recorded here so the paper/research narrative has an unambiguous current state.

### #255 — zero-additional-false cross-encoder rescue

Work item #255 / PR #258 kept the strict BGE-M3 0.55/0.45 base immutable and invoked the pinned BGE reranker only on base abstentions.

Primary zero-additional-false result:

- base: 965/1152 = 83.77% supported exact;
- base false-route: 6/648 = 0.93%;
- rescued correct supported cases: 5;
- additional false routes: 0;
- composed supported exact: 970/1152 = 84.20%;
- near-domain rejection remained 98.96%;
- composed mean / p95 latency: 301.05 / 473.75 ms.

Decision: rejected. Same-winner cross-encoder rescue was safe but recovered only one third of the 15 cases required to cross 85%.

Provenance:

- workflow: `36325681661`;
- artifact: `10934276251`;
- artifact SHA-256: `a51ae289ed3dd4dd2e9bdb06bbf70e26f32f1df030a119feeb9883cd131b8e25`.

### #256 — route-local stable fusion

Work item #256 / PR #257 froze route-local schema/action weights selected from the already-preregistered #246 grid and replaced literal observed-score boundaries with midpoint + upward-rounded thresholds.

Result:

- raw supported exact: 90.54%;
- strict 6/648:
  - supported exact: 963/1152 = 83.59%;
  - near-domain rejection: 98.96%;
  - false-route: 0.93%;
- secondary 12/648:
  - supported exact: 84.46%;
  - near-domain rejection: 97.92%;
  - false-route: 1.85%;
- strict metrics were unchanged under adversarial ±1e-6 and ±1e-5 stability diagnostics;
- mean / p95 latency: 180.50 / 197.16 ms.

Decision: rejected. Route-local fusion proved that ranking headroom above 90% exists, but the open-set acceptance boundary still prevented >=85% exact under the <=1% false-route constraint.

Provenance:

- workflow: `36325721448`;
- artifact: `10933809684`;
- artifact SHA-256: `ca4df26ba5307b8e5aad22e2443f9e69713428b0898303939d8fd1cba3d443c0`.

### #259 — numerically robust frozen BGE-M3 base

The failed #245 confirmation showed that a literal observed-score threshold could flip one case from a runtime drift of only ~1.35e-7.

Work item #259 / PR #260 froze, before execution:

- BGE-M3 revision `5617a9f...`;
- schema/action fusion 0.55 / 0.45;
- #246 strict budget-6 route-local thresholds;
- winner-only rank-then-gate;
- no rank-2 fallthrough;
- a comparison epsilon of 1e-6:
  - `top_score + epsilon >= min_score`;
  - `top_margin + epsilon >= min_margin`.

Executable confirmation passed:

- supported exact: 83.7674%;
- near-domain rejection: 98.9583%;
- OOD rejection: 100%;
- false-route: 6/648 = 0.9259%;
- invalid plans / execution errors / rank-2 fallthroughs: 0 / 0 / 0;
- planner/direct parity mismatches: 0 / 1800;
- planner mean / p95 latency: 118.26 / 134.95 ms.

Decision: confirmed as the robust strict base for later conditional rescue experiments. This is a development confirmation, not independent generalization evidence.

Provenance:

- source revision: `9e9b1049eac779adbc5781bfc45a447966ae32e8`;
- workflow: `36325967632`;
- artifact: `10934635124`;
- artifact SHA-256: `aabe4321e039dbb2e0b0805553e4dfd7d6c4bcf63893e23da028ceb668608462`.

### #262 — cross-model zero-false abstention rescue

Work item #262 / PR #263 is the current active DEV diagnostic.

The #259 base is immutable. Only base abstentions are eligible. A rescue can only restore the same BGE-M3 raw top-1 route; it cannot select rank 2 or change execution authority.

Two preregistered variants are being evaluated:

1. GTE agreement — rescue eligibility requires the GTE 0.25/0.75 top-1 route to equal the frozen BGE-M3 raw top-1 route;
2. GTE agreement + BGE reranker — the same agreement gate plus one pinned winner-only cross-encoder score.

Primary rescue false budget: 0 additional false routes.

Target:

- composed supported exact >= 85%;
- near-domain rejection >= 97%;
- total false-route <= 1%;
- additional false routes = 0.

The active workflow is `36326745694`. Calibration/blind evidence remains untouched.

## 29. Current resume point

The canonical current state is:

1. #259 is the confirmed robust strict base;
2. #255 and #256 are terminal negative results;
3. #262 is the only active quality-improvement experiment;
4. #198 calibration/blind confirmation remains blocked;
5. if #262 passes, freeze the exact rescue profile in a separate executable candidate before any fresh confirmation;
6. if #262 fails, do not weaken the <=1% false-route boundary merely to hit the 85% exact target.

The architectural invariant remains:

> Semantic models may rank, reject, or rescue only among locally registered authority. They do not create execution authority.


## 30. Cross-model rescue, fresh-surface failure, and typed open-set evidence

### #262 — cross-model zero-false abstention rescue

Starting from the confirmed #259 BGE-M3 strict base, #262 restricted rescue authority to base abstentions and preserved the same raw BGE-M3 winner.

Two preregistered variants were evaluated:

1. GTE 0.25/0.75 dual-view top-1 must agree with the frozen BGE-M3 raw top-1;
2. the same agreement condition plus a winner-only BGE reranker score.

The GTE-only variant recovered 12 correct supported cases with zero additional false routes, reaching 977/1152 = 84.81% exact.

The GTE + winner-only reranker variant recovered 17 correct supported cases, 0 wrong-supported cases and 0 additional false routes:

- supported exact: 982/1152 = 85.2431%;
- near-domain rejection: 98.9583%;
- OOD rejection: 100%;
- total false-route: 6/648 = 0.9259%.

Decision: the cross-model variant crossed the full tuning-DEV target and was selected for a separate frozen executable candidate.

### #265 / PR #270 — frozen candidate and fresh-surface confirmation

The #262 winner was frozen before confirmation with:

- immutable #259 BGE-M3 base;
- GTE same-winner agreement;
- eight rescue-enabled routes only;
- a pinned BGE reranker for the four routes requiring a positive reranker threshold;
- global comparison epsilon 1e-6;
- no rank-2 fallback and no route-authority expansion.

Same-corpus executable confirmation reproduced the frozen DEV projection exactly:

- exact: 85.2431%;
- near-domain rejection: 98.9583%;
- false-route: 0.9259%;
- planner/direct mismatch: 0;
- GTE invocation: 28.17%;
- reranker invocation: 4.28%;
- planner p95: 239.32 ms.

The preregistered second stage then used a deterministic zero-overlap fresh-surface DEV corpus.

Result:

- supported exact: 86.7188%;
- near-domain rejection: 77.7778%;
- false-route: 128/648 = 19.7531%;
- base false routes before rescue: 122;
- rescue-added false routes: 6;
- planner/direct mismatch: 0;
- invalid plans / execution errors: 0 / 0.

Decision: rejected.

This is a central late-stage result:

> The route-ranking capacity generalized to new request surfaces, but the positive route-score open-set acceptance boundary did not.

The failed fresh-surface corpus is confirmation-only evidence and is permanently excluded from threshold or row-level retuning.

## 31. #273 — contradiction-only multilingual NLI veto

To avoid positive route-score calibration, #273 removed route-local positive acceptance thresholds and used BGE-M3 raw top-1 as the only route authority. A multilingual NLI model could only veto the winner when contradiction probability exceeded a preregistered global threshold.

Runtime remained practical:

- BGE-M3 ranking mean/p95: 151.15 / 177.15 ms;
- NLI single-pair mean/p95: 14.13 / 15.29 ms;
- sequential mean/p95: 165.28 / 192.02 ms.

However, both supported and unsupported pairs were overwhelmingly classified as neutral, not contradiction.

Correct-supported winners:

- contradiction median: 0.1034;
- neutral median: 0.8432.

Near-domain unsupported:

- contradiction median: 0.0876;
- neutral median: 0.8627.

No preregistered contradiction threshold reached the 85/97/1 target.

Decision: rejected.

Interpretation: generic textual contradiction is not equivalent to absence of a registered operation capability. Open-set rejection needs explicit negative-capability semantics.

## 32. #275 — explicit negative-capability prototype veto

#275 introduced 32 explicit unsupported-action prototypes, four per tool domain, while preserving BGE-M3 raw registered top-1 as the only route authority.

The experiment evaluated 588 preregistered combinations of:

- winner-domain minimum similarity;
- optional winner/top-domain agreement;
- negative prototype minimum similarity;
- negative-over-action advantage.

Raw BGE-M3 supported top-1 remained 88.45% and p95 latency remained 139.79 ms.

The explicit negative evidence showed real semantic separation:

- correct-supported negative-advantage median: -0.0935;
- near-domain unsupported median: +0.1708.

But no rule passed the full gate.

The dominant failure was not the negative-capability signal itself. To reject OOD at 100%, the single winner-domain absolute-score veto entered the low-score tail of otherwise correct supported queries and removed too much supported recall.

Decision: reject the combined architecture, retain the negative-capability finding.

The architectural decomposition becomes:

1. route ranking;
2. near-domain negative-capability veto;
3. OOD membership detection.

These must not be collapsed into one route-local positive threshold.

## 33. #266 and #271 — rejected rescue ablations

Two additional abstention-rescue ablations confirmed that the remaining gap was not easily recoverable from the existing strict base.

### #266 — robust-base same-winner cross-encoder rescue

- base abstentions: 767;
- correct-winner headroom: 54;
- zero-additional-false rescues: 5;
- composed exact: 84.20%;
- composed p95: 472.69 ms.

Decision: rejected.

### #271 — native BGE-M3 abstention geometry

Using only existing BGE-M3 score/margin/agreement geometry:

- zero-additional-false rescues: 4;
- composed exact: 84.11%;
- near-domain rejection: 98.96%;
- false-route: 0.93%.

Decision: rejected.

These ablations support moving the open-set architecture away from strict-base rescue and toward explicit typed capability evidence.

## 34. #277 — global signed capability bank

Work item #277 / PR #278 removed route-local positive acceptance thresholds and evaluated a global signed capability space:

- 16 registered positive operation prototypes;
- 32 explicit unsupported negative prototypes;
- BGE-M3 raw registered top-1 as the only route authority;
- low capability-envelope veto for OOD;
- negative-over-positive signed advantage for near-domain rejection;
- optional positive/raw-winner consistency as veto only.

The fixed preregistered grid contained 504 rules.

Result:

- raw supported top-1: 88.4549%;
- mean / p95 latency: 157.09 / 181.00 ms;
- passing rules: 0.

The closest rule that simultaneously preserved <=1% false-route and 100% OOD rejection was:

- rule `e0.450-n0.350-a+0.050-noagree`;
- supported exact: 81.8576%;
- near-domain rejection: 98.9583%;
- false-route: 6/648 = 0.9259%;
- correct supported raw winners vetoed: 76.

Decision: rejected.

Interpretation:

> A global signed capability bank can enforce the safety boundary, but the evidence is too coarse and removes too many correct supported winners.

This strengthens the #275 decomposition: route-conditioned explicit negative capability evidence is useful for near-domain unsupported actions, while OOD membership needs a separate signal that does not depend on a low positive/domain score.

Provenance:

- workflow: `36356550905`;
- artifact: `10944407595`;
- artifact SHA-256: `00eb49f680d7b1bdfa8c341c2f091c641e4912ca94c9f0bc81815db3e70b3643`.

## 35. #279 — dual signed negative open-world detector

Work item #279 / PR #280 separated near-domain and OOD veto evidence while keeping BGE-M3 raw top-1 as the only route authority.

### Near-domain channel

- route-conditioned explicit unsupported-action prototypes from #275;
- maximum negative score;
- negative-over-raw-winner-action signed advantage.

### OOD channel

- eight registered domain anchors;
- sixteen broad background-domain prototypes;
- maximum background score;
- background-over-known-domain signed advantage.

No low-positive or route-local positive acceptance threshold was used.

The fixed preregistered grid contained 1,764 rules.

Result:

- raw supported top-1: 88.4549%;
- mean / p95 latency: 183.79 / 200.07 ms;
- promotion-gate rules: 0.

The trade-off exposed the structural limit of scalar signed evidence:

- best rule retaining supported exact >=85%:
  - exact 85.8507%;
  - near-domain rejection 86.8056%;
  - OOD rejection 69.4444%;
  - false-route 98/648 = 15.1235%;
- best rule with near >=97% and OOD =100%:
  - exact 65.3646%;
  - false-route 15/648 = 2.3148%;
- best rule with OOD =100% and false-route <=1%:
  - exact 36.0243%;
  - near-domain rejection 99.4792%;
  - false-route 3/648 = 0.4630%.

Background-over-known-domain signed-advantage distributions overlap around zero:

- correct-supported median -0.0890, p95 -0.0040, max +0.0714;
- OOD median +0.0418, p05 -0.0212, min -0.0359.

Decision: rejected.

This result closes the scalar-threshold line for the fixed prototype family. Finer threshold search would optimize inside an overlapping distribution rather than solve the open-set representation problem.

Provenance:

- workflow: `36358352642`;
- artifact: `10944663761`;
- artifact SHA-256: `f04242ac79d22b35f29486b9f3b94b3ce1603400bfc87382ec73a412905cea83`.

## 36. #281 — rank-based capability-set open-world veto

Work item #281 / PR #283 tested the final preregistered fixed-prototype heuristic family using only relative prototype ordering, with no scalar similarity threshold.

The route authority remained unchanged:

- BGE-M3 raw registered global top-1;
- no positive acceptance threshold;
- no rank-2 fallback;
- no pseudo-route;
- capability evidence could veto only.

### Near-domain local set

Within the raw winner domain, the experiment ranked:

- registered positive endpoint capability prototypes;
- four frozen explicit unsupported-action prototypes.

Five fixed near-domain veto modes covered local top-1/top-k negative composition and whether the best negative outranked the raw-route positive prototype.

### OOD global membership set

The experiment ranked:

- eight registered domain anchors;
- sixteen frozen broad background-domain prototypes.

Four fixed OOD modes covered background composition in top-1, top-2, top-3 and top-5.

The Cartesian product contained 20 fixed rules.

### Result

- raw BGE-M3 supported top-1: 1019/1152 = 88.4549%;
- mean / p95 query scoring latency: 185.41 / 200.66 ms;
- authority violations / execution errors: 0 / 0;
- promotion-gate passing rules: 0;
- rules satisfying total false-route <=1%: 0;
- rules retaining supported exact >=85%: 0.

Best supported-exact rule:

- `negative_top2_all__background_top2_all`;
- supported exact: 78.8194%;
- near-domain rejection: 81.9444%;
- OOD rejection: 83.3333%;
- false-route: 116/648 = 17.9012%.

Closest high-rejection rule:

- `negative_top1__background_top3_majority`;
- supported exact: 50.3472%;
- near-domain rejection: 98.2639%;
- OOD rejection: 100%;
- false-route: 10/648 = 1.5432%.

The rank geometry still contains useful semantic signal:

- correct-supported local top-1 negative rate: 21.20%;
- near-domain unsupported local top-1 negative rate: 96.88%;
- correct-supported membership top-1 background rate: 4.32%;
- OOD membership top-1 background rate: 81.94%.

However, composing the two channels still produces an overlap too large for the 85/97/1/100 target. Top-k composition is additionally sensitive to prototype-bank cardinality (8 known anchors vs 16 background anchors).

Decision: rejected; fixed-prototype heuristic refinement is terminated for this capability-bank family.

This activates the preregistered stopping rule from #281. Do not continue with finer scalar thresholds, larger top-k grids, route-specific exceptions or post-result hand rules. The next architecture must use a learned or externally pretrained open-set capability verifier/classifier under strict veto-only authority.

Provenance:

- source revision: `944df2e0f2dc8617e7b97e6a38d4e2f5684f5324`;
- workflow: `36359121048`;
- artifact: `10945431360`;
- artifact digest: `sha256:9d7fcfb8bff361137216c3bdc6182c5bb5cef50f2eee4d2f65e32711fff95b13`.

The failed #270 fresh-surface corpus remains confirmation-only and forbidden for tuning. Calibration/blind evidence remains untouched.

## 37. Current resume point

The current 0.11 research state is now:

1. raw BGE-M3 ranking capacity is sufficient (88.45% tuning DEV; fresh supported ranking also remained >85% in #270);
2. the confirmed strict positive-threshold base remains safe on the original DEV but its acceptance boundary is not surface-robust;
3. generic contradiction NLI does not encode missing capability;
4. fixed positive/negative/background prototype banks contain signal but scalar and relative-rank heuristics cannot jointly satisfy >=85% exact / >=97% near rejection / 100% OOD / <=1% false-route;
5. fixed-prototype heuristic refinement is closed;
6. #198 calibration/blind remains blocked;
7. the next behavior-changing experiment must test a learned or externally pretrained match / no_match / unknown verifier that can veto the raw registered winner but can never reroute or create execution authority.

The architectural invariant remains:

> Semantic models may rank or veto only among locally registered authority. They do not create execution authority.

## 38. #285 — grouped-OOF learned winner verifier

Work item #285 / PR #286 tested the first learned open-set boundary after the fixed-prototype stopping rule.

The learned component was not a router. BGE-M3 raw registered global top-1 remained the sole route authority. The verifier could only output:

- `match` — permit the already-selected raw winner;
- `no_match` — abstain;
- `unknown` — abstain.

No rank-2 fallback, route switching, pseudo-route, or semantic authority creation was allowed.

### Evaluation protocol

To reduce surface memorization, the experiment used six-fold leave-one-language-out OOF over:

- de;
- en;
- es;
- ja;
- ko;
- mixed.

Language was a grouping variable only and was forbidden as a model feature.

The fixed feature schema contained:

- 19 runtime-observable BGE/prototype geometry values;
- one-hot raw winner route ID.

Forbidden classifier features included query text, benchmark IDs, expected route, category, language and unsupported-family labels.

Exactly two classifier families and twelve thresholds were preregistered, for 24 fixed rules:

- regularized logistic regression;
- shallow regularized histogram gradient boosting;
- thresholds from 0.50 to 0.995.

### Result

Three preregistered rules passed the full 85/97/1/100 DEV target under grouped OOF.

Selected rule by preregistered ordering:

- HGB @ p_match >= 0.50;
- supported exact: 1000/1152 = 86.8056%;
- near-domain rejection: 573/576 = 99.4792%;
- OOD rejection: 72/72 = 100%;
- false-route: 3/648 = 0.4630%;
- combined mean / p95 latency: 158.02 / 171.76 ms;
- authority violations / errors: 0 / 0.

Verifier discrimination:

- logistic ROC-AUC: 0.98803;
- logistic average precision: 0.98871;
- HGB ROC-AUC: 0.98797;
- HGB average precision: 0.98902.

Per-language supported exact for the selected held-out predictions ranged from:

- 81.77% on de;
- to 91.15% on mixed.

Per-language unsupported rejection remained approximately 99.07–100%.

Decision: promote HGB p=0.50 to a separate frozen candidate.

This is the first 0.11 open-set design to pass the long-term target under a grouped OOF protocol without query-text features or benchmark labels.

Provenance:

- workflow: `36360129634`;
- source revision: `cfaafb84bb651a6d6d38c4ce741f05ac61f37e9e`;
- artifact: `10945581502`;
- artifact digest: `sha256:eb417bb3aafa4d2f86aee4e79476ea64f49a2a3608269835d4d3b82f971d8054`.

## 39. #287 — frozen HGB winner verifier

Work item #287 / PR #288 froze the #285-selected HGB verifier without changing classifier, features or threshold after OOF results were known.

### Freeze contract

- classifier: `HistGradientBoostingClassifier`;
- threshold: 0.50;
- scikit-learn: 1.7.2;
- fit exactly once on all 1,800 original tuning DEV rows;
- serialized as one joblib file;
- SHA-256 pinned before confirmation;
- the same serialized model reused for same-corpus and fresh-surface evaluation;
- no refit in either confirmation stage;
- raw BGE-M3 registered top-1 remained the sole route authority.

Frozen model SHA-256:

`8cdb8b526705482d2a51dee79f8f17ce10e19199e823cab651a434918c8aa239`

### Same-corpus executable confirmation — PASS

- supported exact: 1010/1152 = 87.6736%;
- near-domain rejection: 575/576 = 99.8264%;
- OOD rejection: 72/72 = 100%;
- false-route: 1/648 = 0.1543%;
- combined p95: 221.33 ms;
- authority violations / errors: 0 / 0.

This confirmed the frozen implementation but is not independent generalization evidence.

### New zero-overlap fresh-surface DEV — FAIL

Fresh corpus:

- seed: `operation-routing-quality-v4-learned-verifier-confirmation-2026-09-28-a`;
- surface version: `learned-verifier-confirmation-wrappers-v1`;
- corpus SHA-256: `c08068e7c68d466b04c96433abd17a6b5da62eaa47969b536f8551ed9db201c6`;
- normalized exact overlap with original tuning DEV: 0;
- distinct from failed #270 seed/surface: yes;
- failed #270 artifact read or used: no.

Fresh result:

- supported exact: 952/1152 = 82.6389%;
- near-domain rejection: 537/576 = 93.2292%;
- OOD rejection: 72/72 = 100%;
- false-route: 39/648 = 6.0185%;
- combined p95: 252.77 ms;
- authority violations / errors: 0 / 0.

Per-language supported exact ranged from 75.00% on German to 89.06% on mixed. The worst unsupported-family rejection was `support.family_1` at 27.78%, but this confirmation set is not tuning evidence and cannot be used for targeted repair.

Decision: rejected.

Interpretation:

> Grouped OOF validation reduced ordinary random-split leakage, but the learned geometry boundary still captured development-surface regularities rather than a sufficiently invariant semantic notion of endpoint capability.

The #287 stopping rule is active:

- do not tune threshold on the fresh set;
- do not add route/family exceptions;
- do not refit or increase learned-model complexity on the same tuning DEV;
- do not use fresh-confirmation rows or errors as training/feature-design evidence;
- do not generate calibration/blind evidence.

Provenance:

- source revision: `e5b10ee01ec23af6113c562b51e1db0c6d003d7a`;
- workflow: `36362105765`;
- artifact: `10946681188`;
- artifact digest: `sha256:e7695598b07d5a0f9757f62c04f74f09b03c201de2bbb3f7699f6d8f18059938`.

## 40. Resume checkpoint after #287

The 0.11 architecture-search evidence now supports a stronger conclusion:

1. BGE-M3 raw route ranking has sufficient capacity;
2. positive score gates are surface-fragile;
3. generic contradiction NLI does not represent missing capability;
4. fixed semantic prototype thresholds and relative ranks do not provide a safe open-set boundary;
5. a shallow learned verifier can pass grouped OOF but still fails zero-overlap fresh-surface confirmation;
6. further supervised complexity on the same DEV geometry is prohibited by the preregistered stopping rule;
7. #198 calibration/blind remains blocked and untouched;
8. the next architecture must use an externally pretrained semantic capability verifier whose capability judgment is learned independently of this benchmark.

The authority invariant remains unchanged:

> External semantic evidence may veto the locally registered raw winner, but it may never select a different route or create execution authority.


## 41. System One provider abstraction and direct Laya routing

After #287 closed learned development-geometry refinement, the research line moved to externally
pretrained typed decision models rather than training another classifier on the same 1,800-row DEV
surface.

### Provider infrastructure — #291 / PR #292

SchemaRouter already had direct `JevDecisionBackend` and `LayaDecisionBackend` integrations.
#291 generalized the Jev-compatible wire boundary instead of adding one class per new model family.

PR #292 merged a generic `SystemOneDecisionBackend` to main:

- compatible providers are configured by `base_url`, `model`, and `provider_name`;
- the provider receives only finite locally authorized option IDs;
- returned IDs are revalidated locally before confidence handling;
- malformed/non-finite confidence fails closed;
- `DecisionOption.metadata` and credentials are not forwarded into model decision state;
- `JevDecisionBackend` remains backward compatible as a thin specialization;
- no compatible provider can create endpoints, fields, arguments, policy, or execution authority.

The benchmark-side companion #297 / PR #298 also merged to main, making the shared decision-routing
benchmark model-neutral for System One-compatible providers. New compatible models can be
benchmarked by configuration rather than another code change.

### Direct full-catalog Laya — #293 / PR #294

A preregistered direct-routing diagnostic then tested whether Laya itself could replace the BGE route
authority over all 16 registered endpoints.

Protocol:

- `laya==0.3.11`;
- CPU;
- auto English/multilingual checkpoint routing;
- preload enabled, max_loaded=2;
- full 16-route catalog;
- no BGE retrieval;
- eight fixed confidence thresholds;
- failed #270/#287 fresh surfaces excluded.

Result:

- raw supported top-1: 692/1152 = 60.0694%;
- passing rules: 0/8;
- p>=0.50: 57.2917% exact / 27.0833% near rejection / 51.3889% OOD / 70.2160% false-route;
- p>=0.995: 24.0451% exact / 77.6042% near rejection / 97.2222% OOD / 20.2160% false-route;
- mean / p95 latency: 657.73 / 1041.43 ms;
- errors / authority violations: 0 / 0.

Raw supported top-1 by language:

- de 48.9583%;
- en 87.5000%;
- es 63.5417%;
- ja 55.2083%;
- ko 40.1042%;
- mixed 65.1042%.

Confidence did not solve the open-set boundary. Mean confidence was 0.8881 for correct supported
choices, 0.7087 for wrong supported choices, and 0.7132 for near-domain unsupported requests.

Decision: reject direct full-catalog Laya route authority. PR #294 was closed unmerged.

Provenance:

- source revision: `48e329ee949d0d7a42d93a7c06c7ecbc62edfedc`;
- workflow: `36365434284`;
- artifact: `10947876029`;
- artifact digest: `sha256:f361f12844cf1da0374ba345051f9c35a0f50c2735c5e7fc9f2b6dbe62d39add`.

This negative result does not reject Laya as a veto signal. Laya's native `noul` primitive is a
different semantic question from 16-way route choice.

## 42. Current resume point — external typed capability boundaries

Calibration/blind remains blocked and untouched.

Active experiments:

1. #289 / PR #290 — Qwen3 external semantic capability verifier
   - immutable BGE-M3 raw top-1 route authority;
   - Qwen3-Reranker-0.6B veto only;
   - no SchemaRouter verifier training;
   - eight fixed yes-probability thresholds.

2. #299 / PR #300 — pinned Kev-0.8B choice + noul
   - pinned Kev source and Hub model revisions;
   - 16 registered routes only;
   - native System One `choice` and `noul` in one request;
   - separate fixed choice-confidence and noul-capability rule families.

3. #301 / PR #302 — pinned Laya noul veto
   - BGE-M3 raw registered top-1 remains sole route authority;
   - Laya may only return native `P(true)` capability evidence for that winner;
   - `laya==0.3.11`;
   - exact Hub family revision `458d7563c5cab85ff9f7f6e06cf2dd166fb697e2`;
   - the workflow materializes the immutable Hub snapshot locally before model construction;
   - eight fixed global `P(true)` thresholds.

The current architectural hypothesis is now narrower:

> route ranking and open-set capability acceptance should remain separate concerns. High-capacity
> registered-route ranking may stay with BGE-M3, while externally pretrained typed decision models
> are evaluated as replaceable capability boundaries. Direct decision-model route authority is not
> assumed merely because a provider supports `choice`.

System One wire compatibility is infrastructure, not quality evidence. Every model/checkpoint still
requires the same frozen v4 gate and, if promoted, a new zero-overlap fresh-surface confirmation.

## 43. #289 / PR #290 — external Qwen3 capability verifier

The first externally pretrained reranker-as-capability-verifier experiment is terminal and rejected.

Frozen protocol:
- BGE-M3 raw registered top-1 remained sole route authority;
- verifier: `Qwen/Qwen3-Reranker-0.6B` at revision
  `e61197ed45024b0ed8a2d74b80b4d909f1255473`;
- no SchemaRouter verifier training;
- one fixed capability instruction;
- eight global yes-probability thresholds;
- verifier veto-only;
- failed #270/#287 fresh sets, calibration, and blind evidence excluded.

Result:
- raw BGE supported top-1: 88.4549%;
- passing rules: 0/8;
- p=0.50: 82.8993% exact / 77.9514% near rejection / 97.2222% OOD / 19.9074% false-route;
- p=0.98: 68.7500% exact / 97.3958% near rejection / 100% OOD / 2.3148% false-route;
- p=0.99: 62.7604% exact / 99.1319% near rejection / 100% OOD / 0.7716% false-route;
- p=0.995: 52.7778% exact / 100% near rejection / 100% OOD / 0% false-route.

Mean verifier P(yes):
- correct supported winner: 0.9266;
- wrong supported winner: 0.6271;
- near unsupported: 0.2325;
- OOD: 0.0417.

The semantic signal is real, but the upper tails overlap too strongly for one safe global boundary.

Runtime:
- Qwen single-request p95: 1864.44 ms;
- combined BGE + Qwen p95: 2059.42 ms;
- errors / authority violations: 0 / 0.

Decision: reject direct generic reranker yes/no gating. Quality failure means runtime optimization is not a valid rescue.

Provenance:
- source revision: `68e812ab5c72bd42664e21f8c9f62a760465cb03`;
- workflow: `36363863046`;
- artifact: `10947604859`;
- artifact digest: `sha256:4e89707dce04d37aece8e803e00751ea86fdd12e5fd9282531ccecc830a9c96c`.

The active external typed-decision paths are now #299 (Kev) and #301 (pinned Laya native noul).
#303 remains a preregistered top-K provider-neutral contingency and is not active yet.

## 44. Replaceable typed-decision candidate registry

The fast-moving Jev/System One ecosystem is tracked separately from core product code in
`benchmarks/system-one-candidate-registry.json`.

The registry records, for each discovery candidate:
- repository and license status;
- wire protocol or callable integration path;
- current benchmark status;
- model-family caveats;
- the frozen promotion gate and intake checklist.

Current verified discovery entries include Laya, Kev, Decis, LiteVar System One, AnyJev,
Bespoke Nimble, and System One Open.

This separation is intentional:

> model discovery is mutable research metadata; execution authority and provider contracts are stable product interfaces.

Wire-compatible models use `SystemOneDecisionBackend`. Non-wire typed models first enter through
`CallableDecisionBackend` / `--decision-callable`. A permanent model-specific core integration
is not required merely to test a new model.

Infrastructure supporting this policy is now merged:
- #291 / PR #292 — generic System One backend;
- #297 / PR #298 — generic System One benchmark CLI;
- #304 / PR #305 — arbitrary bounded decision callable benchmark path, merged as
  `c9678b95a6dc592a1c3b850a6aea8b1675ff94a4`;
- #306 / PR #308 — reusable third-party `schemarouter.decision_backends` entry-point
  discovery/loading, benchmark plugin selection, security documentation, and candidate-registry
  validation, squash-merged as `e782ebb87f80cdb2cefe5a716f77f546cd6309b1`.

The final extension hierarchy is:
1. System One wire-compatible provider → `SystemOneDecisionBackend`;
2. one-off bounded research adapter → `CallableDecisionBackend`;
3. reusable non-wire integration → explicit third-party entry-point plugin.

Discovery is metadata-only. Plugin code is imported only by exact trusted name; plugin execution is
not sandboxed, and local finite-option validation remains authoritative.

## 45. #301 / PR #302 — pinned Laya native noul veto

The winner-only Laya capability-boundary experiment is terminal and rejected.

Frozen protocol:
- BGE-M3 raw registered top-1 remained sole route authority;
- Laya was veto-only through native `noul`;
- `laya==0.3.11`;
- exact Hub family revision `458d7563c5cab85ff9f7f6e06cf2dd166fb697e2` was materialized locally before inference;
- eight fixed global P(true) thresholds;
- failed fresh surfaces, calibration, and blind evidence remained excluded.

Result:
- raw BGE supported top-1: 88.4549%;
- passing rules: 0/8;
- p=0.50: 83.2465% exact / 7.9861% near rejection / 8.3333% OOD / 91.9753% false-route;
- p=0.90: 5.2083% exact / 95.4861% near rejection / 91.6667% OOD / 4.9383% false-route;
- p=0.95: 1.5625% exact / 99.4792% near rejection / 100% OOD / 0.4630% false-route.

Mean P(true):
- correct supported BGE winner: 0.6842;
- wrong supported winner: 0.6214;
- near-domain unsupported: 0.6738;
- OOD: 0.7316.

OOD requests were scored more capable on average than correct supported traffic, so the current
Laya base checkpoints do not supply a usable capability-existence boundary for this workload.

Runtime:
- BGE p95 200.21 ms;
- Laya single-request p95 906.09 ms;
- combined p95 1098.75 ms;
- errors / authority violations 0 / 0.

Provenance:
- source revision `46af3c3d0156b7b7bfd40686aa5639571f91a936`;
- workflow `36367249147`;
- artifact `10948736462`;
- artifact digest `sha256:5f7876d2c8e9c4a33eed62c05ba4df2889ad922322daeb5424d5f11bb18ec738`.

### Consequence for staged top-4 Laya

The staged #310 branch used the same Laya P(true) signal. It was closed without executing the
manual research workflow. At p>=0.95, the first preregistered winner-only threshold satisfying the
canonical false-route gate, only 18 of 1,019 already-correct BGE winners survive. Even granting the
impossible best case that all remaining 133 supported rows are recovered from top-4 and exceed the
same threshold, exact is bounded by 151/1152 = 13.1076%. Taking max P(true) over four candidates
also cannot reduce unsupported acceptance relative to the winner-only candidate at the same
threshold.

#303 remains only as a provider-neutral top-K architecture contingency for a materially different
model/checkpoint. The only active model-quality experiment at this checkpoint is pinned Kev-0.8B
#299 / PR #300.

## 46. Current target-distance checkpoint — Kev active, AnyJev staged

The numeric 0.11 target remains:

- supported exact-route >= 85%;
- near-domain unsupported rejection >= 97%;
- OOD rejection = 100%;
- false-route <= 1%;
- authority violations / execution errors = 0;
- target p95 <= 250 ms.

An important distinction is now explicit:

> The target operating point has already been reached repeatedly on the tuning/development surface.
> The unresolved problem is preserving that operating point under independent surface shift.

Evidence:
- grouped-OOF/frozen learned verifier reached the target on DEV/same-corpus;
- #287 fresh confirmation then fell to 82.64% exact / 93.23% near rejection / 6.02% false-route;
- generic Qwen3 capability gating (#289) and pinned Laya native noul (#301) both failed to provide a safer surface-invariant boundary;
- direct Laya route authority (#293) was capacity-limited at 60.07% supported top-1.

So the research problem is no longer ordinary route-ranking accuracy. BGE-M3 already exposes
88.4549% raw supported top-1 capacity on the canonical DEV. The remaining bottleneck is a
replaceable open-set capability decision that can retain most of those correct winners while rejecting
unsupported requests with <=1% false routing.

### Active — #299 / PR #300 pinned Kev-0.8B

The only active model-quality run is Kev-0.8B native System One `choice+noul`.

Before inference:
- contracts passed;
- pinned Kev runtime installed;
- local server started successfully;
- canonical 1,800-case DEV SHA was verified;
- corpus audit passed.

The full 1,800-row typed-decision diagnostic is executing. No result-driven semantic changes are
permitted.

### Staged Kev composition — #314 / PR #315

A zero-new-inference Kev composition was preregistered before #299 result inspection.

- BGE-M3 raw registered top-1 remains sole route authority;
- the exact frozen #299 `supported_probability` is reused as veto-only evidence;
- exact #299 per-row Kev request latency is reused for combined latency;
- Kev route choice and choice confidence are ignored;
- no new Kev model call is allowed;
- eight fixed global thresholds are retained;
- the manual workflow requires the exact terminal #299 artifact ID and validates its source run, artifact name, case IDs, probabilities, latency, execution errors, and authority violations before composition.

This isolates a useful research question without adding another learned component:

> if Kev's own 16-way route choice is weak, is its independently emitted global support-membership
> probability still a useful open-set gate for the stronger BGE route authority?

The staging PR is #315. It must remain unexecuted until #299 is terminal.

### Staged fallback — #311 / PR #313 AnyJev L0

A second architecture is fully staged but not executed while Kev is unresolved:

- AnyJev source revision `45add301a7aa60ed3420c83d15c061e84e5bce61`;
- zero-label L0;
- content-free prior rather than evaluation-batch prior;
- Qwen3-0.6B pinned base revision;
- BGE raw top-1 remains sole route authority;
- AnyJev native `noul` is veto-only;
- eight fixed global thresholds;
- no L1/L2 fitting on SchemaRouter data;
- workflow is manual-dispatch only.

#312 was closed as a duplicate of #311 so the research line has one canonical fallback record.

Operationally, the framework is now prepared for rapid model replacement:
- Jev-wire-compatible engines use `SystemOneDecisionBackend`;
- arbitrary bounded models can enter through `CallableDecisionBackend` and the generic callable benchmark path;
- model discovery remains separate from stable execution authority.

### Precommitted Kev-family promotion policy

Before #299 terminal metrics were available, the cross-candidate selection rule was fixed:

1. complete #299 exactly as preregistered;
2. if #299 yields complete valid row-level `supported_probability`, run the already-staged #314
   offline composition even if Kev's own route choice fails;
3. compare only full-gate passers;
4. if both #299 and #314 pass quality and runtime, prefer #314 because it preserves the established
   BGE registered-route authority and keeps Kev veto-only;
5. if #314 fails but #299 passes, promote #299;
6. do not select from post-hoc language/route/family slices, prompt variants, or failed-fresh behavior.

This selection policy was committed before result inspection to avoid outcome-driven architecture choice.

## 47. Freeze and final-evaluation ownership

The end of architecture search now has an explicit ownership boundary.

### #197 owns architecture closure

A DEV candidate that meets the standing target does not immediately enter calibration.

#197 must first:
1. select the exact passing DEV rule;
2. freeze source, architecture, authority semantics, models, runtime, representations and threshold;
3. write a machine-readable freeze manifest;
4. validate the manifest against the standing target and authority invariants;
5. generate a NEW zero-overlap fresh confirmation surface distinct from #270 and #287;
6. run the frozen candidate once without semantic retuning;
7. update the manifest to `fresh-confirmed` only if the fresh target also passes.

PR #316 introduces the reusable freeze-manifest template, validator and protocol documentation.

### #198 owns only the final consumed evidence

#198 remains blocked until a validated `fresh-confirmed` manifest exists.

After that point it owns:
1. a NEW 900-case calibration corpus and one evaluation;
2. only after calibration passes, a NEW 1,800-case blind-final corpus and one evaluation.

Calibration and blind-final are consumed evidence. They are never recycled into tuning.

This removes an earlier procedural ambiguity where #198's title/body could be read as owning freeze/fresh
while the tracker simultaneously treated #198 as blocked until fresh confirmation. The canonical
sequence is now:

```text
architecture search
    ↓
DEV pass
    ↓
#197 exact freeze
    ↓
NEW zero-overlap fresh confirmation
    ↓
validated fresh-confirmed manifest
    ↓
#198 calibration
    ↓
#198 one-shot blind-final
```

No semantic change is allowed after freeze. A quality-pass/latency-fail candidate may undergo only a
preregistered runtime-only optimization with unchanged semantics, and that optimized runtime must
itself pass fresh confirmation before #198.

### Guarded staged-experiment activation

The staged fallback workflows no longer depend on a human UI click.

- #314 / PR #315 remains dormant until a terminal #299 artifact exists. It can be activated by
  committing `benchmarks/operation-routing-v4-bge-kev-noul-compose.activation.json` with
  `activate=true`, source workflow run `36366508183`, and the exact artifact ID. The workflow
  revalidates source-run and artifact identity before reading rows.
- #311 / PR #313 remains dormant until the Kev family is non-promotable. Its activation marker must
  declare `activate=true`, `after_issue=299`, and `reason="kev_family_non_promotable"`.

The workflow-definition commits themselves do not start model evaluation because push filters match
only the activation-marker paths. This keeps staging separate from evidence consumption while allowing
session-resume automation to proceed without manual Actions UI access.

### Freeze infrastructure merged — #316

PR #316 was squash-merged as `fad004cdfce8e40c2119d3758ab47332d52e6253`.

Main now contains:
- `benchmarks/operation-routing-production-targets.json` as the machine-readable 85/97/100/1 + 250 ms target;
- `benchmarks/operation-routing-freeze-manifest.template.json`;
- `scripts/validate_operation_routing_freeze_manifest.py`;
- validator tests covering target drift, authority drift, provenance, metric ranges, provider revision IDs, and GitHub artifact digests;
- `docs/research/operation-routing-freeze-protocol.md`.

The canonical ownership boundary is now enforced in documentation and machine-readable governance:
- #197 owns DEV qualification → exact freeze → NEW zero-overlap fresh confirmation;
- #198 begins only after a validated `fresh-confirmed` manifest and owns calibration → one-shot blind-final.


### Runtime parity infrastructure merged — #320

PR #320 was merged as `acaca1e14b2f387094100dde3e1186aa4520d01d`.

Main now contains `scripts/validate_routing_runtime_parity.py`, which compares a frozen reference
analysis with a runtime variant and rejects:
- case-set drift;
- selected-route drift;
- any execute/abstain threshold crossing;
- execution errors;
- authority violations.

It records max/mean/p50/p95 probability drift and the frozen reference boundary margin.
This is the mandatory gate for #318 runtime-only optimization. Any parity failure turns the runtime
variant into a new semantic candidate that requires a separate preregistered experiment.

### Kev CPU runtime terminated without quality evidence

#299 / PR #300 attempted pinned Kev-0.8B native `choice+noul` on GitHub-hosted CPU/fp32.

The run completed infrastructure setup but did not complete the 1,800-row diagnostic:
- workflow: `36366508183`;
- conclusion: `cancelled`;
- artifact: `10951921452`;
- artifact digest: `sha256:58d3c1b4aec1bb70eb2aa1747e3acd86278a16da45582930bb80dbca92f54ee0`;
- `analysis.json`: absent.

The server log shows correct-but-slow reference PyTorch fallbacks for causal convolution and gated-delta kernels. This exact CPU/fp32 runtime is terminal as an impractical execution path, but it is not negative model-quality evidence.

Consequences:
- #317 six-hour timeout retry retired unexecuted;
- #314/#315 frozen BGE+Kev composition closed because its required row-level source analysis does not exist;
- #313 AnyJev CPU execution retired before inference;
- future typed-decision work requires a preregistered runtime with a credible <=250 ms deployment path.

The research frontier returns to lightweight BGE-native/open-set evidence where latency is an architectural constraint from the start.

### Runtime parity infrastructure merged — #320

PR #320 was merged as `acaca1e14b2f387094100dde3e1186aa4520d01d`.

`scripts/validate_routing_runtime_parity.py` is the mandatory gate for any later quality-pass/runtime-fail optimization. It rejects case-set drift, route drift, execute/abstain threshold crossings, execution errors, and authority violations while recording probability drift and reference boundary margin.

## 47. Lightweight BGE composition becomes active frontier

The expensive autoregressive typed-decision path was retired for the CPU product target. The next
candidate reuses only previously measured lightweight evidence.

### #322 / PR #323 — offline composition PASS

Immutable source artifacts:
- #262 GTE-only rescue: workflow `36326745694`, artifact `10934337695`,
  digest `sha256:7881a3594ecdab6a242a946a60cfde14d64e3c452ec9d0956c9cfa75a1e0c748`;
- #275 negative-capability diagnostic: workflow `36352558325`, artifact `10942243493`,
  digest `sha256:a831a35098b546c8003435ea04927fb8767aab1435320823ba4763e0b6608ae1`.

Frozen composition:
- #259 strict BGE base;
- negative veto only on original base accepts at max-negative >=0.55 and advantage >=0.05;
- vetoed base accepts cannot enter rescue;
- exact #262 GTE-only route rules with rescue false budget 4;
- rescue only original base abstentions and only the same raw BGE winner.

Workflow `36379888054`, artifact `10951119927`,
digest `sha256:1e86c0ebd881ff98f73d30d65ea618ff4525ead164f7f8a0b04c4ccf98190303`.

Result:
- exact: 980/1152 = 85.0694%;
- near rejection: 572/576 = 99.3056%;
- OOD rejection: 100%;
- false-route: 4/648 = 0.6173%;
- authority/errors: 0/0.

This is a tuning-DEV offline artifact composition, not executable or generalization evidence.

### #324 / PR #325 — executable candidate

#324 freezes the exact #322 semantics and recomputes them from the models:
- BGE query embedding is shared between route scoring and negative prototypes;
- GTE is invoked only on original #259 base abstentions;
- the executable output must have exact row-level parity with #322;
- directly measured total p95 must be <=250 ms.

If #324 passes, the next step is no longer architecture search: create the #316 freeze manifest and
run a new zero-overlap fresh confirmation distinct from #270/#287.

### Lightweight executable candidate passes DEV — #324/#325

The offline #322 composition was executed directly in workflow `36380771103` at semantic source
`caca039aff1c7b2960d167196f883e3bcbc5d431`.

Artifact `10952711288`, digest
`sha256:4ad9d0cc76500dd8705e0db0f677a21e44dbebb74cc3a9ca097723eb453abdc3`.

Result:
- exact 85.0694%;
- near-domain rejection 99.3056%;
- OOD 100%;
- false-route 0.6173%;
- authority/errors 0/0;
- offline row-level parity mismatches 0;
- BGE p95 134.05 ms;
- conditional GTE p95 54.39 ms;
- end-to-end p95 176.94 ms;
- GTE invoked on 42.61% of rows.

This is the first current-cycle executable candidate to pass quality, authority/parity, and the standing
250 ms runtime gate simultaneously.

### Exact freeze and new fresh confirmation — #326/#327

The candidate was frozen with a machine-readable `frozen-dev` manifest. Representation digests and
the canonical production target validated successfully.

Before fresh execution, a new confirmation surface was preregistered:
- seed `operation-routing-quality-v4-lightweight-bge-gte-confirmation-2026-09-28-a`;
- surface `lightweight-bge-gte-operational-envelope-v1`;
- confirmation-only, not tuning-eligible;
- normalized exact overlap required to be zero against canonical DEV and deterministically regenerated
  #270/#287 fresh surfaces;
- frozen evaluator/manifest must be byte-diff clean against semantic source `caca039…`.

Active fresh workflow: `36382202178`.

### Lightweight candidate fresh confirmation — valid run 36382647406

The executable lightweight candidate from #324/#325 is frozen under #326/#327.

Frozen DEV:
- exact 85.0694%;
- near-domain rejection 99.3056%;
- OOD 100%;
- false-route 0.6173%;
- authority/errors 0/0;
- row parity 0;
- p95 176.9436 ms.

Fresh seed/surface were preregistered before scoring:
- seed `operation-routing-quality-v4-lightweight-bge-gte-confirmation-2026-09-28-a`;
- surface `lightweight-bge-gte-operational-envelope-v1`.

Two early runs were invalid infrastructure evidence only:
- `36382202178`: historical #270/#287 payload regeneration added current-only split metadata and failed contracts;
- `36382467222`: a split-marker test caught an implementation omission and failed contracts.

Neither run generated a fresh corpus artifact or model score.

Current valid run:
- workflow `36382647406`;
- head `b19d7b0255ee9717464b6fa65ce1ebdeaf58a1bd`;
- contracts PASS;
- historical #270/#287 corpus SHA reproduction PASS;
- frozen semantic diff check PASS;
- frozen DEV manifest PASS;
- new fresh generator/gate tests PASS;
- evaluate job queued.

No semantic parameter of the frozen candidate changed during the technical fixes.

## 47. #326 / PR #327 — lightweight BGE+GTE fresh confirmation failed

The executable lightweight candidate from #324/#325 passed canonical DEV at:
- exact 85.0694%;
- near rejection 99.3056%;
- OOD 100%;
- false-route 0.6173%;
- p95 176.9436 ms.

It was frozen without semantic retuning and evaluated once on a new confirmation surface:
- seed `operation-routing-quality-v4-lightweight-bge-gte-confirmation-2026-09-28-a`;
- surface `lightweight-bge-gte-operational-envelope-v1`;
- corpus SHA256 `7d960bb43924569eede34748acc95f5bcd2cc04f2b9f8e396ec59c495dd3e1ec`;
- normalized exact overlap = 0 against canonical DEV and regenerated #270/#287 surfaces.

Terminal fresh result:
- exact 977/1152 = 84.8090%;
- near-domain rejection 521/576 = 90.4514%;
- OOD 72/72 = 100%;
- false-route 55/648 = 8.4877%;
- authority/errors 0/0;
- end-to-end p95 278.3748 ms.

This is valid negative evidence, not a technical failure.

The exact candidate is terminated. The fresh corpus is permanently confirmation-only and may not be
used for threshold, route/language/family repair, prototype changes, rescue-rule changes, model
selection, calibration, or any other tuning.

Together with #270 and #287, this is the third independent demonstration that a candidate can look
strong on the canonical DEV while its open-set acceptance boundary degrades under request-surface
shift. The next architecture must be motivated from tuning-eligible DEV and registry-level operational
invariants rather than another refinement of DEV-fitted score geometry.

## 48. #328 / PR #329 — BGE-M3 multi-representation operation gate

After the valid #326 fresh failure, the next cycle stops refining DEV-fitted dense
acceptance geometry.

The repository history already contains negative evidence for:
- route-local scalar operation-fit thresholds;
- action-only MiniLM gating;
- winner-only BGE cross-encoder rejection;
- cross-encoder rescue;
- signed/negative dense prototypes;
- learned DEV-geometry verifiers;
- externally pretrained Qwen/Laya typed gates.

The new hypothesis changes representation rather than adding another threshold repair.

BGE-M3 natively exposes three retrieval representations:
- dense CLS embedding;
- sparse lexical weights;
- ColBERT-style token-level multi-vector interaction.

SchemaRouter's 0.11 BGE-M3 work before #328 used only the dense representation.

#328 preregisters:
- the same pinned BGE-M3 model/revision;
- dense schema/action fusion as the sole route authority;
- token-level ColBERT evidence against only the trusted endpoint action name +
  `operation_aliases`;
- sparse lexical evidence as diagnostic-only;
- no route-local acceptance threshold;
- no margin-threshold search;
- no second threshold dimension;
- exact row-level raw-winner parity against the frozen #259 artifact.

The four permitted ColBERT rule families are:
1. global route agreement only;
2. same-tool endpoint agreement only;
3. global agreement + one global winner-score threshold;
4. same-tool agreement + one global winner-score threshold.

Threshold families report only false-route budgets 0/6/12 on canonical tuning DEV.

Fresh #270/#287/#326 surfaces remain excluded from design and model selection.

Initial workflow runs `36384727564` and `36384796110` failed contract checks before model
evaluation and are invalid for quality conclusions. The first model-quality execution is
`36384892825`.



## 49. #328 / PR #329 — BGE-M3 ColBERT operation-contract gate rejected

Canonical workflow `36385740263` completed successfully at source
`4c72f2dd1939edb6ecf8415d620dbb5d58683fa0`.

Artifact:
- id `10955036349`;
- digest `sha256:6e6bfbd2cb352aba03e2d98683ae6967a64115f90a04cf49f74e7cd1ab76dde7`;
- canonical DEV SHA remained `fc085c58ed7c667d71024e60cf9e213e66da8f7b43f6e79551ed810a9e328216`;
- dense raw-winner parity mismatches: 0;
- authority violations / execution errors: 0 / 0.

Dense BGE-M3 raw supported top-1 remained 88.4549%, confirming that route-ranking capacity was unchanged.
The preregistered ColBERT operation-contract families did not produce a promotable open-set boundary:

- global agreement only: 82.5521% exact / 32.8125% near rejection / 64.5062% false-route;
- same-tool agreement only: 83.7674% exact / 7.4653% near rejection / 91.2037% false-route;
- global agreement + one global score threshold at the <=1% false-route budget: 38.6285% exact / 98.9583% near rejection / 100% OOD / 0.9259% false-route;
- same-tool agreement + one global score threshold at the same budget: 38.7153% exact / 98.9583% near rejection / 100% OOD / 0.9259% false-route.

No preregistered rule passed the standing 85 / 97 / 100 / 1 quality gate.

The measured full-path p95 was 398.6848 ms. PR #331 was opened before result inspection because sparse scoring is diagnostic-only. Recomputing the executable latency from the already persisted per-row components
(`encode + dense scoring + ColBERT scoring`) gives **398.6149 ms p95**, so excluding sparse diagnostics does not change the terminal decision and no rerun is required.

A post-hoc sparse-only diagnostic was also checked strictly as non-promotion evidence. At the <=1% false-route budget it preserved only 12.6736% supported exact-route accuracy. This is retained solely to prevent repeating the same BGE-M3 sparse representation as another promotion attempt.

Decision: reject and close the BGE-M3 native ColBERT/sparse operation-contract representation for this cycle. Do not add a post-hoc second threshold, route-local exception, margin search, rank-2 fallback, or pseudo-route to repair it.

#198 remains blocked. The next behavior-changing architecture, if any, must be separately preregistered using only tuning-eligible DEV plus registry-defined operational semantics; failed fresh-confirmation surfaces #270/#287/#326 remain permanently non-tuning.

## 50. #332 / PR #333 — registry-self-calibrated alias envelope rejected

After ColBERT failed, #332 tested whether trusted registry metadata itself could define a
surface-independent operation boundary without another query model or a labeled-DEV threshold.

Frozen design:
- BGE-M3 raw registered top-1 remained the sole route authority;
- the same normalized query embedding was reused for route ranking and the gate;
- alias banks contained only normalized endpoint name + trusted `operation_aliases`;
- route margin/cohesion floors were derived only from leave-one-out alias self-cohesion and
  same-tool sibling separation;
- exactly four fixed families A/B/C/D were evaluated;
- #270/#287/#326 fresh surfaces were excluded.

Canonical evidence:
- workflow `36388641609`;
- source `fa091f43296eb1ca680f39921010482275bb4cda`;
- artifact `10955736650`;
- digest `sha256:21166d8c10009401b34380e6e24ddbcdcf4ec06c760d86b4d19eaf99930a1e1e`;
- canonical DEV SHA `fc085c58ed7c667d71024e60cf9e213e66da8f7b43f6e79551ed810a9e328216`;
- dense raw supported top-1 88.4549%;
- dense parity / authority / execution errors 0 / 0 / 0;
- routing-path p95 198.0714 ms.

Results:
- A sibling contrast: 84.8958% exact / 11.9792% near rejection / 18.0556% OOD / 87.3457% false-route;
- B registry margin: 72.3090% exact / 24.1319% near rejection / 68.0556% OOD / 70.9877% false-route;
- C registry cohesion: 24.3056% exact / 98.4375% near rejection / 100% OOD / 1.3889% false-route;
- D joint envelope: 23.5243% exact / 98.4375% near rejection / 100% OOD / 1.3889% false-route.

No fixed family passed the standing 85/97/100/1 target.

The result is structurally informative. Same-tool alias contrast is useful for operation preference but
does not establish capability membership: unsupported requests usually still prefer one registered
sibling. Conversely, the alias self-cohesion floor becomes a strong rejection mechanism only by
demanding supported natural-language requests look nearly as internally coherent as curated registry
aliases, which collapses supported recall.

The representation is terminal. Per preregistration, it is not repaired with a
DEV-fitted score threshold, a second threshold dimension, route/language/family exceptions, or failed
fresh-confirmation rows.

The 0.11 cycle now has no active candidate. #198 remains blocked. A subsequent behavior-changing
hypothesis must provide a materially different source of open-set capability evidence rather than
another transformation of the same dense score/alias geometry.


## 51. #336 / PR #337 — threshold-free BGE/GTE consensus rejected

The final lightweight 0.11 hypothesis isolated cross-backbone route agreement without adding
another score threshold.

Frozen rule:
- BGE-M3 #259 raw registered top-1 remained the sole execution authority;
- GTE multilingual base used the previously frozen 0.25/0.75 schema/action representation;
- execute the BGE winner only when GTE raw top-1 exactly equals the BGE raw top-1;
- otherwise abstain;
- no score, margin, route-local, language, or family threshold;
- no rank-2 fallback, pseudo-route, calibration, blind data, or failed fresh evidence.

Canonical evidence:
- workflow `36390328100`;
- source `d25f427569fc4419a72963c6f31994fa170805f6`;
- artifact `10956013271`;
- digest `sha256:56fad4070ef97782f398a259192bc5ad0e4ec3ac7d6c0fd4d531f17bfc89ccf9`;
- canonical DEV SHA `fc085c58ed7c667d71024e60cf9e213e66da8f7b43f6e79551ed810a9e328216`;
- authority violations / execution errors 0 / 0.

Raw ranking capacity remained high:
- BGE-M3 supported top-1 88.4549%;
- GTE supported top-1 89.1493%.

However, route agreement was not an open-set capability signal:
- BGE/GTE route agreement over all rows 72.7222%;
- supported exact 937/1152 = 81.3368%;
- near-domain rejection 251/576 = 43.5764%;
- OOD rejection 59/72 = 81.9444%;
- false routes 338/648 = 52.1605%;
- wrong-supported accepted 34.

GTE query+scoring p95 was 83.3360 ms and the frozen #259 BGE direct p95 was
132.1553 ms, but no combined executable latency claim was made because quality failed first.

Interpretation:

> Agreement between two strong closed-set rankers measures selection confidence more than
> capability membership. When an unsupported request is topically close to a registered operation,
> both rankers can confidently choose the same wrong executable destination.

The exact consensus rule is terminal. No post-result score/margin threshold is added.

## 52. 0.11 operation-routing-quality-v4 — terminal cycle decision

The 0.11 cycle closes without a promoted production-target candidate.

The standing target was:
- supported exact >=85%;
- near-domain unsupported rejection >=97%;
- OOD rejection =100%;
- false-route <=1%;
- authority/execution errors =0;
- executable p95 <=250 ms.

One executable DEV candidate (#324/#325) met the complete target:
- exact 85.0694%;
- near rejection 99.3056%;
- OOD 100%;
- false-route 0.6173%;
- p95 176.9436 ms.

The exact frozen candidate then failed its new zero-overlap fresh confirmation (#326/#327):
- exact 84.8090%;
- near rejection 90.4514%;
- OOD 100%;
- false-route 8.4877%;
- p95 278.3748 ms.

That failure is the decisive promotion result. Calibration and blind-final are not run.

After the fresh failure, the cycle tested materially different non-fresh-derived representations rather
than repairing from confirmation rows:
- BGE-M3 ColBERT/sparse operation evidence (#328/#329): terminal reject;
- registry-self-calibrated alias envelope (#332/#333): terminal reject;
- threshold-free BGE/GTE consensus (#336/#337): terminal reject.

Combined with the earlier negative lines (positive dense thresholds, NLI, signed/negative prototypes,
rank heuristics, learned DEV verifier geometry, Qwen/Laya/Kev/AnyJev typed-decision paths, and
cross-encoder variants), the current canonical DEV has been mined far enough. Continuing to add
thresholds or hand-written exceptions would increase selection bias without supplying independent
evidence.

The 0.11 research conclusion is:

1. Registered-route ranking capacity is sufficient. BGE-M3 raw top-1 is ~88.45%.
2. Open-set capability membership is the unresolved problem.
3. A DEV pass is not sufficient evidence. Three independent lines degraded under fresh request
   surfaces, and the strongest current executable candidate failed the formal fresh gate.
4. The safe stopping action is to close the architecture-search cycle, not tune against consumed
   evidence.
5. #198 calibration/blind-final stays unexecuted because its entry requirements were never met.

The robust #259 profile remains a useful conservative reference:
- exact 83.7674%;
- near rejection 98.9583%;
- false-route 0.9259%;
- planner p95 ~134.95 ms.

It is not relabeled as a production-target pass because it misses the 85% exact requirement.

Any successor cycle must introduce a materially new source of capability evidence and a new
preregistered protocol. It may not tune on #270/#287/#326, revive terminal 0.11 families with
post-hoc thresholds, or convert compatibility evidence into quality evidence.


## 53. #338 / PR #341 — arbitrary-tool registry-compiled verifier rejected

After the 0.11 architecture-search cycle closed, #338 tested a product-level generalization
constraint that earlier benchmark-specific work did not fully exercise:

> can the same capability compiler and verifier work when a user registers previously unseen native
> ToolSpec, OpenAPI, or MCP tools, without route-specific retraining?

The experiment was preregistered before execution.

Design constraints:
- native ToolSpec, OpenAPI, and MCP had to compile into the same provider-neutral capability IR;
- endpoint names could be opaque and `operation_aliases` could be empty;
- route IDs, fixed endpoint counts, and benchmark-domain keyword tables were forbidden as learned
  features;
- JSON datatype/shape, semantic IDs, source units, explicit unit normalization, and qualifiers were
  preserved as registered deterministic metadata;
- BGE-M3 raw top-1 remained the sole route authority;
- the learned component was veto-only, with no rank-2 fallback or pseudo-route;
- newly registered routes could not require route-specific retraining.

Canonical execution:
- workflow `36393153612`;
- source `ef75100abc1bb03a80ef2d7cfbd9d463accfb623`;
- artifact `10957952613`;
- digest `sha256:2a24d50c563ee872fdad8d498e30ab7a55e6c82e0650bf27ac4bfbadc4fc4269`.

Results:

| Surface | Exact | Near reject | OOD | False-route | Correct raw-winner retention | p95 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Canonical DEV (1,800) | 5.0347% | 100% | 100% | 0% | 5.6919% | 196.93 ms |
| Registration holdout (228) | 2.0833% | 100% | 100% | 0% | 2.4590% | 192.85 ms |

Authority violations and execution errors were zero, and canonical raw BGE parity had zero
mismatches.

Interpretation:

The provider-neutral typed capability/data-contract compiler worked as infrastructure, including
arbitrary native/OpenAPI/MCP registration and preservation of datatype/unit/qualifier metadata.
The generic synthetic learned veto did not. It achieved perfect rejection by rejecting nearly every
valid supported request.

Decision: terminal reject without label-driven repair, exactly as preregistered.

PR #341 was closed without merge. The infrastructure lesson is retained; the learned-veto quality
claim is not promoted into the library default.


## 54. #347 / PR #348 — query-first typed frame preserves supported routes but under-rejects unsupported

The first 0.12 successor experiment stopped comparing query/endpoint similarity for
capability membership.

Preregistered architecture:

```text
query
  -> registry-independent explicit request frame
  -> frozen BGE-M3 raw top tool/domain anchor
  -> deterministic within-tool contract compatibility
  -> unchanged BGE-M3 ranking inside the compatible endpoint set
  -> route or NO_ROUTE
```

Unlike #338, there was no learned binary veto, probability threshold, route-local threshold,
pseudo-route, or post-ranking rank-2 fallback.

A new 0.12 data protocol was frozen before scoring:
- development: 936 cases, SHA
  `79a7cb9672e6633739e0acd08882019f5cfeff479df103f8199aabacb8501a9f`;
- registration confirmation: 1,008 cases, SHA
  `15587c646d64b4f3462127742c05d59092938f68a4c047b731e9a8c78c0eb673`;
- both catalogs used new tool identities and native/OpenAPI/MCP registrations;
- the confirmation corpus was generated and frozen before DEV scoring.

DEV evidence:
- workflow `36404647843`;
- source `ef0e0a567f12129bf9f4b003d13f9f6e9679a216`;
- artifact `10962450383`;
- digest
  `sha256:74df3e068421bb2c551a30c2b5c5cdb9547e17066bf3f4ce7f8154c11690849c`.

Results:
- supported exact 97.2222%;
- raw supported exact 96.7593%;
- raw supported tool accuracy 99.5370%;
- near-domain unsupported rejection 70.3704%;
- OOD rejection 95.8333%;
- false-route 25.9921%;
- p95 179.526 ms;
- authority violations / execution errors 0 / 0.

This is almost the mirror image of #338. The query-first structural filter preserves valid
supported requests extremely well and can correct some endpoint choices, but the high-precision
lexical request frame leaves too many unsupported requests as structurally unknown. So those requests
fall back to the raw BGE domain anchor and still receive an executable destination.

Decision: terminal reject on DEV. No row-driven lexicon expansion, per-language patching, or
route-specific exception is allowed. The frozen 1,008-case confirmation corpus remains completely
unscored.

The architectural lesson is useful: the next materially new signal should improve **query-side
operation-frame coverage** without returning to endpoint-similarity membership thresholds and
without sacrificing the high supported-route retention demonstrated here.


## 55. #349 / PR #352 — flat semantic action ontology rejected

After #347 showed that explicit lexical request frames preserve supported routing but miss too many
unsupported operations, #349 replaced the surface lexicon with a registry-independent multilingual
semantic action ontology.

The request was projected onto one generic action class by frozen BGE-M3 prototype similarity, then
that action was used as a deterministic within-tool capability constraint. No learned veto,
probability threshold, route-local threshold, pseudo-route, or cross-tool fallback was allowed.

A new pair of corpora was generated and frozen before scoring:
- DEV: 504 cases, SHA
  `1a497bcd36192913840d7ecd4c6bed714c908468baed6f2b0b9f4367bf57ffc6`;
- confirmation: 552 cases, SHA
  `548fe42da09e7c8dc89530c43d409db05618f57a39c277fca27aebe79b6802b9`;
- confirmation was never scored.

DEV evidence:
- workflow `36406845612`;
- source `38ee7557565983746e33741897e6168bf4f35643`;
- artifact `10962178834`;
- digest
  `sha256:de687d850e619cb1ce143648ef6fe21950f6a395a33bc6835a7564b24f9a03a1`.

Results:
- supported exact 44.9074%;
- raw BGE supported exact 77.3148%;
- raw BGE supported tool accuracy 94.4444%;
- near-domain unsupported rejection 56.4815%;
- OOD rejection 100%;
- false-route 32.6389%;
- p95 197.549 ms;
- authority violations / execution errors 0 / 0.

The flat semantic ontology was terminally rejected. The key lesson was not that an ontology
is useless, but that a noisy semantic label must not receive hard endpoint-removal authority.

## 56. #354 / PR #357 — hierarchical executable-capability ontology rejected as a hard filter

#354 made the ontology explicit and hierarchical rather than flat.

The generic ontology separated:
- read: search / retrieve / list;
- mutate: create / update / delete / cancel / refund;
- transfer: send / share;
- transform: export / translate / summarize / compare / merge;
- control: restart / execute;
- predict: forecast;
- non-tool: compose / explain / calculate / chat.

Request-side root/leaf evidence came from fixed multilingual contrastive prototypes. Endpoint
root/leaf facts came from trusted registry metadata, with HTTP/read-only/destructive metadata taking
precedence over semantic inference.

The freeze completed before scoring:
- freeze workflow `36408654108`;
- frozen ontology/corpus source
  `9777e1c76df27bff38cb3060d672d4f8baf65334`;
- freeze artifact `10963536169`;
- freeze digest
  `sha256:ac8bb723e8def4dca002c21662504ccbc169d02d2bdcc72905d621710f128bd2`;
- DEV: 564 cases, SHA
  `3731ade0c1cfc69fbf234c00e9090a35b8fca5340af98077e1a18f98782d2a4a`;
- confirmation: 576 cases, SHA
  `1e965111a7835af002b397d0be6b4776ea2a9295f417991f5b7733f79f23a24e`;
- confirmation remained unopened.

DEV evaluation:
- workflow `36408861468`;
- evaluated source `250845bba058a704ab50cdde43326cc1e5c26d62`;
- the workflow first verified all frozen ontology/corpus files were byte-identical to the frozen
  source;
- artifact `10964025921`;
- digest
  `sha256:40eb58bc091380257409d93b662bbfbfa9b966e8c752b9a63df04b68237f7e2b`.

Results:
- supported exact 30.4167%;
- raw BGE supported exact 85.4167%;
- raw BGE supported tool accuracy 100%;
- near-domain rejection 68.6508%;
- OOD rejection 88.8889%;
- false-route 26.8519%;
- p95 164.328 ms;
- authority violations / execution errors 0 / 0.

This was a strong architectural negative result. On this new DEV, the raw BGE ranker already met the
supported exact target and identified the correct tool for every supported case. The hierarchical
ontology hard filter then destroyed that good signal.

Decision: terminal reject without row-driven repair.

The resulting design rule for the next candidate is sharper:

> keep ontology as structured capability metadata and negative evidence, but do not let noisy
> semantic ontology projection select, rerank, or remove supported endpoints.


## 57. #358 / PR #360 — asymmetric ontology veto preserves supported winners but lacks recall

After #347, #349 and #354, the ontology was removed from positive route-selection authority.

#358 preregistered a stricter authority separation:
- frozen BGE-M3 raw top-1 is the sole positive route selector;
- the anchored tool's registered capability leaves define the finite authority set;
- the explicit parser, BGE ontology projection and an independent pinned multilingual MiniLM
  projection may only provide negative evidence;
- ontology can return `NO_ROUTE`, but can never switch, rerank or select another endpoint;
- the veto requires exact unsupported-leaf agreement under a fixed rule;
- no similarity, margin, confidence, route-local or learned threshold is used.

Frozen corpus evidence:
- freeze run `36411756496`;
- freeze source `e29b6e0006dd64bab31c613b97ea68de8c2931f6`;
- freeze artifact `10965015475`;
- digest `sha256:1d93e8441224051ce63aacc050eb6cd99979f613945e5a21419abc5aa65b0a39`;
- DEV: 552 cases, SHA256
  `e2f3ab0f93584d896f401c94200200d7a39c8f00a4983addd4ebc8889757ee07`;
- confirmation: 552 cases, SHA256
  `bbe4984681472ad5ffe1ed881fd2b92937668fed453a45d6afbba587ffa376e8`.

DEV workflow `36412029437` at source
`759359882c3deb1be310fc540bbb1780b1543885` produced artifact `10964703106`,
digest `sha256:6b25f94698650175475a4c7339526298e7582b1be43366a8c695cfeecdcf9aaa`.

Result:
- supported exact 96.0526%;
- raw supported exact 96.0526%;
- raw tool accuracy 99.5614%;
- raw-correct winner veto rate 0%;
- near-domain rejection 26.5873%;
- OOD rejection 84.7222%;
- false-route 60.4938%;
- veto precision 99.2248%;
- veto recall 39.5062%;
- positive route switches 0;
- p95 236.0203 ms;
- authority/execution errors 0/0.

Interpretation:

The authority design worked: ontology evidence can be made safe as a negative-only signal, and this
exact rule vetoed no raw-correct supported winner. The failure is recall, not precision. Requiring
independent evidence to agree on the exact same unsupported leaf is too strict for open-set
membership.

Decision: terminal reject of the exact agreement rule. No failed row is used to add phrases,
rewrite prototypes, tune thresholds or create route-specific exceptions. The already-generated
confirmation corpus remains unopened.


## 58. #363 / PR #364 — capability-set membership consensus improves recall but remains insufficient

#363 kept the authority rule established by #358: frozen BGE-M3 raw top-1 was the sole positive
route selector, and ontology evidence could only veto to `NO_ROUTE`.

The only behavioral change was the unit of semantic agreement. Instead of requiring BGE and MiniLM
to name the exact same unsupported leaf, each signal was mapped against the anchored tool's finite
registered capability set as `SUPPORTED`, `OUTSIDE_SET`, or `UNKNOWN`.

The rule was preregistered before creating a new evaluation surface:
- explicit `OUTSIDE_SET` plus at least one semantic `OUTSIDE_SET` -> veto;
- explicit `UNKNOWN` plus both semantic encoders `OUTSIDE_SET` -> veto;
- explicit `SUPPORTED` -> preserve raw BGE route;
- otherwise preserve;
- no threshold, learned head, endpoint filter, rank-2 fallback, pseudo-route, or positive rerank.

A new native/OpenAPI/MCP pair was frozen before scoring:
- freeze run `36415762115`;
- frozen source `a1a9eb20622dd8a47082ca8fa5cd02c52d27e653`;
- freeze artifact `10966724823`;
- digest `sha256:d957f82e29bdec0723fb0dda0622098563354a8ecdb45e8108b4633bc3bc6915`;
- DEV: 552 cases, SHA `1d3d18975b33156d97f3b4fd518158cba418c449fae01e864977f8bdf77b5e62`;
- confirmation: 552 cases, SHA `ba92c3c25da3601bd50f580dcfaf7b512ec2e26971e10ec9e501bb59cbf35d37`;
- typed numeric/unit examples were present (`W/m2`, `L/s`);
- confirmation remained unopened.

DEV evaluation:
- run `36415951667`;
- source `f198f896c44860c27ce14b4c88200096ef0b754f`;
- artifact `10967871097`;
- digest `sha256:799006f7d69b94a29bfa0cfc62384ca2a8640cba668ac69e04ab2702a08f3f93`.

Results:
- supported exact 86.4035%;
- raw BGE supported exact 94.2982%;
- raw BGE tool accuracy 99.5614%;
- near-domain rejection 54.7619%;
- OOD rejection 97.2222%;
- false-route 35.8025%;
- veto precision 91.2281%;
- veto recall 64.1975%;
- raw-correct winners vetoed 18 / 8.3721%;
- positive route switches 0;
- p95 249.7303 ms;
- authority/execution errors 0 / 0.

Compared with #358, set membership increased veto recall substantially, but the same projection family
still could not provide enough open-set coverage and began harming correct supported winners.

Decision: terminal reject. No membership-combination diagnostic or failed row is used to tune
another rule on this DEV, and the frozen confirmation is not opened. The next candidate must use a
materially different semantic membership evidence source.


## 59. #371 / PR #372 — external multilingual zero-shot OUTSIDE-label membership rejected

#371 introduced a materially different semantic evidence source after the BGE/MiniLM ontology-vote
family was closed. Frozen BGE-M3 remained the sole positive route selector, while an independently
pretrained multilingual zero-shot classifier could only preserve that winner or veto to
`NO_ROUTE`.

For each anchored tool, the candidate label set consisted of:
- one fixed descriptive label for every registered operation leaf;
- one generic `request an operation outside the registered capabilities of this tool` label.

No classifier output could select, rerank, filter to, or fall through to another endpoint. No
probability/margin threshold or SchemaRouter fine-tuning was used.

The pair of V5F corpora was frozen before scoring:
- freeze run `36419226642`;
- frozen behavior/corpus source `6c02c313a022740100377ead5890fd1f0d782978`;
- freeze artifact `10968721554`;
- digest
  `sha256:1820bafd0e5c745e7175e75cca32e6e27f20a7b3bafd53b7138a138d11429a62`;
- DEV: 552 cases, SHA
  `64a89e96a2beaf90e9b44febdef033a2ec9a17c60459c909a0718b759dd9baae`;
- confirmation: 552 cases, SHA
  `9beebb5957f1bfd264a14349582c74ad9b15627c6530324f792d3e1d249ecbe9`;
- typed unit-bearing fields were preserved, including `degC -> K` and `kPa -> Pa`;
- confirmation remained unopened.

The external model was pinned at runtime from tag `v1.1` to immutable revision
`d8c48cf2e7c7640ad5bbb379bdb2f72f5ebde7c4`.

DEV evaluation:
- workflow `36419512215`;
- evaluated source `5e6dde0c3860ff46f0961c74233d7196e6c86f59`;
- artifact `10968782843`;
- digest
  `sha256:fe53e28362d9d9d78573e68f41bcb1cce6eab0c26294f1b73a599d36fafbb6d5`.

Results:
- supported exact 93.4211%;
- raw BGE exact 93.8596%;
- raw BGE tool accuracy 99.1228%;
- near-domain rejection 1.5873%;
- OOD rejection 2.7778%;
- false-route 98.1481%;
- veto precision 85.7143%;
- veto recall 1.8519%;
- one raw-correct supported winner vetoed (0.4673%);
- zero positive route switches / authority violations / execution errors;
- external classifier p95 93.1540 ms;
- end-to-end p95 274.5241 ms.

The external model was fast enough to be operationally interesting as a bounded semantic verifier,
but the generic OUTSIDE catch-all almost never beat the concrete supported labels under native
single-label normalization. The failure is semantic formulation, not only runtime.

Decision: terminal reject. No label wording, hypothesis-template, threshold, language rule, or
route-local repair may use this DEV. The frozen confirmation surface remains unopened.

The next materially distinct hypothesis is to condition the actual anchored tool capability set
directly in a binary entailment/not-entailment question.


## 60. #374 / PR #375 — set-conditioned binary entailment collapses to universal rejection

#374 tested the direct set-conditioned NLI formulation suggested by #371's failure.

The architecture remained authority-safe:
- frozen BGE-M3 raw top-1 was the sole positive route selector;
- the anchored tool's registered capability leaves were compiled from trusted schema metadata;
- one sequence-pair NLI judgment received the raw query as premise and the finite registered
  capability set as hypothesis;
- entailment preserved the raw route; not-entailment vetoed to `NO_ROUTE`;
- no threshold, calibration, language rule, rank-2 fallback, pseudo-route, or positive reranking.

The new V5G corpora were frozen before scoring:
- freeze workflow `36421851941`;
- frozen behavior/corpus source `c456214daba7d98d6822f99bd74aa50fb887a8f4`;
- freeze artifact `10969746736`;
- digest `sha256:d52241d155c043ae4398a471a25b9ce35700229d46377da5f86a41e02b851d8d`;
- DEV: 552 cases, SHA
  `f24d874afb5c248ff0ece71da27f89fd4d442e745e6e610269a9300c1851c034`;
- confirmation: 552 cases, SHA
  `214d59f25e755c73d15d9d6814363604ff88d5f7f6e66a93e1c0f133b0633332`;
- confirmation remained unopened.

DEV evaluation:
- workflow `36422168708`;
- evaluated source `e61058d0aa31819bf99b182f4bd5947dd0d11fab`;
- artifact `10970342078`;
- digest
  `sha256:4584f55a67b6744ba8ba3454290a2acb5e7cee1ce58695a0362618ab07f7faf8`.

Results:
- supported exact 0.0000%;
- raw BGE supported exact 92.5439%;
- raw BGE tool accuracy 99.5614%;
- near-domain rejection 100%;
- OOD rejection 100%;
- false-route 0%;
- entailment / not-entailment decisions 0 / 552;
- raw-correct winners vetoed 211 / 100%;
- veto precision 58.6957%;
- veto recall 100%;
- NLI p95 56.1598 ms;
- end-to-end p95 254.5495 ms;
- positive route switches / authority violations / execution errors 0 / 0 / 0.

This is the semantic mirror image of #371. The multiclass OUTSIDE formulation almost never rejected;
the aggregate set-entailment formulation rejected everything. The external model itself is fast
enough to remain technically interesting, but neither extreme formulation provides a useful
open-set capability-membership boundary.

Decision: terminal reject. No hypothesis rewrite, threshold, language-specific rule or
failed-row-driven repair is permitted. The frozen confirmation surface remains unopened.

The successor must change the semantic decomposition itself rather than interpolate between these
two outcomes with post-hoc thresholds.


## 61. #377 / PR #379 — independent registered-leaf entailment improves recall but over-vetoes support

#377 replaced the failed aggregate set-entailment sentence with one independent NLI pair per
registered capability leaf under the BGE-anchored tool.

The frozen authority rule stayed unchanged:
- BGE-M3 raw top-1 remained the sole positive selector;
- every registered leaf received one fixed generic hypothesis;
- all hypotheses for a query were evaluated in one batch;
- any entailment preserved the raw BGE winner;
- zero entailments vetoed to `NO_ROUTE`;
- NLI could not select, rerank, replace, or filter to another endpoint;
- no confidence, probability, margin, language, route, or learned threshold was used.

Freeze evidence:
- workflow `36424007584`;
- frozen behavior/corpus source `b545999528b17a2782c76e6b6e546703b7b11da5`;
- artifact `10970381458`;
- digest `sha256:48afeead8687eb7d28aa2fce30485a017a368b2b5119b1278a162f7badad45af`;
- DEV: 552 cases, SHA `c68bf11e52f960a7c8600d9d36b7fe13ab0b7b6e215a87f5b2bcffb783a67310`;
- confirmation: 552 cases, SHA `ac4be0d6febda04fea60ae351691dfeebb932c1ec1161f14cf7754c44f49eefd`;
- confirmation remained unopened.

DEV evaluation:
- workflow `36424336147`;
- source `a872c9602dcad959ea1bf10f16a052592754d4ae`;
- artifact `10971456253`;
- digest `sha256:153781b690336a863de5a4ad2f2a7cb0793a01718d5d6c053bcd99a3dd66a937`.

Results:
- supported exact 45.6140%;
- raw BGE exact 96.4912%;
- raw BGE tool accuracy 100%;
- near-domain rejection 71.0317%;
- OOD rejection 95.8333%;
- false-route 23.4568%;
- veto precision 66.8464%;
- veto recall 76.5432%;
- raw-correct winners vetoed 116 / 52.7273%;
- NLI batch p95 79.5343 ms;
- end-to-end p95 278.0917 ms;
- positive route switches / authority violations / execution errors 0 / 0 / 0.

The experiment shows that decomposing the finite capability set into independent leaf judgments is
meaningfully better than one aggregate set-membership sentence, but independent binary argmax is
still too brittle as a hard membership veto. Supported queries frequently receive zero entailment,
causing more than half of raw-correct winners to be rejected.

Decision: terminal reject. No failed-row text, language slices, confusion pairs, score
distributions, hypothesis rewrites, thresholds, margins, or vote rules may be used to repair #377.
Its confirmation corpus remains unopened.

The already-preregistered #378 experiment is the next admissible step: compare the maximum
entailment evidence among registered leaves with the maximum entailment evidence among
counterfactual leaves while preserving BGE as the sole positive route selector.


## 62. #378 / PR #380 — pairwise registered-vs-counterfactual NLI remains below target

#378 was preregistered before #377 DEV was opened. It evaluated all 22 fixed generic operation
hypotheses independently in one batch, then compared the maximum entailment score among the
BGE-anchored tool's registered leaves with the maximum score among counterfactual tool/non-tool
leaves.

The authority rule remained asymmetric: counterfactual evidence could only veto to `NO_ROUTE`;
frozen BGE-M3 raw top-1 remained the sole positive route selector.

Freeze:
- workflow `36424651535`;
- source `7fccdb1eccb5f08d31ca87c798fc5f9f52a119f3`;
- artifact `10971625459`;
- digest `sha256:9a0f4cfa2f5fe3a47f81374a9867dd618ebe84fa17cbb0a09c2c8a2cd2503577`;
- DEV SHA `75c7bab67de9c533df08ab5a76f7ce5e49acd92d3737f70b8dcfa50222c6abbd`;
- confirmation SHA `caee6eb89b07e948b42130e4bb1ea3f6c1b4088fc76137f0d8e7cb394f8c6007`;
- confirmation remained unopened.

DEV:
- workflow `36424971822`;
- source `02aeefd4656f5b61a948142dfba74f51207bd979`;
- artifact `10970443611`;
- digest `sha256:8f24db27938f6924723d2088fd5ddc6811db433d0ceaf5b5e23c2412422dfd06`;
- supported exact 67.5439%;
- raw BGE exact 95.1754%;
- raw BGE tool accuracy 98.2456%;
- near-domain rejection 55.9524%;
- OOD rejection 95.8333%;
- false-route 35.1852%;
- veto precision 75.5396%;
- veto recall 64.8148%;
- raw-correct winners vetoed 63 / 29.0323%;
- NLI batch p95 387.8679 ms;
- end-to-end p95 539.9184 ms;
- positive route switches / authority violations / execution errors 0 / 0 / 0.

Decision: terminal reject. The exact pairwise comparison neither met open-set quality nor runtime
targets. No threshold, epsilon, tie rule, hypothesis wording, language rule or failed-row repair is
permitted.

This closes the Horizon zero-shot/NLI decomposition family (#371/#374/#377/#378). The next research
cycle (#382) moves to a materially different family grounded in open-intent/OOS literature:
schema-derived adaptive decision boundaries, then schema-derived hard negatives and energy-based
open-set evidence.


## 2026-09-28/29 — 0.13 post-V6E semantic-evidence sequence

After V6A-V6E showed that schema-synthetic spherical, ellipsoidal, Gaussian-mixture and local-kNN
geometry did not transfer cleanly to natural requests, the research line changed evidence sources
rather than retuning geometry.

Five preregistered controls were consumed:

1. #404 naturalistic generic-operation probes trained fixed MiniLM linear probes on a frozen
   multilingual utterance bank. Broad OOD improved, but supported exact fell to 75.44%, near-domain
   rejection reached only 59.52%, and p95 was 297.36 ms.
2. #406 Tool-Embed positive retrieval tested an external tool-specialized embedding model as the
   positive selector. It reached 78.07% exact versus 86.84% for same-surface BGE-M3 and missed the
   latency target.
3. #408 relative multilingual cross-encoding jointly scored requests against registered,
   same-resource counterfactual, and background documents. It reached 79.39% supported exact,
   19.84% near rejection, 59.72% OOD rejection, 71.30% false-route, and ~2.99 s p95.
4. #409 frozen GTE multilingual positive retrieval revisited a historically strong pre-V6F
   representation on a new supported-only registry. GTE reached 71.49% exact versus 88.16% for
   same-surface BGE, despite a viable 100.14 ms p95.
5. #412 multilingual-E5 split-conformal membership separated route selection from abstention and
   calibrated a one-sided unsupported null at fixed alpha=0.01. It achieved 99.21% near rejection,
   100% OOD rejection, 0.62% false-route and 244.24 ms p95, but supported exact collapsed to 10.09%
   because 87.29% of raw-correct BGE winners were vetoed.

Every associated confirmation surface remained unopened because DEV failed at least one
preregistered gate.

The resulting architectural constraint is stronger than before: a future candidate must improve the
semantic separability of supported versus same-domain unsupported capability requests. Neither
positive-retriever replacement, generic operation classification, relative relevance ranking nor
conformal calibration over a weak scalar score is sufficient by itself.



## 2026-09-29 — V6H closes the authoritative parser line and 0.14 reframes the product question

### #415 / PR #416 — V6H end-to-end multilingual operation/OOS parser

V6H was the last 0.13 attempt to make a learned semantic parser act as a veto over the frozen BGE
winner. Unlike #404, the multilingual MiniLM encoder itself was fine-tuned end-to-end for
TOOL_OPERATION/BACKGROUND scope and 18-way generic operation classification.

The experiment was frozen before model scoring:
- freeze workflow `36501993390`;
- source `5135a29f39633421136a0c13c39675947fd92f3b`;
- training bank SHA `c9bf9d378f8f9ef7388fde833e9a04c941871514319961b4a0666d97983caa68`;
- DEV SHA `4da38c34929fcbd7ef828a5ccee9afa89b048c960b852cf315dd68b97370f09e`;
- confirmation SHA `26140a4a77ef07fbda0d875cbcba421b0f7a7465990c775fe656bfa4115c7565`.

DEV result:
- gated supported exact 70.18%;
- raw BGE exact 81.58%;
- raw BGE tool accuracy 92.98%;
- near-domain rejection 65.08%;
- OOD rejection 98.61%;
- false-route 27.47%;
- raw-correct winner veto 13.98%;
- scope accuracy 90.58%;
- supported operation accuracy 70.61%;
- near-domain unsupported operation accuracy 51.98%;
- combined p95 181.44 ms;
- authority / route-switch / execution errors 0 / 0 / 0.

The result is important because representation learning did improve the generic scope task and stayed
inside the runtime target, yet the same-domain operation distinction still did not generalize well
enough. Confirmation remained unopened and the exact V6H training/decision formulation is terminal.

### The conceptual correction

At this point the research question itself was re-examined.

SchemaRouter's stable product architecture already compiles and indexes registered executable
capabilities with typed metadata. In an LLM-agent system, that layer is naturally analogous to a
typed executable retriever/index, not necessarily the final autonomous tool-choice authority.

The 0.11–0.13 research had gradually burdened the retrieval layer with three distinct responsibilities:
1. retrieve the exact route;
2. decide whether the request belongs to the registered capability set;
3. make the final execution/no-execution decision.

The terminal lineage showed that this combination can force a safety/coverage trade-off. #412 is the
clearest example: near rejection 99.21%, OOD 100%, false-route 0.62%, and p95 244 ms
were achieved only by collapsing supported exact to 10.09%.

0.14 separates concerns:

```text
query
  -> SchemaRouter typed Top-K capability retrieval
  -> downstream LLM agent
  -> execution validation / permission / destructive policy
  -> tool
  -> deterministic result evaluation
  -> optional candidate expansion / retry
```

This does not mean retrieval accuracy is irrelevant. It changes the relevant accuracy question from
"did the retriever itself choose the one final endpoint?" to "did the compact candidate set preserve
all capabilities needed by the downstream agent?"

### #417 / #418 / PR #419 — Phase A establishes the retrieval premise

The first 0.14 benchmark froze 23 single/multi-tool tasks across 20, 50, 100 and 250 endpoint
catalogs. Before agent inference, two multi-tool data-dependency contracts and missing explicit task
arguments were corrected so the benchmark was actually executable; the corrected corpus was then
re-frozen and the old hashes superseded.

Corrected canonical freeze:
- workflow `36507439562`;
- artifact `11006614997`;
- digest `sha256:5cec1c650bd2a98fc78f7fbb911c0b15d95a39c96a43848b939ba56302658022`;
- task SHA `9663145d1e331007a45901a6426f62df4e67179ca44dc1b7e0e5bfa6390d1fd1`.

Phase A:
- Recall@1 68.97%;
- Recall@3 96.55%;
- Recall@5 100%;
- Recall@10 100%;
- all-required task coverage@5 100%;
- MRR 0.82471.

Mean Top-5 serialized schema context versus FULL:
- 20 endpoints: 26.76%;
- 50: 11.47%;
- 100: 5.87%;
- 250: 2.38%.

This is the first direct evidence for the revised product thesis: a low Top-1 number can coexist with
complete Top-K capability preservation, and candidate reduction becomes more valuable as the catalog
grows.

PR #419 was merged to main as `1c0dc93e843f6f9bf8a628c80ca95e02efcf5088`.

### #420 / PR #421 — B1 end-to-end downstream-agent A/B

B1 adds a real tool-calling model but keeps SchemaRouter retrieval and the agent role strictly
separate.

Conditions:
- FULL;
- SR-3;
- SR-5;
- SR-10;
- SR-PROGRESSIVE;
- ORACLE.

The same deterministic executor enforces typed arguments, multi-step data dependencies and destructive
policy. SchemaRouter rank scores and positions are hidden; after Top-K set membership is chosen, tools
are lexically ordered before being shown to the agent.

The local model is `Qwen/Qwen3-0.6B` at immutable revision
`c1899de289a04d12100db370d81485cdf75e47ca`. It is a reproducible sanity baseline, not
the final product model.

This does not revive #289. #289 tested `Qwen3-Reranker-0.6B` as a yes/no capability verifier
inside the routing boundary and remains terminal. B1 uses a different causal model only as the
downstream tool-using agent; no Qwen score affects retrieval.

The canonical B1 evaluation contains 552 episodes:
23 tasks × 4 catalog sizes × 6 conditions.

A tool-calling smoke passed before the benchmark. Long CPU FULL-catalog episodes required runtime-only
micro-sharding, but task/catalog/model/prompt/K/executor semantics remained frozen. The canonical
aggregate is accepted only if all 552 episodes are reconstructed.

### #423 and #424 — required replication layers

B1 alone cannot establish general agent utility.

- #423 requires the same frozen benchmark to be replicated with a materially stronger tool-calling
  agent before generalizing beyond the small local baseline.
- #424 separates final-answer factual quality from tool-call success and will measure required fact
  recall, hallucination, numeric/unit accuracy and provenance under FULL vs compact capability
  context.

The research endpoint is no longer "find a better open-set threshold." It is to establish
whether a typed capability retrieval substrate improves downstream agent utility, efficiency and
safety under controlled and then realistic conditions.


## 2026-09-29 — B1 integrity hardening before canonical aggregate

Before any accepted 552-episode B1 aggregate, artifact inspection exposed a mechanical shard-ID
bug: the frozen task ID `multi-create-send` had been referenced as
`multi-inventory-create-send` in the s06 execution workflow and executor-specific validation
branch. The affected pre-correction run never produced an accepted full aggregate.

The correction did not alter task text, catalog contents, model identity, K values, prompt,
candidate ordering, executor success semantics, or thresholds. The evaluator now fails closed on
unknown task IDs, workflow tests prove that each frozen task appears exactly once across shards, and
the aggregator verifies unique `(catalog_size, task_id, condition)` identities and the exact frozen
23-task set.

A second design-level correction was frozen before an accepted aggregate: because the same 23
semantic tasks repeat under four catalog sizes, paired uncertainty is now bootstrapped by
task_id cluster rather than treating 92 task×catalog rows as independent. This prevents
pseudoreplication. The B1 -2pp non-inferiority margin is consequently interpreted only as a
descriptive engineering sanity gate; #432 stages the larger independent held-out task population
required for a population-level inference.

The staged 0.14 successors are:
- #428 public typed Top-K retrieval API;
- #430 adaptive shortlist depth;
- #431 execution-state-aware corrective re-retrieval;
- #432 independent held-out generalization surface.

None may use B1 row-level failures to rewrite the frozen B1 task surface.


### B1 v2 canonical protocol

A further static benchmark audit, still before any accepted complete B1 aggregate, found two user
arguments that the executor required but the original task text did not explicitly provide:
`single-message-send` lacked exact message content and `multi-create-share` lacked the numeric
credit amount. The task contract was corrected rather than allowing the agent to guess hidden user
intent.

This changed the frozen task SHA from
`9663145d1e331007a45901a6426f62df4e67179ca44dc1b7e0e5bfa6390d1fd1` to
`bc0b78ff2be11b89e6ac54ea0ee336f944f04b3c203fc61da70a46ff48b4e03c`.
Task IDs, required-route sets, task kinds, catalogs, K values and retrieval algorithm did not change.

A separate causality audit also found that multiple tool calls emitted in one assistant turn could
previously be executed sequentially before the model observed the first tool result. B1 v2 now
enforces:
- at most one executed tool call per assistant turn;
- later same-turn calls are recorded but cannot advance task state;
- dependent calls require a prior tool observation;
- `multi-create-send` must propagate the observed `INV-NEW-1` identifier.

The exact B1 runtime is frozen to:
- Ubuntu 24.04;
- Python 3.12.14;
- torch 2.14.0+cpu;
- transformers 4.57.6;
- tokenizers 0.22.2;
- safetensors 0.8.0.

A two-turn deterministic smoke must pass before inference in the same workflow. In canonical run
`36529108855`, preflight and smoke both passed; the smoke produced
`lookup__value(key="alpha")` followed, after the observation, by
`calculator__add(a=41,b=1)`, with deterministic repeat behavior.

B1 v2 Phase A re-passed:
- Recall@3 96.55% across every catalog size;
- Recall@5 / Recall@10 100% / 100%;
- Top-1 68.97% for 20/50/100 endpoints and 65.52% at 250;
- mean Top-5 serialized context at 250 endpoints 2.383% of FULL.

The canonical v2 run is `36529108855` at
`b9eadefd3cd076f026a54bbc55a949f0424f5dab`. It uses 30 execution jobs because the 250-endpoint
surface is split into smaller task groups for wall-clock control. Scheduling is not an experimental
treatment; all jobs are checked against the frozen sharding plan and aggregate into exactly 552
unique `(catalog_size, task_id, condition)` episodes.

No B1 result is accepted until that aggregate succeeds. The 23 semantic tasks remain a controlled
mechanism surface, so the -2pp criterion is only a descriptive engineering gate; #432 is required
before a population-level generalization or non-inferiority claim.
