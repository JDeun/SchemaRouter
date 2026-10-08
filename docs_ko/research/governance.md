# Research governance 및 work-item protocol

SchemaRouter research는 repository state만으로도 이어서 진행할 수 있어야 합니다.

정본 tracker: GitHub issue #200.

## Work-item 계층

GitHub Issues를 GitLab work item에 대응하는 repository 단위로 사용합니다.

- **Tracker / epic:** #200
- **Historical backfill:** #196
- **Active research candidate:** #197
- **Confirmation evaluation:** #198
- **Paper evidence package:** #199

기존 operational/ecosystem issue는 #200에서 연결합니다.

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

모든 idea가 freeze 단계까지 도달하는 것은 아닙니다. Rejected development ablation은 rejected evidence로 종료하고 ledger에 남깁니다.

## Routing behavior 변경 전

Behavior를 변경하는 experiment에는 다음 항목이 필요합니다:

- research question;
- hypothesis;
- exact allowed tuning data;
- forbidden evidence;
- candidate architecture/configuration;
- metrics;
- promotion gates;
- failure/abstention semantics.

가능한 경우 implementation 전에 preregistration을 commit합니다.

## Development

Development data는 다음 용도로 사용할 수 있습니다:

- choose architecture;
- select thresholds;
- compare ablations;
- diagnose failure slices.

이러한 tuning은 모두 기록해야 합니다.

## Freeze

Calibration 전에 다음을 기록합니다:

- exact source revision;
- models;
- representations;
- thresholds;
- routing policy;
- prediction/config digest when practical;
- preregistered calibration gates.

Freeze 이후에는 candidate를 변경할 수 없습니다.

## Calibration

Calibration은 confirmation 전용입니다.

If any required gate fails:

- reject the candidate;
- mark calibration consumed;
- do not modify the candidate using those rows;
- start a new development cycle with fresh tuning data if needed.

## Blind final

Calibration을 통과한 뒤에만 blind data를 생성합니다.

정확히 한 번만 평가합니다.

평가 후 blind evidence를 영구적으로 consumed 상태로 표시합니다.

## 결과 전 무효화된 run

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

## Session 재개

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
