# 모델 보조 분석

기본 플래너는 `KeywordAnalyzer`를 통해 오프라인에서 동작할 수 있습니다. 자연어 요청에서 도구·엔드포인트·인자·필드·증거 요구사항을 더 풍부하게 추출해야 한다면 `ModelQueryAnalyzer`를 사용하십시오.

## 공급자에 종속되지 않는 callable

SchemaRouter는 특정 LLM SDK를 요구하지 않습니다.

```python
from schemarouter import ModelQueryAnalyzer, SchemaRouter

async def model(payload: dict) -> dict:
    # Bridge to your provider's structured-output API.
    return {
        "preferred_tools": ["users_api"],
        "preferred_endpoints": ["users_api.get_user"],
        "arguments": {"user_id": "42"},
        "fields": ["name", "email"],
        "concepts": [],
        "evidence": {},
    }

router = SchemaRouter(
    analyzer=ModelQueryAnalyzer(model),
)
```

전달되는 페이로드에는 현재 기능 카탈로그와 응답 스키마가 포함됩니다.

이 callable은 애플리케이션에서 이미 사용하는 호스팅 모델 클라이언트로 구현할 수 있습니다. 예를 들어 GPT, Gemini, Claude 또는 다른 공급자의 구조화 출력 API를 연결하되, SchemaRouter 자체에 해당 공급자의 SDK를 추가하지 않아도 됩니다.

이 방식은 범위가 제한된 `DecisionBackend`와 구분됩니다.

| 인터페이스 | 모델에 보이는 정보 | 모델이 반환할 수 있는 정보 | SchemaRouter의 후속 처리 |
| --- | --- | --- | --- |
| `ModelQueryAnalyzer` | 쿼리 + 스키마 카탈로그 + 응답 계약 | 도구/엔드포인트 선호도, 선언된 인자/필드, 개념, 증거 요청 | 모든 값을 현재 레지스트리 기준으로 정제한 뒤 결정론적 계획 실행 |
| `CallableDecisionBackend` | 쿼리 + 이미 허가된 유한한 후보 ID | 제한된 범위의 후보 선택만 가능 | ID 및 개수를 검증한 후 기존 플래너로 진행 |

어느 인터페이스에서도 클라우드 모델이 에이전트 실행 런타임이 되는 것은 아닙니다. 도구 실행, 정책, 스키마 지문, 실행 권한은 계속 SchemaRouter의 로컬 경계 안에 남습니다.

OpenAPI에서 구분자(discriminator)가 있는 요청 본문을 지원하는 경우, 카탈로그에는 원래의 합성 스키마를 유지한 하나의 `body` 파라미터가 들어갑니다. 호스팅 모델은 다음과 같이 반환할 수 있습니다.

```json
{
  "preferred_tools": ["pets"],
  "preferred_endpoints": ["pets.create_pet"],
  "arguments": {
    "body": {
      "kind": "dog",
      "name": "Mong",
      "breed": "retriever"
    }
  },
  "fields": ["id"],
  "concepts": [],
  "evidence": {}
}
```

SchemaRouter는 어떠한 HTTP 요청도 허용하기 전에 그 객체를 엔드포인트의 입력 스키마와 대조해 로컬에서 다시 검증합니다.

## 모델 출력 자체에는 실행 권한이 없습니다

분석기는 응답 형태를 검증한 다음 현재 레지스트리로 다시 투영합니다.

```text
model output
 -> strict shape validation
 -> known tool?
 -> known endpoint?
 -> declared argument?
 -> declared field?
 -> deterministic planner
```

알려지지 않았거나 모델이 임의로 만들어 낸 스키마 요소는 실행 가능한 호출이 될 수 없습니다.

애플리케이션이 명시적으로 제공한 인자는 모델이 생성한 인자보다 우선합니다.

## 원격 설명은 신뢰할 수 없는 데이터입니다

OpenAPI의 description, MCP의 annotation, 문서 텍스트에는 프롬프트 인젝션이나 잘못된 지시가 포함될 수 있습니다. 분석기 프롬프트는 카탈로그 설명을 명시적으로 신뢰할 수 없는 데이터로 취급합니다.

자격 증명을 카탈로그 설명이나 모델에 노출되는 인자에 넣지 마십시오.

## 동기식과 비동기식 호출

`ModelQueryAnalyzer`는 비동기 동작을 지원합니다. 비동기 분석기를 연결했다면 `aplan()`, `ainvoke()` 또는 다른 비동기 실행 인터페이스를 사용하십시오.

비동기 분석기를 동기식 계획 인터페이스에서 호출하면, await되지 않은 코루틴이 조용히 누출되는 대신 명시적으로 실패합니다.
