# Research governance와 work-item protocol

SchemaRouter research는 repository state만으로 재개할 수 있어야 합니다. Canonical tracker는 GitHub Issue #200입니다.

## Work-item hierarchy

GitHub Issue를 GitLab work item에 대응하는 repository mechanism으로 사용합니다.

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

모든 아이디어가 freeze까지 가는 것은 아닙니다. Rejected development ablation은 rejected evidence로 닫고 ledger에 유지합니다.

## Routing behavior 변경 전

Behavior-changing experiment에는 research question, hypothesis, exact allowed tuning data, forbidden evidence, candidate architecture/configuration, metric, promotion gate, failure/abstention semantics가 있어야 합니다. 가능하면 implementation 전에 preregistration을 commit합니다.

## Development

Development data는 architecture 선택, threshold 선택, ablation 비교, failure slice 진단에 사용할 수 있으며 모든 tuning을 기록해야 합니다.

## Freeze

Calibration 전에 exact source revision, model, representation, threshold, routing policy, 가능한 경우 prediction/config digest, preregistered calibration gate를 기록합니다. Freeze 이후 candidate 변경은 허용하지 않습니다.

## Calibration

Calibration은 confirmation-only입니다. Required gate 하나라도 실패하면 candidate를 reject하고 calibration을 consumed로 표시하며 해당 row로 candidate를 수정하지 않습니다. 필요하면 fresh tuning data로 새 development cycle을 시작합니다.

## Blind final

Calibration 통과 후에만 blind data를 생성하고 정확히 한 번 평가합니다. 이후 blind evidence는 영구 consumed로 표시합니다.

## Invalidated pre-result run

Result inspection 전에 structural/leakage audit가 run을 invalidated하면 run ID, 이유, metric/artifact inspection 여부를 기록하고 evidence에서 제외합니다. 사건을 조용히 삭제하지 않습니다.

## Artifact provenance

각 empirical result에서 가능한 경우 git/source revision, workflow run ID, artifact ID/digest, corpus hash, hardware/runtime label, exact configuration을 보존합니다.

## Session resume

미래 session은 chat memory에서 현재 작업을 추론하지 않습니다. Issue #200 → active child issue → `benchmarks/research-experiment-ledger.json` → active cycle protocol/result → open PR/workflow 순서로 읽고 prerequisite를 만족하는 첫 incomplete task를 계속합니다.

## Paper policy

후속 paper에는 successful candidate뿐 아니라 negative evidence도 포함합니다. Claim은 architecture/design reasoning, development evidence, confirmation evidence, blind-final evidence, retrospective diagnostic을 구분해야 합니다. Protocol에서 consumed로 표시된 calibration/blind data를 tuning evidence로 설명해서는 안 됩니다.
