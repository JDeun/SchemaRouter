# 외부 사례 연구 템플릿

실제 외부 project/user가 SchemaRouter를 평가한 뒤에만 사용합니다. 존재하지 않는 도입 사례처럼 project 이름을 미리 채우지 않습니다.

## 허가

- 공개 project/user 이름:
- 공개 evaluation/integration URL:
- 이름 공개 허가: yes / no
- 인용 허가: yes / no
- logo 사용 허가: yes / no / not requested
- 허가 확인일:
- 공개 근거:

private contact detail은 기록하지 않습니다.

## Context / 환경

어떤 application/agent stack인지, tool/capability/provider 수, 평가 계기, 기존 discovery/filtering 방식을 기록합니다. downstream commit, SchemaRouter version, Python/runtime, 관련 model/provider/hardware/integration package version도 고정합니다.

## Integration surface

실제 사용한 가장 작은 경계를 기술하고 agent orchestration/tool retrieval/execution approval/transport lifecycle/schema validation/output projection의 소유자를 명확히 구분합니다.

## Workload

request/task 수, 결과 확인 전후 생성 여부, 최소 하나의 unsupported/no-route request, adversarial/ambiguous request, 공개 가능한 재현 데이터를 기록합니다.

## Before / after

| Metric | Before | With SchemaRouter | 측정 참고 |
| --- | ---: | ---: | --- |
| model-visible tools |  |  |  |
| serialized schema bytes 또는 실제 model tokens |  |  | 단위를 정확히 표시 |
| required-tool recall |  |  |  |
| task completion |  |  |  |
| unsupported false-route rate |  |  |  |
| added routing latency p50/p95 |  |  |  |
| execution/validation failures |  |  |  |

측정 효과, maintainer/user qualitative feedback, 해석을 분리하고 주관적 comment를 quantitative claim으로 바꾸지 않습니다.

## 한계와 artifact

모든 사례에는 single application/small workload/untuned baseline/byte-vs-token/no production traffic/single-machine latency/provider drift 등 해당 한계를 기록합니다. downstream PR/commit, runnable example, benchmark output, feedback issue/PR, independent reproduction을 연결합니다.

Evidence level은 E1 public evaluation, E2 reproducible downstream branch/PR/test, E3 released/default downstream use, E4 independent reproduction 중 하나를 사용합니다. quote는 명시적 허가가 있을 때만 포함합니다.
