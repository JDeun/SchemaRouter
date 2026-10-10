# Research evidence package

SchemaRouter의 research record는 `benchmarks/research-experiment-ledger.json`에 유지합니다. Ledger가 source of truth이며 paper table은 derived view이므로 독립적인 experimental fact source가 되어서는 안 됩니다.

## Generate

```bash
python scripts/export_research_evidence.py
```

Default output `docs/research/generated/`:

- `research-evidence-package.json` — target, governance, current conclusion, flattened experiment, invalidated run을 포함한 machine-readable aggregate
- `research-experiments.csv` — table-ready experiment/provenance/metric rows
- `invalidated-runs.csv` — model-quality evidence로 인용하면 안 되는 invalid/pre-result technical run
- `research-evidence-table.md` — compact human-readable experiment table

Generated file은 canonical ledger의 대체물이 아니라 build artifact입니다. CI가 exporter를 실행해 paper preparation 전에 schema drift를 잡습니다.

## 0.14 최종 연구 결과 보고서 준비

[0.14 최종 근거 보고서 템플릿](https://github.com/JDeun/SchemaRouter/blob/main/benchmarks/agent-utility-0.14-terminal-report-prep.md)에는
동결된 출처 정보, 홀드아웃 쌍대 비교의 통계 분석 단위, 최종 답변 품질표,
논문 주장 허용 조건, 무효 실행 분류 및 종료 점검표를 정리했습니다.
아직 검증되지 않은 측정값은 추정하지 않고 **Pending(미확정)**으로 표시합니다.

[0.14 실험 컨베이어](https://github.com/JDeun/SchemaRouter/issues/500)는 동결된 실험 순서와 완료 조건을 추적합니다.
컨트롤러 실행이 성공하더라도 내부 상태가 `waiting_heldout`이면 연구가 완료된 것이 아닙니다.
모든 샤드가 모인 정본 아티팩트를 출처 및 집계 기준으로 검증한 뒤에만
연구 결과로 인정합니다. 일부 샤드, 실행 중인 워크플로 또는 인프라 재시도를
완료된 홀드아웃 결과로 서술해서는 안 됩니다.

## Evidence roles

Exporter는 ledger의 evidence-role distinction을 보존합니다. 특히 tuning DEV, fresh confirmation, calibration, blind-final, design-known stress, compatibility, infrastructure evidence를 role 없이 하나의 accuracy table로 합치면 안 됩니다.

Development pass는 generalization claim이 아닙니다. Fresh-confirmation failure는 consumed negative evidence이며 threshold repair에 사용할 수 없습니다. Exact frozen candidate가 repository freeze protocol 아래 새로운 zero-overlap fresh confirmation을 통과할 때까지 calibration/blind-final은 blocked입니다.

## Provenance requirements

Available record가 experiment, source revision, workflow run, artifact/digest, corpus identity/role, frozen configuration, metrics, terminal decision을 식별할 때만 paper-ready입니다. Missing historical field는 missing value로 표시하며 exporter는 provenance를 만들어내지 않습니다.

Invalidated-run table은 contract failure, cancelled pre-result run, leakage incident 등 non-evidence execution이 narrative에서 사라지지 않게 합니다.

## Architecture interpretation

SchemaRouter는 execution authority와 semantic evidence를 분리합니다.

```text
user request
    |
registered schema + local authority
    |
bounded ranking / evidence / veto
    |
accept registered route OR abstain
    |
local validation / policy / execution
```

Semantic model은 preregistered experiment에 따라 finite registered authority 위에서 rank/veto/abstain할 수 있습니다. 새로운 executable tool, endpoint, field, argument, pseudo-route를 만들 수 없습니다.

## Threats to validity

Evidence package의 한계:

- benchmark corpus는 synthetic controlled workload이며 production prevalence/user-distribution performance를 단독으로 입증할 수 없음
- multilingual template coverage는 English-only testing보다 넓지만 각 언어 community의 natural traffic과 동일하지 않음
- GitHub-hosted CPU latency는 reproducible infrastructure evidence이지 universal hardware benchmark가 아님
- canonical DEV에서 반복 architecture search는 selection pressure를 높이므로 zero-overlap fresh confirmation과 one-shot calibration/blind evidence를 분리
- registry description/trusted alias는 tested system의 일부이며 실제 integration마다 quality가 다를 수 있음
- provider/model compatibility는 routing quality evidence가 아님
- aggregate metric은 route/language/family collapse를 숨길 수 있으므로 promotable candidate는 slice diagnostic과 authority/error count를 유지해야 함

## Final-paper closure

Active 0.14 cycle 동안 package를 재생성할 수 있지만 final paper table은 active 또는 infrastructure-invalid run을 scientific evidence로 취급해서는 안 됩니다. 현재 closure path:

- terminal #431 corrective aggregate와 preregistered gate
- terminal #432 large held-out generalization result
- terminal #424 final-answer factual/value/unit/provenance result
- field-level line을 paper에 포함한다면 terminal #510 runtime qualification과 successor projection result

이전 operation-routing lineage의 historical calibration/blind work는 ledger 일부지만 위 frozen 0.14 held-out/final-answer evidence를 대체하지 않습니다. 모든 final table은 consumed/invalid run에서 semantic retuning 없이 canonical ledger와 immutable workflow/artifact provenance로 재구성 가능해야 합니다.
