# Microsoft-Decision-1 — 호스팅 의사결정 모델 후보 조사(#1324)

**상태: 도입 후보만 등록, SchemaRouter 실측 검증 없음. 무료 로컬 모델도
아니며 실제 실행 권한 정책을 대체하지 않습니다.**
확인일: 2026-10-13.

## 모델 개요

Microsoft가 **2026-10-09**에 발표한 **Microsoft-Decision-1**은
Qwen3.5-9B를 의사결정에 맞게 추가 학습한 호스팅 모델입니다.
일반적인 문장 생성 대신 `choice`(유한 선택지),
`noul`(참/거짓 확률), `score`(등급 점수)를 반환합니다.
Microsoft의 36종 벤치마크 주장은 공급사 자체 결과이며
SchemaRouter에서 재현된 품질 지표가 아닙니다.

- 공식 발표: https://commandline.microsoft.com/microsoft-decision-1-model-foundry/
- Microsoft Foundry: https://learn.microsoft.com/en-us/azure/foundry/foundry-models/how-to/use-foundry-models-microsoft-decision
- OpenRouter: https://openrouter.ai/microsoft/microsoft-decision-1/

2026-10-13 확인 기준 공식 입력 가격은 **100만 토큰당 $0.042**,
출력 토큰 비용은 **$0**입니다. Foundry는 Azure 결제 계정과
배포 및 인증이 필요하고, OpenRouter 역시 API 계정이 필요합니다.
Microsoft가 추가 학습한 모델의 가중치는 공개되지 않았습니다.
공개 Qwen3.5 기반 모델을 실행하는 것은 동일 모델 재현이 아닙니다.

## 전송 프로토콜과 기존 구현 차이

Foundry의 공식 요청 주소는
`<Azure 리소스 엔드포인트>/providers/microsoft/v1/systemone`이며
Entra Bearer 토큰 또는 `api-key` 헤더로 인증합니다.
요청 전송 형식은 다음과 같으며, 리소스 엔드포인트와 인증 값은 실제 배포에서만 설정합니다.

```text
POST <foundry-resource-endpoint>/providers/microsoft/v1/systemone
Content-Type: application/json
api-key: <foundry-key>
# OR: Authorization: Bearer <Entra access token>
```

요청은 `state`, `questions`와
`model`로 구성되며, **Foundry의 `model`은 배포 이름**입니다.
OpenRouter에서 사용하는 ID는 별도로
`microsoft/microsoft-decision-1`입니다.

등록된 도구와 명시적인 미지원 요청 거부 옵션을 포함한 요청 예시입니다.

```json
{
  "model": "<the-created-Foundry-deployment-name>",
  "state": {
    "query": "Cancel a customer's order."
  },
  "questions": {
    "route": {
      "type": "choice",
      "instructions": "Select a supported route. Choose none_of_above if no registered route performs the requested action.",
      "criteria": {
        "orders_lookup": "Look up an order; cannot cancel it",
        "none_of_above": "No offered route supports the requested operation"
      }
    }
  }
}
```

SchemaRouter의 `SystemOneDecisionBackend`는 현재
**TypeSafe SDK의 `system_one()` 응답과 `response.choices`**
형식을 사용합니다. Foundry 공식 HTTP 응답은 `answers`를
사용하므로 기존 SDK에 Foundry `base_url`만 지정해
동작한다고 확인된 상태가 **아닙니다**. OpenRouter의
Decisions API도 실제 인증·응답 구조를 별도로 검증해야 합니다.
우선 별도의 HTTP/Callable 실험 연결 경로에서
문자열 ID, 0~1 유한 확률 및 인증·전송 실패를
fail-closed 검증하는 것이 적절합니다.

## 없는 기능 요청을 거부하는 실험(#1291)

`choice`는 제시된 후보 하나를 선택합니다. 등록 도구에
없는 기능을 자동으로 거부한다고 가정하면 안 됩니다.
예를 들어 주문 **조회**만 가능한 도구를 제공한 상태에서
주문 **취소**를 요구하면, 선택지에 `none_of_above`
(해당 기능 없음)를 명시하고 그 선택이 실제 거부로 이어지도록
실행 전에 차단해야 합니다.

실험은 기존 ClicShopping 공개 DEV 실패 사례와 다른 신규
독립 데이터에서 다음 항목을 나누어 측정합니다.

- 지원 기능의 정확한 도구 선택과 정상 요청 오거부
- 미지원·유사 미지원·금지 요청의 잘못된 도구 선택 및 올바른 거부
- 확률 보정, 옵션 순서·문구 변화 민감도
- 실제 왕복 지연시간, 오류율, 사용 토큰, 당시 가격·배포 버전

## 근거와 도입 판정 기준

Jev 측의 2026-10-11 OpenRouter 비교(한 차례)에서는 없는
도구 거부율이 Microsoft 92.5%, Jev 88.8%였지만
제3자·동일 조건에서 SchemaRouter가 재현한 결과는 아닙니다.
해당 실험에서는 Jev의 API 왕복 지연시간이 약간 짧았습니다.
Microsoft의 발표 수치 역시 서로 다른 서빙 경로를 포함하므로
실제 애플리케이션에서 재검증해야 합니다.

이 문서와 후보 등록은 **실행 정책, 기존 임계값, 0.14 동결
실험을 변경하지 않으며**, 유료 API를 호출하지 않습니다.
이슈 #1324는 실제 인증·응답 호환성 및 독립적인
No-match 검증 완료 전까지 열어둡니다.
