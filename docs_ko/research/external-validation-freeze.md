# 외부 검증 동결 패키지

외부 프로젝트가 교차 평가 참여를 결정하기 전에 검토 가능한 평가 패키지를 요구할 때 사용하는
공통 계약입니다.

이 패키지는 framework-neutral합니다. 비교의 출처와 평가 권한을 고정할 뿐,
SchemaRouter가 상대 프로젝트의 실행 권한을 가져오지 않습니다.

## scoring 전에 고정할 항목

다음을 결과 확인 전에 고정합니다.

1. SchemaRouter와 상대 프로젝트의 정확한 commit SHA
2. 양쪽이 공통으로 사용하는 catalog, SHA-256, 출처, 라이선스
3. field-contract label의 출처와 digest
4. supported / unsupported / ambiguous case와 tool/field ground truth
5. 동일한 Top-K와 schema disclosure budget
6. cold/hot latency 정의, warmup 횟수, 측정 횟수
7. 상대 시스템이 discovery와 activation을 나누는 경우 candidate recall과 activation recall의 구분

`benchmarks/external-validation-freeze-manifest.template.json`에서 시작합니다.
필수 artifact와 digest가 모두 확정되기 전에는 `status`를 `frozen`으로 바꾸지 않습니다.

첫 scoring 전에 다음 validator를 실행합니다.

```bash
python scripts/validate_external_validation_freeze.py path/to/frozen-manifest.json
```

출처, label, budget, field recall, unsupported rejection, offline execution boundary,
freeze governance가 불완전하면 validator가 fail-closed합니다.

## metric 의미

**Tool recall**과 **field recall**은 별도 지표입니다. 상대 시스템이 올바른 tool을 찾지만 output
field를 선택하지 않는다면 tool recall은 측정하되 SchemaRouter metadata를 사용해 상대 시스템의
field 선택을 임의로 만들어내지 않습니다.

상대 시스템이 2단계 discovery/activation 구조라면 **candidate recall**과
**activation recall**도 분리합니다.

**Exposed schema bytes**는 frozen budget 아래 실제 downstream agent/model에 공개된 canonical
UTF-8 schema byte입니다. Source-code byte는 별도로 보고할 수 있지만 wire/schema byte와
혼합하지 않습니다.

**Unsupported rejection**은 catalog에 요청을 만족하는 capability가 없는 case를 측정합니다.
**Ambiguous abstention**은 frozen label상 clarification 또는 abstention이 필요한 의도적
불충분 요청을 측정합니다.

## latency

Cold/hot 정의는 scoring 전에 고정합니다. 일반적인 offline 정의는 다음과 같습니다.

- cold: index/model/catalog 초기화를 포함한 첫 process invocation
- hot: 같은 process에서 고정된 횟수의 untimed warmup 이후 retrieval

결과를 공개할 때 hardware/environment도 함께 기록합니다. GPU HYSET latency와 CPU
SchemaRouter latency를 hardware label 없이 직접 비교하지 않습니다.

## 현재 외부 검증 queue

- HYSET (#795): discovery anchor `93808cb8d633b6b685f0f9353923b27c2ad7ad81`. Source는 MIT이지만 `data/hyset_corpus.json`은 ToolBench 파생 데이터이므로 ToolBench 조건을 따릅니다. 호환되는 공개 ToolBench subset을 사용하고 라이선스가 허용하지 않는 데이터는 재배포하지 않습니다.
- pi-jev (#796): discovery anchor `c5b5847aa189fe5ffec52893b7051fe8f9e7a548`, MIT. 작은 shared catalog를 먼저 고정하고 Jev tool activation과 SchemaRouter field narrowing을 별도 지표로 기록합니다.
- hope-agent (#799): discovery anchor `2784abba5823922dba06a3c722eba0ca91f69fd6`, MIT. 상대 maintainer가 참여 여부를 결정하기 전에 이 frozen decision package를 먼저 요청했습니다.

위 SHA는 조사 시점 anchor이며 영구 benchmark pin이 아닙니다. 실제 비교 manifest는 catalog/case를
동결하는 시점에 사용한 정확한 commit을 기록해야 합니다.
