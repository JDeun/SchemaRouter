# SafeAct V1 independent-contract preflight

## Prospective repeated-trajectory research gate (not yet executed)

The first official 131-case × 3-arm execution is only a **single-rollout
feasibility study**, even if every trajectory receives an official score.
The 2026-10-10 researcher follow-up highlighted two additional requirements:
independently justified evidence-contract authorship (including the risk of
case-specific human heuristics and uncertain LLM-authored proposals) and
repeated open-ended agent rollouts with blinded human trajectory annotation.

See [the prospective repeated-evaluation protocol](../../../research/safeact-v1/repeated-evaluation-protocol.md).
Do **not** treat the existing 393-output aggregator as repeated-run,
manually annotated, or unseen-domain generalization evidence. The
machine-readable scored summary explicitly marks these unmeasured boundaries.
No new model calls, privileged broker permission, approval or hidden case
information are conferred by this design document.

These files provide **unscored** research mechanisms, not a completed
SafeActBench evaluation. The upstream revision is
`841816cf1e376e6fbf8600cffac5df1736e1d369`; its V1 set contains 131 cases.

Independently approve a contract using only agent-visible/public capabilities
and policies.
The SafeAct preflight workflow also publishes an **unreviewed public source
inventory**: pinned `templates/*/tools/*.py` tool filenames and the files
directly under `templates/*/world/policies/`, with SHA-256 digests only.
Domains with no policy directory are listed explicitly. No other world state,
gold, case manifests, labels or evaluator files are traversed; symlinks fail
closed. Public policy candidates are **not automatically Evidence Contracts**
or verified runtime observations. A human author must interpret the public
sources, establish the action/field semantics and cite pinned source bytes;
a different person must independently review the complete mapping.
Opaque 131-case IDs alone do not establish which contract an action requires.
Never infer that correspondence from hidden evaluator requirements, labels
or trajectories. This inventory supplies no case decisions or model scores.
Every source reference should declare an allowed `kind`, a relative `path`,
and the exact lowercase SHA-256 digest of the frozen *actual public file*.

To verify source identity from a trusted parent process, run:

```bash
python scripts/verify_safeact_v1_sources.py contracts.json --source-root public-sources/
```

This verifies path safety, file identity and post-freeze tampering. It **does not
establish independent authorship or semantic correctness**.

For a parent-process session, use
`TrustedEvidenceSession.from_verified_sources(..., source_root=trusted_path)`
to fail closed on the pinned source files **before** any tool invocation.
The trusted parent supplies `source_root`; never accept it from model output.
The ordinary constructor is mechanism-test only and does not attest source files.

`TrustedEvidenceSession` wraps agent-inaccessible information/action callers
and verifies real tool results before adding observations. It records per-case
mechanism diagnostics, not official task success or unsupported execution.
For post-run comparison only, validate three official `external_agent`
output directories with `python scripts/verify_safeact_v1_comparison.py`
and the required `--safeact-ungated`,
`--safeact-schemarouter-no-evidence-gate`, and
`--safeact-schemarouter-evidence-gate` directory options.
This checks 131 paired case fingerprints, actual runtime-model attestation,
ephemeral sessions and per-case official artifact SHA-256 values. It reports
only the official strict task-success metric; unsupported executions,
premature attempts and false refusals are **not yet scored here**.

The full independently approved contracts, official agent bridge and scored
131-case three-condition evaluation remain pending.

## Official three-arm runtime integrity preflight

Before any scored claims, use `validate_comparison_matrix()` on exactly
three `V1RunPlan` objects. The official runner is invoked by absolute path.
After official trajectories finish, call `audit_v1_completions(plans)` from a
trusted parent process. The audit reads only post-run completion markers and
checks that all 131 public case IDs match across conditions, that the
requested and observed model identities match the frozen model, and that
each task used a fresh ephemeral session. It rejects symlinked markers.

This is a **post-run runtime identity check, not a SafeAct score**. Hidden
evaluator contents, gold labels, and evaluation records are not read or
exposed to the agent. Official evaluator scores remain a separate output.


## Verified official V1 reference evaluator (no model, no experiment effect)

The pinned official evaluator completed all **131/131** V1 reference cases in
`--simulate` mode on 2026-10-08. See
[`benchmarks/safeact-v1-official-reference-20261008.json`](../../../benchmarks/safeact-v1-official-reference-20261008.json)
for the exact upstream SHA, mode, checks and
[GitHub Actions run](https://github.com/JDeun/SchemaRouter/actions/runs/37766251911).
This execution does **not** constitute the three-arm model benchmark; the
reference simulator uses official gold information and is strictly isolated
from the agent runtime and Evidence Contract authoring.

For CI efficiency, pull requests run the pinned public V1 listing, synthetic
host-bridge checks, and independent-contract preflight without rerunning all
131 official gold-reference simulations. The 131-case gold-reference
regression remains available via explicit workflow dispatch and a weekly
schedule **after the workflow is merged to the repository default branch**;
its result is never an actual agent score. The previously completed 131/131
reference run is linked above.


## Launching a scored three-arm experiment (requires a trusted model runtime)

Run `python scripts/run_safeact_v1_scored.py --help` from SchemaRouter.
The controller accepts a pinned SafeAct checkout, a frozen model name,
**three distinct external agent commands**, an independently approved
`contracts.json`, its pinned public-source root, and a reviewed
`intervention_manifest.json`. The contract document must include an explicit
`case_coverage` map for all 131 **public** V1 case IDs, with all values
`null`. This map is **cohort membership only**, not a per-case target-action
lookup. The host gate selects a contract by the model's proposed
consequential tool identity, and denies unknown actions. The source-hash
validator rejects forbidden evaluator/gold input paths. This prospective
case-blind method is not yet approved or scored (see #1268).

Each arm's command must declare the same `--model` argument.
All three commands must also explicitly declare the **same** `--backend`
(`codex` or `claude`) and `--strategy baseline`. The launcher additionally
pins `SAFEACT_AGENT_STRATEGY=baseline` for the upstream runner, preventing
ambient SCGR strategy settings from silently confounding the ungated arm.
The scored launcher also rejects differences in pinned upstream CLI runtime
options across arms: `--profile`, `--cfuse-config`, `--cli-bin`,
`--model-catalog`, `--timeout`, `--max-turns`, repeatable
`--extra-arg`, and `--keep-sandbox`. Absent options must be absent in
all arms; identical explicit options must match, including order of repeated
extra arguments. Any runtime-level behavior not described by these flags
(e.g. external CLI configuration, actual service provider or environment
secrets) still requires independent runtime identity and execution audit. The intervention
manifest must bind each condition to the corresponding `ungated`,
`routing_only`, or `evidence_gate` implementation and a pinned 40-character
adapter commit SHA, with explicit review. These are declared identities;
the upstream post-run audit independently checks the **observed model**
and matched public/hidden case fingerprints after all trajectories finish.

The separate `independent_contract_review` entry in the intervention
manifest is also mandatory. It must contain `approved: true`, nonempty
**different** `author` and `reviewer` identities, the SHA-256 digest of
the frozen canonical `contracts.json` under `contract_sha256`, and the
frozen upstream commit under `upstream_revision`. The launcher rejects
missing, self-reviewed, stale or mismatched attestations. The reviewer must
independently check public source authoring and all 131 case mappings before
sign-off. **These fields attest review but cannot cryptographically prove
human authorship, independence or semantic correctness.** Do not set them
merely to make the preflight pass; no score is authorized without the actual
independent review.

By default, this command performs a **preflight only** and does not issue
any model calls. The opt-in `--execute` runs all 131 official V1 cases
for each arm and then runs the official full-pair verifier and post-run
metric aggregator. It aborts on a failed arm rather than reporting
incomplete output as a three-arm result.

**Critical integration requirement:** The command controller does **not**
itself implement the SafeAct agent-tool interception layer. An unreviewed
adapter must not be labeled "SchemaRouter evidence gate". The actual
condition-specific adapter, independent contracts, model credentials, and
runtime action dispatch/denial audit remain prerequisites. Merely creating
an intervention manifest does not prove treatment fidelity.

The aggregator reports official exact-case success, post-run premature
**attempts** and descriptive paired McNemar contrasts. The latter
are unadjusted exploratory statistics, not proof of causality. Unsupported
**executions** and false refusals must remain unmeasured until the trusted
dispatch/denial and counterfactual evaluation boundary is connected.


### Host-side official adapter integration

`official_agent_hook.py` patches the pinned official coding agent's **host-side**
V1 normalization point, not the model or sandbox. The official `ToolGateway`
continues to execute information queries, and only its completed public
`gateway.calls` may contribute verified observations. No hidden SafeAct
requirements or expected decisions are examined by the hook.

The evidence-gate arm must call the hook with `--contract-file`,
`--contract-sha256`, `--public-source-root`, and
`--condition evidence_gate`, followed by the usual official agent
`--backend` / `--model` arguments. The contract hash is computed over
canonical JSON (sorted keys, UTF-8, compact separators). The official
upstream revision, frozen policy source files and 131-case coverage are
verified before invoking the model. The only recognized verifier shape is
an explicit independent `public_observation_mappings` contract, mapping
information-tool names to `record_id_key` and `field_name_key` in the
**actual public returned observations**.

The trusted gate preserves model proposals as counters, denies unsupported
proposals before they enter the official normalized action record and stores
a separate, coarse intervention diagnostic. Denied model proposals
**must not** be counted as physically dispatched actions.

The final orchestrator also requires `verify_arm_interventions()` to
attest every scored case: genuine ungated baseline, SchemaRouter
`schemarouter_typed_route` routing-only records, and
`trusted_official_v1_record_gate` records. The routing-only host adapter is now implemented in
`official_routing_hook.py`. It constructs a real SchemaRouter typed registry
from the **public fixed candidate action** and validates the routed action
before record commit without applying an evidence gate. This only validates
tool identity and object-shaped arguments; it does not infer a complete
vendor parameter schema from example argument values. Actual 131-case
condition fidelity and independent review remain prerequisites. The
post-run verifier still rejects substituting ordinary baseline records.


## Scored GitHub Actions setup and explicit blockers

The scored workflow is
`.github/workflows/safeact-v1-scored.yml`. PR checks intentionally execute
**no model calls** and cannot read production model credentials. The public
131-case listing, synthetic adapter tests, and no-model readiness artifacts
do **not** imply that the scored job ran. To avoid billing an unauthorized
or invalid three-arm comparison, the scored job requires **all** of:

1. Freeze `research/safeact-v1/contracts.json` with 131 complete
   public-case mappings and action-specific evidence requirements.
   Each source file must exist under
   `research/safeact-v1/public-sources/` with a pinned SHA-256.
   Author solely from independently visible public policies/tools.
   Never infer evidence requirements from evaluator, case manifest or gold.
2. Generate the initially **unapproved** three-arm command manifest from
   that contract snapshot and the actual pinned adapter Git commit:

   ```bash
   python -m scripts.prepare_safeact_v1_scored_manifest \
     --contracts research/safeact-v1/contracts.json \
     --out research/safeact-v1/intervention-manifest.json \
     --backend codex --model YOUR_FROZEN_MODEL \
     --adapter-commit YOUR_40_HEX_ADAPTER_COMMIT
   ```

   Have an **actual second person** independently review all source
   citations, mappings, policy semantics and execution adapters.
   Only the reviewers themselves should populate
   `independent_contract_review.author`,
   `independent_contract_review.reviewer`,
   `independent_contract_review.approved=true` and
   `reviewed=true` after completing the review. An auto-generated
   manifest must never self-approve.
3. Configure a **trusted Linux** GitHub Actions runner with labels
   `self-hosted`, `linux`, `safeact-v1`, restricted to approved code.
   The pinned upstream official CLI requires root-owned immutable
   `bwrap`, `/usr/bin/timeout`, `/usr/bin/prlimit`, a working
   Codex/Claude CLI, and an already configured **trusted Unix-socket
   model broker** (`SAFEACT_MODEL_BROKER_DIR`,
   `SAFEACT_MODEL_BROKER_SOCKET`, `SAFEACT_MODEL_BROKER_PORT`).
   These credentials and broker must be supplied on the secured host,
   never committed to the repo or a PR artifact.
4. Protect the GitHub Actions environment `safeact-research`,
   restrict deployment to reviewed `main`, and configure
   environment secret `SAFEACT_V1_RUNTIME_VERIFIED=1` only after
   the authenticated runner has been independently qualified.
   This secret is an authorization marker, not a model credential.
5. Once a reviewed PR is merged, go to **Actions → SafeAct V1
   Scored Experiment (Gated) → Run workflow**, choose the `main`
   branch, enter the exact frozen `model`, and select `execute=true`.
   The workflow first runs readiness checks and then the protected
   runner's `scripts/check_safeact_v1_runner.py` before any agent call.
   Scoring must produce and verify all 393 official trajectories, paired
   intervention attestations, and post-run aggregate artifacts.
   If any check fails, **do not relabel simulation or partial records
   as official V1 results**.

There is deliberately no automatic `push` or `schedule` path that runs
393 paid model calls merely because a new PR was opened. Without the
independent contract review and working external broker, the experiment is
**not ready to execute**; Github reports a successful no-model readiness
job and **skips** the scored job.

No credential-bearing model runtime, independent 131-case policy coverage,
or full 393-case scored result is bundled with these source files.


## Gated GitHub Actions scored experiment and hourly tracking

[`SafeAct V1 Scored Experiment (Gated)`](../../../.github/workflows/safeact-v1-scored.yml)
is the official launch entrypoint. Each pull-request update first runs the
`readiness` job **without credentials, agents or evaluator scores** and uploads
`safeact-v1-scored-readiness.json`. A successful readiness CI job only proves
that the *checker ran*; if the report says `ready: false`, scored execution
**has not started**.

The scored launch is permitted **only after the reviewed workflow is merged
to protected `main`**, via an explicit `workflow_dispatch` with
`execute: true` and the exact frozen `model`. It requires the
`safeact-research` GitHub Environment (with independent approval), a trusted
Linux self-hosted runner labeled `safeact-v1`, verified provider CLI/auth,
and the `SAFEACT_V1_RUNTIME_VERIFIED=1` Environment secret. **Never put
credentials in the repo or in pull-request workflow jobs.**

Independent reviewed material is expected at:

- `research/safeact-v1/contracts.json`: 131 public case mappings, pinned
  independently authored public policy sources, explicit observation mappings.
- `research/safeact-v1/public-sources/`: the exact pinned, independently
  reviewed publicly accessible policy and tool interfaces referenced by hashes.
- `research/safeact-v1/intervention-manifest.json`: exact three conditions,
  pinned actual adapter commits and reviewed agent commands plus SHA-256s,
  independent author/reviewer attestation bound to the frozen contract JSON.

Agent commands must be reviewed as **portable templates**, using
`@SAFEACT_ROOT@` for the pinned official checkout and
`@SCHEMAROUTER_ROOT@` for the reviewed SchemaRouter checkout. Store
`agent_command_sha256` as SHA-256 of the original UTF-8 template, *not*
the machine-specific expanded command. The launcher checks the reviewed
template digest **before** expanding only these two tokens into verified
absolute checkout paths, and separately binds the expanded command hash
in a local ephemeral runtime manifest. This prevents GitHub-hosted readiness
and trusted self-hosted execution from disagreeing solely over workspace
paths while retaining auditable template provenance.

The launcher validates each expanded agent command actually points to the
expected official upstream baseline, SchemaRouter routing adapter or
SchemaRouter EvidenceGate adapter—not merely a command with a matching SHA.
Only on the
approved runner may the `--execute` path issue model calls. The actual
three-arm controller refuses incomplete 131-case sets, invalid intervention
identity, reused/fabricated records and mismatched model/runtime identity,
and then writes `safeact-v1-scored-summary.json` **after** all official
model evaluations pass. Only the post-run aggregate and readiness status
are uploaded; raw hidden evaluator data, agent traces and credentials are
not uploaded as public workflow artifacts.

**Current status:** these three approved inputs and a verified credentialed
research runner are *not yet provided*. The official 393 trajectories are
**not yet running**; simulator and PR preflight checks are unscored. Do not
fake attestations to bypass this safety and scientific-validity boundary.


### Public-domain authorization boundary

The scored V1 adapter must select a trusted contract by the tuple
`(public scenario env_id, model-proposed consequential tool)`. The case ID
is a pairing/cohort identifier, never an expected action label; the tool
name alone is also insufficient because several public SafeAct domains reuse
tool names. For example, the public interfaces in customer policy and legal
finance both expose `reply_send`. Scoped policies cannot be substituted
across domains. Production launch validates recognized public domains and
uniqueness of every `(domain, action)` contract, while missing/unknown
domain scope fails closed. Isolated unscoped synthetic tests are not proof
of a scored-run-ready domain-scoped contract catalogue.

## Unreviewed domain-scoped public action review queue (no models)

The SafeAct preflight also builds a deterministic
`safeact-v1-unreviewed-domain-action-queue` artifact from **only** the
pinned public 131-case ID listing and the template tool/policy filename +
SHA-256 inventory. It retains null-valued case cohort entries, enumerates
each unique `(domain, tool)` source identity, and leaves consequential-action
classification, required evidence, record-field bindings, authorship and
review **unset**. Cross-domain name collisions are distinct entries.

For an equivalent local no-gold preparation:

```bash
python -m scripts.prepare_safeact_v1_review_queue \
  --public-listing safeact-v1-list.json \
  --inventory safeact-v1-public-tool-inventory.json \
  --out safeact-v1-review-queue.json
```

This is an authoring **work queue**, not generated policy semantics,
approved `contracts.json`, validated 131-case action coverage, or an
official model benchmark. A human must independently decide which public
tools are consequential, cite their actual public policy interfaces and
grounded observations, write scoped evidence requirements and obtain
independent second-person approval before the protected scored run.


### Domain-qualified public observation extraction

The scored contract document must declare a nested
`public_observation_mappings` object, e.g.
`{"customer_policy_qa":{"charge_read":{"record_id_key":"subject","field_name_key":"predicate"}}}`.
Every required observation tool needs an extraction rule under its **own**
public `env_id`, not merely a matching tool name in another domain.
The host and launch controller reject legacy flat mappings. Human source
review and approved, grounded evidence semantics remain necessary.


### Independently authored value comparison rules (unapproved draft)

The trusted `EvidenceGate` can now check `value_conditions` only through
strict `eq`, `lte`, `gte` operators, with **left** operand an
`action_argument` or trusted policy-authored scalar `literal` and **right**
operand a real public observation `object`. Every rule binds a declared
`{tool, record_id, field}` observation within the same domain-scoped
contract. Example:

```json
{"value_conditions": [{"tool": "charge_read",
                       "record_id": "$action.charge_id",
                       "field": "amount", "operator": "lte",
                       "action_argument": "refund_amount"}]}
```

Unknown keys, ungrounded fields, contradictory trusted values and unsupported
expressions fail closed. The scored launcher parses all scoped contracts
before starting expensive model work, but neither compilation nor passing
synthetic tests confirms that a policy author's predicates are complete or
correct. Missing required business-specific checks, units, validity windows
and exception handling remain explicit human review blockers (#1269).


## Consequential-action side-effect boundary (2026-10-11)

At pinned upstream SafeAct commit `841816cf1e376e6fbf8600cffac5df1736e1d369`,
the official V1 `normalize_v1()` converts a model-proposed consequential
call into a `CONSEQUENTIAL_CALL` **in the normalized evaluation record**.
The SchemaRouter routing-only and evidence-gate hooks intervene at that
**post-inference, pre-record-commit** seam, and remove/retain the recorded
action. Neither hook invokes a real consequential operation against a live
external system; upstream information-tool `ToolGateway.calls` are actual
read observations and remain a distinct boundary.

The historical intervention counter
`authorized_action_dispatches` therefore counts **authorized recorded
actions**, not audited physical execution of external side effects.
To prevent claim inflation, both intervention arms must attest
`action_effect_boundary="normalized_record_only"` and
`physical_action_execution_observed=false`; the post-run verifier rejects
missing or contradictory side-effect assertions. Aggregate reports explicitly
set `physical_action_executions_measured=false` and must not use retained
record counts to calculate an unsupported-execution or physical
call-blocking rate.

This is still a meaningful benchmark-level interception of the **official
evaluation record** with trace provenance. It is **not** production tool-call
authorization, a SafeActBench task-success improvement result, a covered
131-domain evidence-policy catalogue, or proof of counterfactual false
refusal. A future executor-boundary study requires separately validated real
dispatch interception, and must be labelled as such.
