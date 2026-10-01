# Public roadmap

This roadmap separates **stable product**, **research**, **ecosystem integrations**, and **community
growth** so contributors can tell which boundaries are open to change.

It is a coordination view, not a promise of dates. GitHub issues are the source of truth for current
work and acceptance criteria.

## Stable product

**Current stable release:** SchemaRouter 0.13.0 (Beta / pre-1.0).

The stable core is a typed capability retrieval and schema-aware execution boundary. Product work
should preserve local execution authority, schema/fingerprint validation, explicit side-effect
policy, and protocol-neutral contracts.

Current coordination:

- [#606 — Product completeness / next stable release gate](https://github.com/JDeun/SchemaRouter/issues/606)
- [Stable-core contract](../stable-core.md)
- [Release checklist](../release-checklist.md)
- [Trust, stability, and public evidence](trust-and-evidence.md)

Do not reopen the core architecture merely to support one provider. Prefer adapters, trusted SDK
bindings, framework bridges, or decision plugins.

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
