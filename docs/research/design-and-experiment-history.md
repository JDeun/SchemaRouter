# SchemaRouter design and experiment history

> Canonical session-resume tracker: GitHub issue #200  
> Machine-readable evidence ledger: `benchmarks/research-experiment-ledger.json`

This document reconstructs the material design and research lineage of SchemaRouter from the initial repository implementation onward. It is intentionally broader than release notes: it records architectural intent, empirical questions, rejected alternatives, data-consumption rules, and why the project moved from one routing design to the next.

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

The follow-up run showed why the mechanism was wrong: **16 explicit no-route selections contained 13 valid Korean in-domain requests and only 3 true no-route cases**. PR #87 / commit `e41f57a0` therefore removed the sentinel.

Without the sentinel, recall-on-empty reached **61.81% overall and 43.64% Korean accuracy**; adding the same 0.25 confidence/no-route policy reached **60.42% overall, 38.18% Korean and 50% OOD/adversarial accuracy**. The project retained empty-recall expansion, confidence gating, candidate abstention and offline threshold calibration instead.

This matters to the current 0.11 research: a generic catch-all sentinel should not simply be reintroduced under a new name. Negative capability evidence must instead be represented as a distinct typed boundary signal and remain non-authoritative.

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

The design deliberately kept unit metadata optional because not every source is scientific/numeric; text sources such as papers and web/document search remain valid unitless capabilities.

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

- **v2** — 1,200-case multilingual stress corpus with fixed splits;
- **v3** — separate 600-case untouched capability-fit holdout;
- **v4** — operation-fit holdout;
- **v5** — operation development/calibration source;
- **v6** — 600-case operation regression holdout;
- **v7** — fresh post-change holdout;
- **v8** — alias-aware holdout later found to have been accidentally consumed by a diagnostic path;
- **v9** — replacement fresh alias-aware one-shot holdout;
- **v10** — fresh operation-generalization holdout.

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

The same line also added explicit **routing error taxonomy and failure-stage attribution**, allowing later studies to separate candidate recall, capability-fit, operation-fit, wrong-tool and wrong-endpoint failures. The operation-fit semantic representation itself was simplified using v5 development/calibration only before the one-shot v10 generalization run.

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

This established a recurring theme of the follow-up research: **selection quality and rejection quality are not the same objective.**

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

v12 had been inspected before architecture selection, therefore it was explicitly classified as **design-known stress evidence**, not blind evidence.

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

**Rejected**, by one case, without calibration retuning.

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

**Rejected** because unsupported rejection missed the 95% confirmation floor. Calibration was consumed and not used for retuning.

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

Decision: **rejected**.

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

**endpoint selection can be improved independently of unsupported-operation rejection.**

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

The zero-threshold run was intentionally a ranking-ceiling diagnostic, not a promotable router.

Result on the same fresh 1,800-case v4 development corpus:

- raw supported top-route exactness: **90.71%** (1045 / 1152);
- invalid plans / execution errors: **0 / 0**;
- mean / p95 latency: **1014 / 1916 ms** on the GitHub CPU runner.

The raw score distributions showed strong separation between most supported-correct winners and no-route requests, although route-specific tails remained.

Using the preregistered **winner-first** semantics—rank first, then apply only the raw winner's route-local threshold, and abstain instead of falling through—produced the following development-only score frontier:

| canonical false-route budget | supported exact-route | false-route rate | actual near-domain rejection | actual OOD rejection |
| ---: | ---: | ---: | ---: | ---: |
| 0 / 648 | 70.57% | 0.00% | 100.00% | 100.00% |
| 6 / 648 | 74.05% | 0.93% | 99.13% | 98.61% |
| 12 / 648 | **75.78%** | **1.85%** | **98.09%** | **98.61%** |

This changed the immediate research conclusion:

- an additional NLI/negative model is **not required** to cross the current accuracy/rejection/false-route development gates;
- threshold **application order** was a major safety variable;
- the remaining primary gate is **latency**, because scoring four BGE candidates for every request is too expensive.

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
3. choose the **smallest** width that preserves >=70% supported exact-route, <=2% canonical false-route, >=96% near-domain rejection lower bound, and zero invalid plans/errors;
4. if neither passes, retain width 4.

The chosen width must still pass a separately executed **paired latency gate** before the candidate is frozen.

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

Canonical tracker: **#200**

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
- mainline commits enumerated: **140**
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

This enumeration is deliberately broader than the narrative above. It prevents the research record from silently excluding early implementation work just because it predated the formal 0.10/0.11 experiment manifests.

Rejected and unmerged research branches are not expected to appear in mainline history. They remain represented independently in `benchmarks/research-experiment-ledger.json` through PR, branch, workflow-run, artifact, and decision provenance.

The audit therefore has two complementary axes:

1. **mainline history completeness** — every commit from repository inception is enumerated;
2. **research evidence completeness** — material unmerged/rejected experiments remain in the experiment ledger instead of disappearing when their PR is closed.


## 18. Width-2 frozen winner-gate executable result

Work item #227 / PR #228 executed the preregistered width-2, score-only, route-local `rank_then_gate` candidate on the fresh 1,800-case v4 development corpus. The threshold map was frozen before execution from canonical width-selection artifact `10930665000`; no calibration or blind evidence was used.

Quality/safety result:

- supported exact-route: **72.57%** (gate >=70%);
- near-domain unsupported rejection: **98.09%** (gate >=96%);
- canonical false routes: **12/648 = 1.85%** (gate <=2%);
- OOD rejection: **98.61%**;
- invalid plans / execution errors: **0 / 0**.

The quality gates therefore passed. The paired same-runner latency gate did not:

- baseline mean/p50/p95: **531.031 / 605.144 / 697.912 ms**;
- candidate mean/p50/p95: **765.187 / 582.750 / 1836.868 ms**;
- mean latency: **+44.09%**;
- p95 latency: **+163.19%**.

Decision: **rejected on the development latency gate**. This candidate is not frozen for confirmation and must not advance to #198 calibration/blind evaluation. The result is important negative evidence: winner-only route-local gating can cross the current quality/safety frontier at width 2, but unconditional BGE invocation still produces unacceptable CPU mean/tail latency.

Provenance:

- source revision: `fdaf3f77e95b504e81739c69cd1d9889d36afabb`;
- workflow run: `36315784179`;
- artifact: `10931078672`;
- artifact SHA-256: `00517181c286197fe61156d04348eb9519bc8dab3681d20650216bfb923b37e1`;
- corpus SHA-256: `fc085c58ed7c667d71024e60cf9e213e66da8f7b43f6e79551ed810a9e328216`.

The next development-only evidence task was #226: measure a cheap multilingual action-only signal built solely from endpoint action names and trusted `operation_aliases`. Any behavior-changing fast path, veto, or evidence projection remained subject to separate preregistration.

## 19. Cheap action-only evidence diagnostic

Work item #226 / PR #230 tested a behavior-preserving evidence surface using the existing multilingual MiniLM. The representation included only the normalized endpoint action name and trusted `operation_aliases`; tool descriptions, endpoint descriptions, fields, parameters, corpus templates, and unsupported-operation labels were explicitly excluded.

DEV result:

- supported raw top-route exact: **73.00%**;
- English / Spanish / mixed / Japanese / German / Korean raw exact: **86.46 / 80.73 / 76.56 / 73.96 / 64.06 / 56.25%**;
- query embedding + cosine mean/p50/p95: **13.836 / 13.604 / 15.515 ms**;
- static 16-option embedding cost: **68.724 ms**, cacheable.

The high-precision direct-accept frontier was narrow:

- score >=0.50 and margin >=0.10: 155/1800 accepted, **98.06% precision**, 8.61% overall coverage;
- score >=0.55 and margin >=0.15: 67/1800 accepted, **100% observed precision**, 3.72% overall coverage.

Decision: retain the signal as a cheap bounded selector/supporting evidence surface, but **do not** promote it as a global direct fast path. Its high-precision coverage is too small to remove the BGE p95 bottleneck.

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

- raw supported exact-route: **74.48%**;
- mean / p95 latency: **445.96 / 476.42 ms**;
- strict 6/648 false-route frontier:
  - supported exact: **62.15%**;
  - false-route: **0.93%**;
  - near-domain rejection lower bound: **98.96%**;
- canonical 12/648 frontier:
  - supported exact: **65.36%**;
  - false-route: **1.85%**;
  - near-domain rejection lower bound: **97.92%**;
- invalid plans / execution errors: **0 / 0**.

Decision: **rejected**. Single-pair BGE solved much of the CPU latency problem but did not preserve enough supported recall.

Provenance:

- workflow: `36319879567`;
- artifact: `10932093354`;
- artifact SHA-256: `47f1a8dcab2f1956a939df995c0f19137e96d92b8a4451753abdf039598934aa`.

## 21. Cheap embedding architecture diagnostics

### Bounded action embedding

Work item #233 / PR #236 tested cached multilingual MiniLM action-only evidence inside the bounded width-2 set.

Valid revision-2 result:

- raw supported top-route exact: **73.35%**;
- canonical 12/648 supported exact: **47.92%**;
- near-domain rejection: **97.92%**;
- false-route: **1.85%**;
- mean / p95 latency: **44.29 / 47.98 ms**.

An earlier run was invalidated **before result inspection** because projected metrics could have used only scored rows rather than the fixed 1,800-case denominator.

Decision: **rejected**. The architecture was fast, but score/margin open-set gating collapsed supported recall.

### Single-query MiniLM dual view

Work item #240 / PR #241 scored two cached route representations from one query embedding:

- schema/domain view;
- action/alias view.

The best raw strategy was schema/action 0.25/0.75 at **75.00%** supported exact. The best canonical 12/648 point reached only **54.77%** exact at **97.92%** near-domain rejection and **1.85%** false-route, while latency fell to about **14.02 / 15.31 ms mean/p95**.

Decision: **rejected for quality, retained as evidence that representation capacity rather than runtime had become the limiting factor**.

## 22. Multilingual embedding backbone screen

Work item #242 / PR #243 kept the dual-view architecture fixed and changed only the multilingual embedding backbone.

### E5-base

- best raw exact: **84.46%**;
- best canonical 12/648 exact: **62.41%**;
- latency: **50.19 / 56.20 ms mean/p95**.

### GTE multilingual base

- best raw exact: **89.15%** using schema/action 0.25/0.75;
- best canonical 12/648 exact: **63.11%**;
- latency: **69.37 / 76.58 ms mean/p95**.

GTE proved that >=85% ranking capacity was available, but its native score geometry was not a sufficient open-set boundary.

### BGE-M3 embedding

BGE-M3 was the first embedding-only architecture to combine high ranking quality with a strong open-set frontier:

- best raw exact: **88.45%**;
- at 12/648 false routes:
  - supported exact: **83.85%**;
  - near-domain rejection: **97.92%**;
  - false-route: **1.85%**;
- at 6/648 false routes:
  - supported exact: **83.33%**;
  - near-domain rejection: **98.96%**;
  - false-route: **0.93%**;
- p95 latency: approximately **168 ms**.

Decision: **BGE-M3 selected as the main strict open-set optimization line**.

## 23. GTE winner + BGE rejector

Work item #244 / PR #249 tested a factorized architecture:

1. GTE 0.25/0.75 dual-view selects one registered route;
2. BGE reranker scores only that winner;
3. BGE may accept/reject but may not switch routes.

All four preregistered action/capability × max-length variants preserved raw GTE ranking at **89.15%**, but the best canonical open-set result was only:

- supported exact: **76.13%**;
- near-domain rejection: **97.92%**;
- false-route: **1.85%**;
- best end-to-end mean / p95 latency: **293.89 / 328.11 ms**.

Decision: **rejected**. A cross-encoder winner relevance score was not a clean enough open-set separator to preserve GTE's ranking headroom.

## 24. Frozen BGE-M3 candidate and numerical-stability finding

Work item #245 / PR #247 froze the BGE-M3 50/50, budget-6 profile and executed it through the actual `SchemaPlanner`.

Safety and authority behavior reproduced exactly:

- planner/direct parity mismatches: **0 / 1800**;
- invalid plans: **0**;
- execution errors: **0**;
- rank-2 fallthroughs: **0**;
- false-route: **6/648 = 0.93%**;
- near-domain rejection: **98.96%**;
- OOD rejection: **100%**;
- planner mean / p95 latency: **188.73 / 206.00 ms**.

However, the frozen projection expected 960 supported-correct cases and executable confirmation produced **959/1152 = 83.25%**.

Artifact inspection localized the single-case drift:

- case: `v4-dev-papers-citations-ko-08`;
- route: `papers.citations`;
- frozen min score: `0.46308739913552904`;
- rerun score: `0.4630872644672503`;
- difference: approximately **-1.35e-7**.

The route winner and planner/direct behavior did not change; only the accept/reject boundary flipped.

Decision: **not promoted**.

This established an additional operational requirement: **a frozen threshold must not be an observed floating-point sample boundary**. Later candidates must define explicit numerical-stability semantics such as midpoint thresholds, conservative quantization/guard bands, and perturbation checks.

Provenance:

- workflow: `36323685913`;
- artifact: `10933122169`;
- artifact SHA-256: `a63e6954d8cf44db21bc89b336ca8f67bacc77af933fe870c33bc9298bf6a1a1`.

## 25. BGE-M3 fine global fusion

Work item #246 / PR #248 preregistered schema weights 0.30–0.60 with no post-run interpolation.

Best strict 6/648 result:

- schema/action fusion: **0.55 / 0.45**;
- supported exact: **965/1152 = 83.77%**;
- near-domain rejection: **98.96%**;
- false-route: **0.93%**;
- wrong-supported accepted: 62;
- mean / p95 latency: **180.34 / 195.97 ms**.

Best secondary 12/648 result:

- supported exact: **970/1152 = 84.20%**;
- near-domain rejection: **97.92%**;
- false-route: **1.85%**.

The final >=85% strict target requires at least **980/1152** correct cases, so the best global fusion remained **15 cases short**.

Decision: **global fine-fusion search exhausted without passing the production target**.

Provenance:

- workflow: `36324755106`;
- artifact: `10934145256`;
- artifact SHA-256: `60dfbb1d32f1f27873bd8fad4aa4888af80856365196e3ab6fb5be6b1e7f0af7`.

## 26. Current active optimization: recover the final 15 cases

Route-level analysis of #246 found that different routes prefer different schema/action weights. Holding the global 0.55 weight produced 1,019 raw supported-correct cases, while independently choosing the best preregistered grid weight for each route yields a diagnostic raw ceiling of **1,046**, a **+27-case** headroom.

The largest examples include:

- `inventory.search`: 50.00% raw exact at global 0.55 versus **69.44%** at route-local 0.35;
- `papers.search`: 81.94% versus **90.28%** at route-local 0.30.

### #256 route-local stable fusion

Work item #256 / PR #257 is the lower-cost active line.

It freezes the route-local weight map before execution and changes boundary construction so that:

- an observed sample score is never used directly as a threshold;
- candidate thresholds are midpoints between adjacent unique winner scores;
- selected score thresholds are conservatively rounded upward to six decimals;
- final metrics are stress-tested at **±1e-6** and **±1e-5** score/margin perturbations.

Primary gate:

- supported exact >=85%;
- near-domain rejection >=97%;
- false-route <=1%;
- OOD rejection 100%;
- p95 <=250 ms;
- the same primary quality/safety gates must survive ±1e-6 perturbation.

### #255 conditional zero-false rescue

Work item #255 / PR #258 runs in parallel as a more expensive fallback.

It keeps the immutable #246 strict 0.55/0.45 base and invokes a pinned BGE cross-encoder **only on base abstentions**, with a primary rescue budget of zero additional false routes.

The validator may only rescue the same raw rank-1 winner; it cannot switch to rank 2 or create execution authority.

Both lines remain DEV-only. Calibration/blind evidence remains blocked until a fully frozen candidate passes the complete development, numerical-stability, and runtime gates.
