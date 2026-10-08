# 외부 사례 연구 템플릿

실제 외부 프로젝트나 사용자가 SchemaRouter를 평가한 뒤에만 이 템플릿을 사용합니다. 실제 도입이
확인되지 않았는데 프로젝트 이름을 미리 채워 넣지 않습니다.

## 허가

- 공개 프로젝트/사용자 이름:
- 공개 평가/integration URL:
- 프로젝트 이름 공개 허가: yes / no
- 인용 허가: yes / no
- 로고 사용 허가: yes / no / not requested
- 허가 확인 날짜:
- 공개 허가 근거(있는 경우):

비공개 연락처 정보는 이 파일에 기록하지 않습니다.

## 맥락

- 어떤 application/agent stack을 만들고 있었는가?
- tool/capability/provider가 몇 개였는가?
- 어떤 문제가 평가를 시작하게 했는가?
- 기존 tool discovery/filtering 방식은 무엇이었는가?

## 환경

- downstream project version/commit:
- SchemaRouter version/commit:
- Python/runtime:
- 관련되는 경우 model/provider:
- 관련되는 경우 hardware:
- 관련 integration package와 version:

## Integration 경계

실제로 사용한 가장 작은 경계를 설명합니다.

```text
existing agent/runtime
    -> <SchemaRouter retrieval / execution boundary>
    -> existing tool/MCP/provider surface
```

다음 책임을 어느 시스템이 소유하는지 명확히 적습니다.

- agent orchestration;
- tool retrieval;
- execution approval/policy;
- transport lifecycle;
- schema validation;
- output projection.

## Workload

평가 request/task를 설명합니다.

다음을 포함합니다.

- request/task 수;
- 결과를 보기 전 또는 후에 만들어졌는지;
- unsupported/no-route request 최소 1개;
- adversarial 또는 ambiguous request;
- 공개 가능한 경우 workload를 재현하는 데 필요한 정확한 데이터.

## 전/후 비교

| 지표 | 이전 | SchemaRouter 적용 | 측정 메모 |
| --- | ---: | ---: | --- |
| model-visible tools |  |  |  |
| serialized schema bytes 또는 실제 model tokens |  |  | 단위를 정확히 표시 |
| required-tool recall |  |  |  |
| task completion |  |  |  |
| unsupported false-route rate |  |  |  |
| added routing latency p50/p95 |  |  |  |
| execution/validation failures |  |  |  |

실제로 측정한 경우에만 domain-specific metric을 추가합니다.

## 결과

무엇이 달라졌는지 구체적으로 요약합니다. 다음을 분리합니다.

- 측정된 효과;
- maintainer/user의 정성적 피드백;
- 해석.

주관적 의견을 정량적 주장으로 바꾸지 않습니다.

## 한계

모든 case study에는 한계를 포함해야 합니다. 예:

- downstream application 하나만 평가;
- 작거나 무작위가 아닌 workload;
- framework-native filtering을 튜닝하지 않음;
- model token 대신 byte count 사용;
- production traffic 없음;
- 한 머신에서만 latency 측정;
- provider/version이 바뀔 수 있음;
- SchemaRouter를 execution이 아니라 retrieval에만 사용.

## Artifact

- downstream PR/commit:
- 실행 가능한 example:
- benchmark/evaluation output:
- 피드백에서 생성된 SchemaRouter issue/PR:
- 독립 재현(있는 경우):

## 근거 수준

하나를 선택합니다.

- E1 — 공개 외부 평가;
- E2 — downstream에서 재현 가능한 branch/PR/test;
- E3 — downstream released/default 사용;
- E4 — 독립 benchmark/reliability 재현.

## 인용

명시적 허가가 있을 때만 인용을 포함합니다.

> _선택적 공개 인용문_

출처:
