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

## Official three-arm post-run integrity audit

After external agent trajectories and official evaluator runs finish, use
`scripts/verify_safeact_v1_comparison.py` with one output directory per
preregistered condition. The post-run auditor rejects simulator outputs,
incomplete or reused cases, unmatched task fingerprints, divergent observed
model identities, non-ephemeral sessions, and altered official artifact hashes.
It checks all 131 V1 cases before comparing the official success-rate field.

The separate `scripts/aggregate_safeact_v1_metrics.py` derives exact-case success
and retained non-ALLOW **consequential records** from the official V1 evaluator's per-case records
*after* verifying all three runs. It cross-checks the official strict success
rate and rejects simulated or incomplete output. Retained consequential records are neither original pre-gate attempts nor
unsupported **executions**: gate-blocked attempts may never be dispatched.
Unsupported execution and false-refusal rates remain explicitly unavailable
until independently verified intervention dispatch logs and counterfactual
justification are implemented. Never infer them from task success.
Gold/evaluator artifacts are inspected **only after** trajectories finish and
never used as inputs to the action gate.

## Typed routing-only official V1 host adapter

`official_routing_hook.py` now supplies a distinct host-side routing-only
ablation. It builds a real SchemaRouter `ToolSpec` / `EndpointSpec` /
`InMemoryRegistry` from the **agent-visible fixed public candidate tool**,
retains information observations, and checks the proposed consequential
tool identity and object-shaped arguments before official record commit.
It does not consult SafeAct evaluator labels, infer detailed argument
schemas from example values, or enforce an evidence requirement. A
distinct `schemarouter_typed_route` intervention marker enables
post-run separation from both ungated and evidence-gated conditions.

The eight-case controlled regression now invokes the actual `EvidenceGate`
implementation and checks the frozen synthetic expected outcomes. It is
**not a SafeActBench model experiment**. Official 131×3 scored evaluation
still requires independently reviewed case contracts, a trusted
Codex/Claude model broker, and end-to-end treatment fidelity.

## Action-target evidence binding

An independently authored contract may specify `argument_bindings` that map a
consequential action argument (for example, `charge_id`) to a record ID already
required by `required_observations`. The evidence gate checks action arguments
**and** previously observed evidence before invocation. Evidence collected for
charge `C2` must not authorize a modification of charge `C1`.

A record requirement can alternatively use `"$action.charge_id"` as its
independently authored record identifier. At dispatch, the gate resolves that
value exclusively from the current action's `charge_id` argument, then checks
the previously trusted observations for the same record. Missing or non-string
arguments fail closed. This allows a single policy template to apply across
public V1 case IDs without copying evaluator-only target labels.

This is a deterministic regression-tested gate primitive, **not** a scored
SafeActBench result. The trusted tool-observation adapter and independently
authored V1 contracts remain mandatory before scored execution.

The existing eight-case Evidence-to-Action seed remains deterministic mechanism/regression evidence
only and is not a SafeActBench result.

## Prospective case-blind contract-selection amendment (#1268; unscored)

The original draft's `case_coverage[case_id] -> expected action` field would
require a case-specific target label not established by the pinned official
public-ID-only listing. Such a label must **never** be backfilled from hidden
gold or evaluator case manifests. The revised draft keeps **all 131 IDs** for
pairing/cohort checks, with every `case_coverage` value set to `null`.
The evidence gate now chooses a contract using the model's *actual proposed
consequential tool identity* and independently pinned tool/policy requirements.
Unknown actions are denied before record commit. This alters the pre-scoring
method, requires independent author/reviewer approval and is **not** a scored
SafeActBench result. See [issue #1268](https://github.com/JDeun/SchemaRouter/issues/1268).

## Domain-qualified case-blind policy selection (prospective, unscored)

Public SafeAct environments can expose the **same tool name in different
domains** (for example, `reply_send`). Therefore the model-proposed tool name
is not a globally unique authority key. The V1 trusted host derives
`env_id` from the pinned upstream **public scenario** and selects the
independently reviewed contract by **(`env_id`, proposed consequential tool)**.
It must not derive the domain from evaluator-only case labels, model prose, or
opaque case IDs. Missing/unknown domains fail closed; a foreign-domain
contract cannot authorize a same-named action. Cross-domain tool-name reuse is
permitted only with **different independently authored domain-scoped
contracts**. Formal scored launch rejects contracts lacking a recognized
domain or duplicating the same (domain, action) identity.

This is a pre-scoring integrity improvement, **not a new SafeAct model
result**. The domain-scoped policy corpus still requires real human authorship,
independent review, pinned source digests, trusted Linux runner/broker and
explicit execution authorization. Tracking: #1268 and #1224.


## Domain-qualified trusted evidence extraction (prospective; unscored)

Selecting contracts by public domain and proposed action is insufficient if
an information tool with the same name in another domain can supply its
extraction rule. `public_observation_mappings` now requires the structure
`env_id -> information tool -> {record_id_key, field_name_key}`.
The trusted official host derives `env_id` only from the public scenario.
Flat tool-only mappings fail closed. The scored-launch controller requires
a correctly formed mapping within each action contract's own domain for
every required observation tool. This is a pre-scoring configuration guard,
not proof of independent policy authorship, correctness or real model score.
