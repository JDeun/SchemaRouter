# Public roadmap

This roadmap separates **stable product**, **research**, **ecosystem integrations**, and **community
growth** so contributors can tell which boundaries are open to change.

It is a coordination view, not a promise of dates. GitHub issues are the source of truth for current
work and acceptance criteria.

## Stable product

**Current stable release:** SchemaRouter 0.17.0 (Beta / pre-1.0).

The stable core is a typed capability retrieval and schema-aware execution boundary. Product work
should preserve local execution authority, schema/fingerprint validation, explicit side-effect
policy, and protocol-neutral contracts.

Recent product follow-ups on current `main`:

- Issue #743 — explicit state-conditioned corrective re-retrieval;
- Issue #744 — scalable indexed/incremental capability dependency graphs;
- Issue #745 — atomic validated snapshot rebuild/publication;
- Issue #746 — versioned capability artifact/snapshot migration and semantic integrity;
- Issue #747 — unified privacy-safe capability decision traces;
- Issue #748 — provider-first registration with Materials Project, Crossref, and Tavily acceptance.

Current coordination:

- [#606 — Product completeness / next stable release gate](https://github.com/JDeun/SchemaRouter/issues/606)
- [Stable-core contract](../stable-core.md)
- [Release checklist](../release-checklist.md)
- [Trust, stability, and public evidence](trust-and-evidence.md)

Do not reopen the core architecture merely to support one provider. Prefer adapters, trusted SDK
bindings, framework bridges, or decision plugins.

## Original-paper Algorithm 1 parity checkpoint (2026-10-24)

Read the [**paper-first Algorithm 1 ↔ product code alignment**](../research/original-paper-algorithm1-parity.md)
before proposing more graph-frontier, tool-list presentation, agent-harness
or synthetic cost experiments. The current product is **not a different
project**: original contracts, typed endpoints, field projection,
evidence/provenance and permission-checked execution remain.
**However, complete paper parity is not yet delivered:**
`retrieve[_authorized]` defaults to `KeywordAnalyzer` and
lexical/typed K ranking, not the original query→intent/concept→
declared FieldGroup→recall-preserving field projection graph algorithm.
The existing producer→consumer graph and exact owner-declared
concept aliases are useful **opt-in** modules, not a substitute
for that default end-to-end path.

Priority is **#1535 required source-visible field completeness before K**
then **#1560 opt-in paper-complete plan composition**,
followed by **#1339 + #1346 + #1477** independent downstream
field recall, retrieved *data-context* tokens, answer quality
and source/license attribution. The newer #1742–#1744
multi-domain **schema-menu** token evidence is valid narrow E0,
**not** the original paper's retrieved-context savings or
task-quality reproduction. No default behavior, permission
or release gate changes are authorized by this documentation.

## Original paper's schema-graph retrieval north star (current priority)

**SchemaRouter is a field-aware, agent-neutral capability retrieval and typed-contract
boundary, not an autonomous agent.** The [original SchemaRouter paper](https://arxiv.org/abs/2608.21375)
models relationships among registered Tool, Endpoint, Parameter, OutputField,
DomainConcept, FieldGroup, Unit, SourceType, license and provenance. Given a
query, the goal is to find its required **concepts and output fields** through
these trusted typed graph relationships, enforce the principal's allowed
source/data scope, and deliver a small relevant tool/field shortlist. The
**external agent** chooses the tool, arguments and follow-up action; any actual
invocation must pass a separate explicit host authorization and schema check.
A graph database is one storage choice, **not** proof of graph-informed search.

**Do not mistake an existing feature for future work:** the public
`retrieve_authorized(query, k=5)` already returns principal-filtered Top-K
contracts. A new catalog wrapper or agent loop does not implement the
paper's query-to-concept-to-field matching. The separate producer/consumer
dependency graph and versioned artifacts are valuable but do not, alone,
prove that the original graph relationships drive default search.

**Implementation and qualification order (source of truth: issue acceptance):**

1. [#1530 — paper-to-code graph retrieval audit](https://github.com/JDeun/SchemaRouter/issues/1530):
   distinguish wired default matching from existing standalone primitives
   for intent, aliases, field groups, typed units/qualifiers, source/license,
   field projection and graph snapshot identity; cite specific code/tests.
2. [#1532 — P0 hidden schema metadata](https://github.com/JDeun/SchemaRouter/issues/1532)
   and [#1450 — authority/source drift](https://github.com/JDeun/SchemaRouter/issues/1450):
   repair or verify principal-hidden fields and source identity **before**
   ranking promotion. No semantic relationship may expose a denied tool,
   hidden field or new execution permission.
3. [#1531 — opt-in E0 declared concept-to-field bridge](https://github.com/JDeun/SchemaRouter/pull/1531):
   test trusted alias-to-semantic-ID edges, then field-group/endpoint,
   unit/type/source/license constraints inside the existing authorized
   retrieval boundary. This **does not** implement all of Algorithm 1;
   keep production defaults and strict K=5 unchanged pending qualification.
4. [#1339 — EN/KO/JA initial route/field recall](https://github.com/JDeun/SchemaRouter/issues/1339),
   [#1477 — paired external-agent task E2](https://github.com/JDeun/SchemaRouter/issues/1477):
   measure operation, input/field correctness, OOD/no-fit, schema bytes and
   actual tokenizer count, CPU p50/p95/p99 and final agent completion.
   Independent publisher-native, permission-reviewed task/gold
   [#1346](https://github.com/JDeun/SchemaRouter/issues/1346) is a hard
   **BLOCKED_EXTERNAL** dependency. Do not retune frozen #432 results.
5. [#1356 — v0.18 release](https://github.com/JDeun/SchemaRouter/pull/1356):
   remain **HARD HOLD** until independent task-level quality, safety,
   source correctness and CPU budget gates are passed.

**Negative control:** [#1528](https://github.com/JDeun/SchemaRouter/pull/1528)
showed that exposing a full authorized 100–500-tool index can use
far more bytes than a selected K5 schema set, or exceed the 32KiB
experimental cap. Never infer that sending the entire graph/index to
an LLM or increasing K/caps improves retrieval. The K5 presentation
wrapper [#1529](https://github.com/JDeun/SchemaRouter/pull/1529) was
closed without merging; it was not a graph search improvement.

This section is an **architectural direction**, not a declaration of
completed paper parity, multilingual quality or a released feature.

## Research

Research may test alternatives that are not product defaults.

Current public evidence and work:

- [#15 — live decision-routing benchmark evidence](https://github.com/JDeun/SchemaRouter/issues/15)
- [0.14 evidence checkpoint](../research/0.14-paper-evidence-checkpoint.md)
- [Research evidence package](../research/paper-evidence-package.md)
- [Research governance](../research/governance.md)

Frozen workloads, splits, promotion gates, negative results, and historical evidence must not be
rewritten to accommodate a product change. A new hypothesis requires a new versioned experiment.

## Ecosystem and integrations

The goal is to make SchemaRouter usable beside existing agent/tool ecosystems rather than replace
them.

Current coordination:

- [#10 — LangChain/LlamaIndex ecosystem distribution](https://github.com/JDeun/SchemaRouter/issues/10)
- LangChain / LangGraph bridges
- LlamaIndex bridge
- MCP, OpenAPI, OPTIMADE, GraphQL, OData, OpenRPC, HTTP/JSON ingestion
- System One / Jev / Laya / Ollama bounded decision backends
- OpenTelemetry integration
- third-party SourceAdapter and decision-backend entry points

Integration work should remain optional and must not bypass SchemaRouter execution validation or
policy.

## Community and adoption

Community work exists to make the project easier to discover, try, verify, contribute to, and
adopt without weakening technical boundaries.

Current coordination:

- [#576 — growth parent](https://github.com/JDeun/SchemaRouter/issues/576)
- [#581 — contributor/community experience](https://github.com/JDeun/SchemaRouter/issues/581)
- [#582 — developer-focused launch/content](https://github.com/JDeun/SchemaRouter/issues/582)
- [#584 — external adopters/case studies/independent validation](https://github.com/JDeun/SchemaRouter/issues/584)
- [Adoption scorecard](adoption-scorecard.md)
- [Discoverability and positioning](discoverability.md)
- [Developer launch playbook](launch-playbook.md)
- [Launch and outreach log](launch-log.md)
- [External adoption and validation](external-adoption.md)
- [External case-study template](case-study-template.md)

Stars are a lagging signal. Prefer reproducible examples, downstream integrations, external
reproductions, and repeat usage over vanity promotion.

## What is suitable for outside contributors?

Good contribution surfaces include:

- a bounded adapter for a structured protocol/provider with a documented schema;
- focused compatibility tests for an existing integration;
- docs/examples that make a supported path reproducible;
- a decision-backend plugin with finite-option validation;
- a framework bridge that preserves SchemaRouter authority;
- a benchmark reproduction with machine-readable artifacts;
- small reliability or developer-experience defects with an explicit failing test.

Changes that require maintainer design before implementation include:

- new execution-authority semantics;
- changing destructive-operation policy;
- changing persisted-format compatibility guarantees;
- changing a frozen research workload or promotion gate;
- moving release credentials/signing/publishing trust;
- turning SchemaRouter into a general agent runtime.

## Issue labels

Use labels as work-shape signals, not priority theater.

- `good first issue`: bounded task, public acceptance criterion, no hidden infrastructure;
- `help wanted`: externally tractable work that may span more than one file;
- `bug`: reproducible correctness/reliability defect;
- `enhancement`: supported product/integration improvement;
- `research`: empirical or benchmark work whose result is not a stable product guarantee.

Maintainers should remove `good first issue` when the task acquires an unresolved architecture
decision or private dependency.

## GitHub Discussions decision

**Discussions are intentionally deferred for now.**

The project currently benefits more from one actionable issue queue than from splitting low-volume
traffic across Issues and Discussions. Revisit this after launch/adoption work produces recurring
Q&A or design conversations that are not actionable defects/features.

If enabled later, start with only:

- Q&A;
- Ideas;
- Show and tell;
- Announcements (maintainer-only posting).

Security reports remain private regardless of channel.

## How the roadmap changes

A roadmap change should cite the issue that motivated it. Completing an item does not imply a new
stable guarantee until the corresponding code/docs are merged and, where relevant, shipped in a
stable release.
