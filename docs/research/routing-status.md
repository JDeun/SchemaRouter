# Routing research status

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

## Current successor prototype

The next research direction is a **registry-compiled capability verifier**.

Instead of asking only whether a request is similar to an endpoint, the prototype compiles generic
operation and data contracts from ordinary `ToolSpec` / `EndpointSpec` metadata and checks whether
the raw winning route actually supports the requested operation.

Its design constraints are stricter than the earlier benchmark-specific experiments:

- the same compiler must accept native tools, OpenAPI imports and MCP imports;
- endpoint names may be opaque and `operation_aliases` may be empty;
- no route IDs, fixed endpoint counts or benchmark-domain keyword tables may become learned features;
- datatype, source unit, canonical unit normalization, semantic IDs and qualifiers remain registered
  deterministic metadata;
- a verifier is veto-only and cannot invent or switch routes;
- newly registered tools must not require route-specific retraining.

This successor remains a **research prototype until canonical DEV and a separate registration-
generalization holdout pass, followed by a new zero-overlap fresh confirmation**. It is not the
default routing path in the 0.10.0 library release.

## Reproducibility

The closed-cycle machine-readable decision is stored at
`benchmarks/operation-routing-v4-terminal-decision.json`.

The full evidence ledger is stored at
`benchmarks/research-experiment-ledger.json`.

The complete design/experiment narrative is stored at
`docs/research/design-and-experiment-history.md`.

The terminal report is available at
[Operation routing v4 terminal report](operation-routing-v4-terminal-report.md).
