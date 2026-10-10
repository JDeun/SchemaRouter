# Operation-routing freeze protocol

SchemaRouter는 routing candidate가 independent confirmation, calibration 또는 blind evaluation에 들어가기 전에 freeze합니다.

목적은 evaluated system을 움직이는 research configuration이 아니라 reproducible object로 만드는 것입니다.

## Canonical production target

Machine-readable source of truth:

`benchmarks/operation-routing-production-targets.json`

Freeze manifest는 이 target block을 정확히 복사하며 validator는 canonical target file과의 drift를 거부합니다.

## Freeze 시점

모든 canonical development target 통과 후에만 freeze합니다.

- supported exact-route accuracy >= 85%
- near-domain unsupported rejection >= 97%
- OOD rejection = 100%
- false-route rate <= 1%
- authority violations = 0
- execution errors = 0
- target combined p95 <= 250 ms

Quality pass + latency miss는 별도 preregistered runtime-only optimization에 들어갈 수 있지만 semantic behavior는 변하지 않아야 합니다.

## Freeze에 포함할 것

`benchmarks/operation-routing-freeze-manifest.template.json`에서 시작합니다.

Template을 candidate-specific JSON으로 복사합니다. DEV candidate freeze 뒤 status는 `frozen-dev`, independent fresh confirmation 통과 뒤에만 `fresh-confirmed`를 사용합니다.

정확히 기록:

- SchemaRouter source revision
- architecture identifier
- route-authority와 verifier/veto role
- model/checkpoint/provider/runtime revision; model revision은 immutable Git/Hugging Face commit 또는 immutable provider model/version ID
- Python/dependency/hardware identity
- query/capability/prompt representation digest
- option ordering rule
- decision rule과 threshold
- development corpus/workflow/artifact provenance
- development metrics
- 독립적인 신규 확인용 코퍼스·워크플로·산출물의 출처 기록
- fresh-confirmation metrics

DEV freeze validation:

```bash
python scripts/validate_operation_routing_freeze_manifest.py \
  benchmarks/<candidate-freeze>.json \
  --phase dev
```

Independent fresh confirmation을 기록한 뒤 status를 `fresh-confirmed`로 바꾸고 `--phase fresh`로 다시 validate합니다. Missing provenance, target drift, authority drift, invalid digest 또는 standing gate 미달 evidence에서 fail합니다.

Manifest authority invariants:

- finite locally registered ID만 선택 가능
- winner reject 후 rank-2 fallthrough 없음
- pseudo-route 없음
- external model은 execution authority를 만들 수 없음

## Confirmation boundary

Development pass만으로 충분하지 않습니다.

Exact candidate를 freeze한 뒤 failed #270/#287 surface와 다른 **new zero-overlap fresh confirmation surface**를 생성합니다. Frozen candidate를 semantic retuning 없이 한 번 실행합니다.

Failed confirmation corpus는 영구 confirmation-only입니다. 다음에 재사용 금지:

- threshold 선택
- prompt 변경
- alias 추가
- route/language/family exception 생성
- model 선택
- verifier train/calibrate

Independent confirmation을 생존한 candidate만 #198에 들어갈 수 있습니다.

Ownership:

- **#197: 개발 데이터 평가 → 정확한 동결 → 독립적인 신규 확인 평가**
- validated `fresh-confirmed` manifest 이후 **#198: calibration → one-shot blind-final**

## Calibration과 blind-final

이슈 #197이 validated `fresh-confirmed` manifest를 만들면 #198이 나머지 evidence sequence를 소유합니다.

1. 새로운 900-case calibration corpus 생성
2. unchanged frozen candidate로 calibration 정확히 한 번 평가
3. calibration pass 후에만 새로운 1,800-case blind-final corpus 생성
4. blind-final 정확히 한 번 평가

Calibration/blind evidence는 사용 후 consumed 상태이며 tuning으로 재활용할 수 없습니다.

## Runtime-only optimization

Quality가 pass하고 latency가 fail하면 exact semantic decision function을 보존하는 경우에만 quantization/execution backend 같은 implementation detail을 바꿀 수 있습니다.

```bash
python scripts/validate_routing_runtime_parity.py \
  --reference artifacts/reference/analysis.json \
  --candidate artifacts/optimized/analysis.json \
  --route-field predicted \
  --score-field supported_probability \
  --threshold 0.95 \
  --out artifacts/runtime-parity.json
```

실제 frozen route/score field와 threshold를 사용합니다. BGE+external-gate composition에서는 `raw_top_route`가 route field가 될 수 있습니다. Validator 요구:

- identical case IDs
- zero execution/authority errors
- 모든 case의 selected route 동일
- 모든 case의 execute/abstain decision 동일
- probability-drift distribution과 reference decision-boundary margin 기록

Route change 또는 threshold crossing은 semantic difference이므로 runtime-only optimization으로 취급할 수 없습니다. Parity failure에서도 validator는 requested JSON report를 먼저 쓰고 non-zero exit하여 mismatch case와 probability drift를 terminal research evidence로 보존합니다.

Optimized runtime은 calibration 전에 자체 recorded identity와 confirmation이 필요합니다.

## Evidence recording

모든 terminal phase에서 보존:

- source SHA
- corpus seed/hash
- workflow run ID
- artifact ID/digest
- exact model/runtime identity
- aggregate 및 required slice metrics
- authority/error counts
- terminal decision/interpretation

Frozen candidate/evidence phase가 변할 때 #200, #197, research ledger, design/experiment history, #199를 업데이트합니다. Fresh confirmation 통과 후 #198도 업데이트하고 unchanged frozen candidate의 ownership을 calibration/blind evaluation으로 이전합니다.
