# Research governance and work-item protocol

SchemaRouter research must remain resumable from repository state alone.

Canonical tracker: GitHub issue **#200**.

## Work-item hierarchy

GitHub Issues are used as the repository equivalent of GitLab work items.

- **Tracker / epic:** #200
- **Historical backfill:** #196
- **Active research candidate:** #197
- **Confirmation evaluation:** #198
- **Paper evidence package:** #199

Existing operational/ecosystem issues are linked from #200.

## Lifecycle

```text
idea
  ↓
work item
  ↓
preregistration
  ↓
implementation
  ↓
development evidence
  ↓
freeze
  ↓
fresh calibration
  ↓
one-shot blind
  ↓
accepted / rejected
  ↓
ledger + paper evidence
```

Not every idea reaches freeze. Rejected development ablations are closed as rejected evidence and remain in the ledger.

## Before changing routing behavior

A behavior-changing experiment must have:

- research question;
- hypothesis;
- exact allowed tuning data;
- forbidden evidence;
- candidate architecture/configuration;
- metrics;
- promotion gates;
- failure/abstention semantics.

Commit the preregistration before implementation whenever feasible.

## Development

Development data may be used to:

- choose architecture;
- select thresholds;
- compare ablations;
- diagnose failure slices.

All such tuning must be recorded.

## Freeze

Before calibration, record:

- exact source revision;
- models;
- representations;
- thresholds;
- routing policy;
- prediction/config digest when practical;
- preregistered calibration gates.

No candidate changes are allowed after freeze.

## Calibration

Calibration is confirmation-only.

If any required gate fails:

- reject the candidate;
- mark calibration consumed;
- do not modify the candidate using those rows;
- start a new development cycle with fresh tuning data if needed.

## Blind final

Generate blind data only after calibration passes.

Evaluate exactly once.

After evaluation, mark blind evidence permanently consumed.

## Invalidated pre-result runs

If a structural/leakage audit invalidates a run before result inspection:

- record the run ID;
- record the reason;
- record whether metrics/artifacts were inspected;
- exclude the run from evidence;
- do not silently delete the event.

## Artifact provenance

For each empirical result preserve when available:

- git/source revision;
- workflow run ID;
- artifact ID;
- artifact digest;
- corpus hash;
- hardware/runtime label;
- exact configuration.

## Session resume

A future session must not infer current work from chat memory.

Read in this order:

1. issue #200;
2. active child issue(s);
3. `benchmarks/research-experiment-ledger.json`;
4. active cycle protocol/result files;
5. open PRs and workflow runs.

Continue the first incomplete task whose prerequisites are satisfied.

## Paper policy

The follow-up paper must include negative evidence, not only successful candidates.

Claims must distinguish:

- architecture/design reasoning;
- development evidence;
- confirmation evidence;
- blind-final evidence;
- retrospective diagnostics.

Calibration or blind data must never be described as tuning evidence when the protocol marks it consumed.
