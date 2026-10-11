# SafeAct V1 repeated-trajectory preregistration integrity preflight

**Status: prospective, unscored engineering instrument. Not a frozen or
approved repetition study.** Tracks [#1263](https://github.com/JDeun/SchemaRouter/issues/1263).
The original 131 × 3 single-rollout plan in draft PR #1212 and all 0.14
frozen research inputs remain unchanged. No hidden evaluator, expected target
action, gold labels, model credential or scored agent trajectory is read here.

## Contract and exact paired schedule

`scripts/check_safeact_v1_repeated_prereg.py` requires **real, independently
retrieved public V1 case IDs**, supplied as a JSON list of exactly 131 unique
opaque strings. Do not use the scored evaluator or case gold to produce this
list. The script does not invent or scrape IDs.

The separate `plan.json` uses exactly these fields:

| Field | Design requirement |
| --- | --- |
| `schema_version, study, status, approved` | `1`, `safeact-v1-repeated-trajectory`, `draft`, `false` |
| `pins` | upstream V1 SHA, public case-list digest, model identity/revision, adapter Git SHA, contract/runtime/annotation rubric SHA-256 values |
| `arms` | exact original 3 SafeAct V1 arms, in fixed order |
| `seeds, repetitions` | fixed identifiers for at least 2 independent repeats; count matches exact seed list |
| `analysis` | `cluster_unit: case_id`, `annotation_sample: all`, `annotators_per_item: 2` or more |
| `methods` | nonempty predeclared precision/budget rationale, runtime reset, retry, missingness, randomness, blinding limitation policies |

`pins.public_cases_sha256` equals SHA-256 of canonical JSON of the **sorted**
public IDs (`sort_keys=True`, compact separators, UTF-8). The tool validates
hex syntax and these identities; **it cannot independently confirm model
weights, real author independence, source-policy correctness, or that a
human-authored plan was frozen before any results were examined**.

The `schedule.json` contains exactly:

```json
{
  "schema_version": 1,
  "plan_sha256": "<SHA256 of canonical plan.json>",
  "runs": [
    {
      "case_id": "<opaque public ID>",
      "seed_id": "<predeclared seed>",
      "arm": "SAFEACT-UNGATED",
      "execution_id": "<unique opaque execution ID>",
      "session_id": "<unique independently reset session ID>"
    }
  ]
}
```

The complete array must enumerate **each public case × seed × three arms
exactly once**. Duplicate or missing case/seed/arm tuples, extra unknown
conditions, unapproved outcomes/labels, shared execution IDs or shared
session IDs fail closed. A plan edit after schedule generation changes its
digest and invalidates the schedule. The schedule declares isolation; the
future protected runner must independently attest actual session resets.

## Run an offline preflight

```bash
python scripts/check_safeact_v1_repeated_prereg.py \
  --plan path/to/plan.json \
  --public-case-ids path/to/public-v1-ids.json \
  --schedule path/to/schedule.json
```

A successful result means only that a **draft** has coherent identities,
planned pair coverage and declared independence. At two repetitions, this
means **131 × 2 × 3 = 786 planned executions**, not any executed
or officially scored trajectories. Do not name this a CI qualification of
SafeAct policies or launch authorization.

## Reviewer blinding and annotation coverage

After schedule audit, produce **two separate files** in precreated,
access-controlled directories:

```bash
python scripts/check_safeact_v1_repeated_prereg.py \
  --plan path/to/plan.json \
  --public-case-ids path/to/public-v1-ids.json \
  --schedule path/to/schedule.json \
  --blind-queue-out reviewer-only/queue.json \
  --private-linkage-out trusted-parent-only/linkage.json
```

The reviewer queue exposes **random opaque `blind_id` values only**, in
randomized order, plus the immutable plan digest. The private linkage maps
each ID to case, seed, condition, execution and session. Both files are
created exclusively with owner-only file permissions where supported;
existing files and symlinks cannot be overwritten. The two output
directories must differ. Do not publish the private linkage or combine it
with reviewers' files in CI artifacts.

Before any annotation, a trusted parent should verify the reviewer list and
private linkage together against the exact frozen schedule (do **not** give
reviewers access to this command's linkage inputs):

```bash
python scripts/check_safeact_v1_repeated_prereg.py \
  --plan path/to/plan.json \
  --public-case-ids path/to/public-v1-ids.json \
  --schedule path/to/schedule.json \
  --blind-queue-in reviewer-only/queue.json \
  --private-linkage-in trusted-parent-only/linkage.json
```

This rejects stale plan hashes, missing/duplicated reviewer IDs, fabricated
executions, altered case/seed/arm/session assignments and linkage tables that
are not a one-to-one mapping to all preregistered runs. It validates
metadata identity only, not actual trajectory content or human blindness.

A **separately built trajectory renderer** must present sanitized records
using blind IDs and strip intervention-specific markers, tool/event
annotations, gold results and condition-identifying content. This tool does
**not** render or inspect trajectory text: structural pseudonyms alone
cannot guarantee reviewer blindness.

For an all-trajectory annotation audit, an independent annotation assignment
file contains:

```json
{
  "schema_version": 1,
  "plan_sha256": "<matching canonical plan SHA256>",
  "items": [
    {
      "blind_id": "<ID from reviewer queue>",
      "annotator_id": "<independent human reviewer ID>",
      "decision_sha256": "<64 lowercase hex of a separately stored decision>"
    }
  ]
}
```

Check it with `--blind-queue-in reviewer-only/queue.json
--annotations reviewer-only/annotations.json` and the same required
plan/case-list/schedule flags. Every planned blind ID must have at least
two **distinct** annotator IDs; unknown IDs, duplicated person/trajectory
pairs, unexpected extra fields and modified plan digests are rejected.
These checks cannot prove that two identifiers correspond to different
people, actual blinding or annotation quality. Human reviewer governance,
adjudication and a preregistered rubric remain mandatory.

## Pre-aggregate execution receipts (no scoring)

A future trusted runner can assemble `receipts.json` using only immutable
schedule IDs, actual post-run artifact SHA-256 identities and **one** of the
following administrative states: `completed`, `missing`, `infra_failed`.
A missing or failed run must have `artifact_sha256: null`; a completed run
requires a lowercase 64-digit artifact digest. There must be one receipt
for **every preregistered execution**, without duplicate IDs or changed
session bindings. This preserves intention-to-treat accounting without
silently dropping unsuccessful executions.

```json
{
  "schema_version": 1,
  "plan_sha256": "<matching canonical plan SHA256>",
  "runs": [
    {
      "execution_id": "<registered execution ID>",
      "session_id": "<registered independent session ID>",
      "state": "infra_failed",
      "artifact_sha256": null
    }
  ]
}
```

Run the same basic CLI with `--receipts path/to/receipts.json` for this
pre-aggregate **identity/missingness audit**. It reports only counts by
administrative state, not success/failure of any SafeAct task. It does
not authenticate artifact bytes, model/backend identity or reviewer
quality, and it **does not compute scores or statistical intervals**.
Those are separate, approved trusted-runner and blinded-analysis stages.

## Scientific boundary and release gate

- A repeated rollout is **not** a new independent scenario. Case-clustered
  inference must retain the 131 public cases as statistical units. This
  preflight validates the declared clustering, not the eventual statistical
  estimator or confidence-interval implementation.
- Failures and missingness must remain visible in the planned schedule and
  the eventual intention-to-treat ledger. This checker **does not** fabricate
  outcomes or convert an absent result into a failed/passed score.
- No hidden-gold or post-hoc result adaptation is permitted. Preserve
  negative and undecidable adjudications.
- Keep this entire workflow **unscored and unapproved**. Draft PR #1212,
  independent source-contract author/reviewer approval, protected Linux
  runner/model broker qualification, and the first 393 real official model
  trajectories remain separate prerequisites. A future reviewed/frozen
  repetition protocol needs a distinct authorization and immutable release
  artifact; changing `status` to `frozen` or `approved` to `true`
  is intentionally **rejected** by this preflight.

Run `pytest tests/test_check_safeact_v1_repeated_prereg.py` for synthetic
no-model regression coverage. This PR alone **does not close #1263**.
