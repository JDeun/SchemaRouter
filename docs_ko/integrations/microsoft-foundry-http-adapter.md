# Microsoft-Decision-1 Foundry HTTP 어댑터(선택적 연동, #1324)

**상태: 가짜 HTTP 기반 구조 검증 코드만 구현.**
실제 Azure Foundry 배포에 호출하거나 성능·없는 기능 거부율을
측정한 결과가 아닙니다. 기본 백엔드로 설정하지 않습니다.

공식 문서:
https://learn.microsoft.com/en-us/azure/foundry/foundry-models/how-to/use-foundry-models-microsoft-decision

Microsoft Foundry는 리소스의
`/providers/microsoft/v1/systemone`에
`model`(Foundry **배포 이름**), `state`, `questions`를
보내고 JSON `answers`를 받습니다.
기존 `SystemOneDecisionBackend`의 TypeSafe SDK
`response.choices` 방식과 다르므로
`MicrosoftDecisionOneFoundryBackend`를 별도로 제공합니다.

## 호출 예시(명시적 동의 시)

```python
import os

from schemarouter import DecisionOption, DecisionRequest, choose_sync
from schemarouter.integrations import MicrosoftDecisionOneFoundryBackend

backend = MicrosoftDecisionOneFoundryBackend(
    resource_endpoint=os.environ["AZURE_ENDPOINT"],
    deployment=os.environ["DEPLOYMENT_NAME"],  # Foundry 배포 이름
    api_key=os.environ["AZURE_API_KEY"],
)
request = DecisionRequest(
    query="고객 주문을 취소해줘",
    options=[
        DecisionOption(
            id="orders_lookup",
            description="주문 조회만 가능. 취소 불가능",
        ),
        DecisionOption(
            id="none_of_above",
            description="이 중 요청한 작업을 수행할 도구 없음",
        ),
    ],
)
decision = choose_sync(backend, request)
if decision.abstained:
    # 실제 도구 호출 금지. 사용자 확인이나 담당자 검토로 이동.
    ...
else:
    # 선택된 도구라도 기존 실행 권한·인수·스키마를 다시 검증.
    ...
```

인증은 `api_key` 또는 `bearer_token`을 **하나만** 허용하고
HTTPS 리소스 주소만 받습니다. 실제 `decide()` 호출 시
호스팅 API 비용이 발생하므로 애플리케이션에서 키·과금을
명시적으로 관리해야 합니다. OpenRouter는 별도 API입니다.

현재는 도구 선택용 **`choice`만** 구현했습니다.
`noul`이나 `score` 응답을 도구 ID로 오인하지 않으며,
문자열 선택 ID와 실제 등록된 ID를 정확하게 대조합니다.
`none_of_above`가 없으면 요청 전에 실패하고,
이 선택지가 선택되면 명시적인 **실행 거부**를 반환합니다.

모델은 실제 응답의 확률 직렬화 방식이 문서와 다를 수
있으므로 유효한 `probabilities` 맵이 없는 경우
**임의의 신뢰도 점수를 만들어내지 않습니다**(`score=None`).
이 값은 자동 승인이나 임계값으로 사용할 수 없습니다.
불리언·문자열 선택 ID, 비유한 확률, 중복 JSON 키,
허용되지 않은 선택지·비정상 토큰 수·전송 실패는 거부합니다.
옵션별 확률 정보가 반환되었다면 선택된 ID가 **단독 최고 확률**
이어야 합니다. 확률 동률이나 `none_of_above`의 확률이
더 높은데 다른 도구를 선택한 모순된 응답은 실패로 처리합니다.
이는 응답 무결성 검사이며 미지원 기능 분류 성능의 보정이 아닙니다.

옵션 내부 메타데이터와 `context`는 기본적으로 전송하지
않습니다. `include_context=True`는 호스트가 정보 공개를
승인한 때에만 사용해야 합니다.

회귀 테스트는 전부 `httpx.MockTransport`를 사용해
HTTP 요청 형식과 거부 경계를 확인합니다.
**실제 Microsoft API 응답 호환성, 모델 버전, 안전한
No-match 정확도, 실제 비용·지연시간은 검증하지 않았습니다.**
독립 작성한 새 지원·미지원·금지 요청 자료와 실행 안전성
검증(#1291)이 후속 작업으로 필요합니다.

### 전송 크기 제한 및 불필요한 호출 차단

요청 전에 검증을 우회해 복사한 Pydantic 객체의 선택지도 다시
검사합니다. **실제 도구 후보 없이 `none_of_above`만 있으면**
유료 요청을 전송하지 않습니다. 전송할 JSON은 비유한 값이나
직렬화 불가 객체를 거부하고, 1MiB를 넘는 본문도 미리 차단합니다.

응답은 `httpx.Client.stream`으로 읽으면서 압축 해제 후 최대
1MiB만 허용합니다. 응답 전체를 메모리에 받은 뒤 크기를 검사하는
방식을 피하고, 제한 초과 시 스트림을 닫습니다. 가짜 스트리밍
응답과 크기 초과 및 비정상 context에 대한 회귀 테스트를 추가했지만
실제 Microsoft 호스팅 환경의 응답을 검증한 것은 아닙니다.
