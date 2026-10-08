# Evidence-to-Action boundary

SchemaRouter treats evidence sufficiency as an execution precondition, not as workflow orchestration.

## Evidence Contract

`EvidenceContract` is trusted local authority. It can require global evidence and per-field evidence already declared by the registered capability. Model output and remote descriptions cannot upgrade missing evidence.

The initial contract supports:

- provenance;
- licence;
- units;
- exact source type;
- per-field requirements;
- an explicit corroboration count.

A corroboration count above one intentionally fails closed at the single-route boundary until an explicit aggregation boundary establishes independent observations.

## Evidence Ledger

`EvidenceLedgerEntry` records what was established without retaining result payloads. It contains the tool and endpoint identity, selected logical fields, exact tool/endpoint fingerprints, declared available evidence, per-field validation context, and validation state.

`build_evidence_ledger_entry()` re-evaluates the contract against the current trusted `ToolSpec` and `EndpointSpec`. Missing evidence fails closed.

This is deliberately not a DAG, memory system, autonomous re-planner, or evidence inference engine.

## Benchmark plan

The frozen comparison for issue 1203 is:

1. vanilla tool-using agent;
2. SchemaRouter routing/execution without an evidence gate;
3. SchemaRouter with the typed evidence gate.

Primary metrics are premature action rate, evidence-complete action rate, unsupported action rate, exact action success, provenance correctness, schema validity, route/field exactness, false refusal rate, and latency/token overhead.

A benchmark result must distinguish locally declared evidence from model assertions and must not count a model assertion as established evidence.

## Reproduction and current result

The deterministic seed corpus, runner, checked-in baseline, and ablation/error analysis live under `benchmarks/evidence-to-action-v1/`. On the frozen eight-case seed, routing-only retains a 0.375 premature/unsupported action rate, while the evidence-gated condition reduces both to 0 with no false refusals. This is a contract-regression result, not an external-agent benchmark claim.
