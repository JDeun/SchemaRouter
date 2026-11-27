> **Development discontinued (2026-11-27).** This isolated PoC is preserved as research history. No new work or release is planned. See [final retrospective](FINAL-RETROSPECTIVE.md). The GitHub archive setting is a separate administrative step.

# Agent-driven SchemaRouter — clean-slate PoC

Status: restricted local discovery PoC implemented; 29/29 local engineering tests recorded. Agent-performance comparison not run.

**Current implementation and test receipt:** [Discovery contract / Gate B acceptance](discovery-contract.md). Backend decision: [ADR-001](prior-art-and-adr.md).

**Canonical requirements:** [PRD.md](PRD.md). This README is an orientation; PRD requirement IDs and acceptance criteria govern new product work.
Decision tracker: [#1897](https://github.com/JDeun/SchemaRouter/issues/1897).
Work items: [prior art #1898](https://github.com/JDeun/SchemaRouter/issues/1898), [PoC #1899](https://github.com/JDeun/SchemaRouter/issues/1899), [evaluation #1900](https://github.com/JDeun/SchemaRouter/issues/1900), [legacy disposition #1901](https://github.com/JDeun/SchemaRouter/issues/1901).

## Product boundary

SchemaRouter is an agent-consumed semantic tool-schema ontology and field-aware discovery service. It stores tool capabilities and schema relationships, not the underlying business or scientific records. An external agent understands the user, initiates searches, chooses tools, fills arguments, calls tools and synthesizes the answer. The discovery core requires no LLM, internal intent classifier, execution planner or tool executor.

The historical Algorithm 1 includes an LLM Understand stage and tool-plan construction; that remains a separate reproducible paper experiment. This narrower future product contract does not rewrite the paper or historical evidence.

## Minimal interface (implemented research subset)

```text
Catalog(concepts, host_permitted_routes)
Catalog.discover(requirements, max_routes=None)
  -> matched routes + projected schemas + per-requirement receipts + revision
```

Separate search by known semantic identifiers/aliases from natural-language matching of search terms; the agent supplies requirements, not a mandatory raw-user-query plan. The first experiment must not require a model inside the search core. Index the host-permitted schema surface. Preserve necessary input properties and constraints, identifiers, selected output properties and their provenance. Return original route identity and revision; a discovery hit does not grant execution authority. An output view is not a promise of upstream wire-level field selection.

Example agent request (illustrative vocabulary, not a source schema):
```json
{"concepts": ["bulk modulus", "research paper"]}
```

Expected behavior: return relevant material property and literature capabilities, potentially in different endpoints, with the associated partial schemas. Do not silently substitute Young's modulus for bulk modulus or map an ambiguous elastic modulus to a single quantity. Unknown or ambiguous requirements must be distinguishable from complete coverage. No hard-coded top-five cutoff.

## Minimal architecture

1. Source schema ingestion and normalization
2. Persistent versioned semantic graph (Tool, Endpoint, Parameter, ResponseField, DomainConcept, field group, alias, unit, source type, provenance, license)
3. Concept/field/endpoint/tool search
4. Source-grounded partial schema projection
5. External agent integration outside the discovery core

Choose an existing ontology/graph implementation if feasible. The comparison in #1898 precedes a backend commitment. No custom generic database, generic OWL reasoning engine, second agent, or unnecessary framework. The isolated PoC must not import the existing planning/execution core by default. Keep the current package and release machinery unchanged.

## First decision experiment

A: full tool schemas.
B: ordinary lexical/vector tool-level retrieval.
C: standard ontology/SPARQL plus straightforward field projection and equivalent metadata.
D: proposed PoC only if it differs meaningfully from C; otherwise use C directly and evaluate whether a small adapter is justified.

Use identical external agent/model, allowed metadata, tool surface, tasks, execution fixtures, scoring and budget. The public paper inventory (19 tools, 166 fields, 110 exposed queries) is development evidence, not an independent held-out set. Begin with a two-need materials/literature fixture and a generic ontology baseline. Measure all required-field coverage, tool/field precision and recall, end-task success, operational tokens, latency, actual vs projected payload, build/update costs and annotation/maintenance effort. Predefine final decision rules and independent cohort before viewing final scores.

If an ordinary ontology plus a small projection function is sufficient, reuse it or stop the standalone engine. If the advantage is limited to a domain, narrow the product. If the evidence is unavailable, mark inconclusive. No new release before the decision.

## Preservation

Base main snapshot: `bbe466d5b7fd9284db9b1f467633186bf89c7d68`.
Historical paper consolidation PR #1895 was closed without merge; its exact head `8fa102d28aa7071e00f2e212767c9b25838e747d` and branch remain preserved. Its incomplete qualification and previous negative evidence (#432) remain separate. Do not delete or rewrite old branches or publish private paper assets. The old release candidate #1356 was canceled and closed without merge. See completed disposition #1901.

This directory is the isolated new work area. Local mechanism tests are complete for the documented subset; fresh CI and Gate C agent comparisons remain outstanding.
