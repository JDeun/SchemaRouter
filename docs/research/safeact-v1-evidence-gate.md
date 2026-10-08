# SafeActBench V1 evidence-gate evaluation

Tracking issue: #1211

This experiment evaluates SchemaRouter as an **execution-layer intervention** on the official
SafeActBench V1 single-action protocol. It does not reinterpret an evidence-gated run as the
agent's original behavior.

## Upstream freeze

- repository: `caoshidong66/safeact`
- revision: `841816cf1e376e6fbf8600cffac5df1736e1d369`
- protocol: V1
- V1 cases: 131
- code license: MIT
- benchmark/environment data: CC BY 4.0

The upstream benchmark contains 656 cases across six domains and five protocols. V1 requires one
consequential action whose required evidence must be established before the action.

## Author feedback incorporated

Hongzhan Lin confirmed in direct correspondence on 2026-10-08 that a trusted typed evidence
contract is conceptually consistent with SafeActBench's evidence-to-action perspective, while
emphasizing two constraints:

1. SchemaRouter must be evaluated as an execution-layer intervention rather than as a direct
   measurement of the ungated agent.
2. The gate must not use SafeActBench hidden ground-truth requirements. It must use independently
   defined trusted contracts and evidence actually established during execution.

The author recommended V1 before V2/V3 and specifically suggested measuring unsupported execution,
premature action attempts, overall task success, and false refusals.

## Conditions

1. `SAFEACT-UNGATED`
2. `SAFEACT-SCHEMAROUTER-NO-EVIDENCE-GATE`
3. `SAFEACT-SCHEMAROUTER-EVIDENCE-GATE`

Model, harness, task order, public task/tool surface, and evaluator revision must otherwise remain
fixed within a comparison.

The preparatory `V1RunPlan` now targets the official runner by absolute path through the
current Python interpreter. `validate_comparison_matrix()` requires exactly one
entry for each of the three preregistered conditions, one declared model,
one pinned upstream checkout, and separate output directories. This protects
the *declared* comparison design; the trusted adapter still needs to attest
the actual runtime model and per-case environment before scored evaluation.

## Leakage boundary

Runtime contract construction may read only independently trusted, agent-visible/public capability
and policy surfaces. It must not read evaluator-only gold requirements or support labels.

Forbidden runtime inputs include:

- `env/case_evidence.json`
- evaluator-only requirements in `env/case_manifest.json`
- `env/case_provenance.json`
- gold requirement annotations in materialized evidence
- expected action/support labels, gold decisions, or evaluator summaries

The official evaluator may consume its hidden/evaluator-side records **after** trajectory completion.
Those records must never flow back into the Evidence Contract or Evidence Ledger used to decide
whether an action executes.

## Metrics

Primary metrics are reported separately:

- unsupported execution rate
- premature action attempt rate
- Exact Case Success / overall task success
- false refusal rate

Secondary diagnostics include evidence-complete action rate, provenance correctness where
observable, argument-schema validity, gate trigger/reason counts, latency, and context cost.

## Authorization gate

No scored V1 run is authorized until:

- independent V1 contracts exist;
- their provenance is machine-checkable;
- a regression test proves evaluator-only fields cannot enter the runtime contract/ledger;
- the SafeAct adapter preserves the official evaluator boundary;
- exact upstream and SchemaRouter revisions are frozen.

## Mandatory source identity for a trusted session

The `from_verified_sources(..., source_root=...)` factory checks pinned SHA-256
content and local path safety **before** starting a per-case trusted session.
Only the parent harness chooses the trusted root. Direct construction of the
mechanism-test session does not verify physical source files. This SHA check
does **not** prove independent authorship, nor authorize a scored result.

## Action-target evidence binding

An independently authored contract may specify `argument_bindings` that map a
consequential action argument (for example, `charge_id`) to a record ID already
required by `required_observations`. The evidence gate checks action arguments
**and** previously observed evidence before invocation. Evidence collected for
charge `C2` must not authorize a modification of charge `C1`.

This is a deterministic regression-tested gate primitive, **not** a scored
SafeActBench result. The trusted tool-observation adapter and independently
authored V1 contracts remain mandatory before scored execution.

The existing eight-case Evidence-to-Action seed remains deterministic mechanism/regression evidence
only and is not a SafeActBench result.
