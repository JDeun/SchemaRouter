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

Commit `e41f57a0` removed it after full-corpus Laya evidence showed **higher overall and Korean routing accuracy without the sentinel**. The project retained empty-recall expansion, confidence gating, candidate abstention and offline threshold calibration instead.

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
