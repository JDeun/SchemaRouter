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

## Relation to SafeActBench

The motivating reference is Lin et al., *From Evidence to Action: How Tool-Using Agents Fail* (arXiv:2610.07753). SafeActBench contains 656 cases across six operational domains and five protocols. The protocol ladder separates static action judgement, investigated non-action, single consequential actions, linear multi-action workflows, and dependency-constrained DAG workflows. Its provenance-bound Evidence Ledger and deterministic trajectory evaluator test whether required evidence was established before an action and whether downstream prerequisites were satisfied.

SchemaRouter does **not** claim to reproduce those 656 cases in the checked-in eight-case seed. The local harness is a mechanism-level regression test for the execution boundary. A proper external comparison must run the published SafeActBench corpus/evaluator and report model, harness, protocol version, repetitions, and cost/latency metadata separately.

### Mapping

| SafeActBench concern | SchemaRouter boundary |
| --- | --- |
| evidence established before action | trusted-local `EvidenceContract` checked before execution |
| provenance-bound evidence | payload-free `EvidenceLedgerEntry` plus registered evidence metadata |
| premature action | fail-closed evidence sufficiency gate |
| exact action/tool arguments | existing schema, fingerprint, argument and policy validation |
| multi-action prerequisites | intentionally outside the current evidence gate; SchemaRouter does not become a DAG orchestrator |
| deterministic evaluation | frozen local regression scorer today; published SafeActBench evaluator required for external comparison |

### Follow-up validation

The corresponding authors were contacted on 2026-10-08 after PR #1204 merged. We asked whether externally declared typed evidence requirements are consistent with the intended SafeActBench evaluation model and whether validation should begin with the single-action protocol before multi-action protocols. Any future result from that work must be reported separately from the deterministic seed above.
