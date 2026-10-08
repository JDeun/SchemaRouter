# Model-assisted analysis

기본 planner는 `KeywordAnalyzer`로 오프라인에서도 동작합니다. 자연어에서 tool, endpoint, argument, field, evidence requirement를 더 풍부하게 추출해야 할 때 `ModelQueryAnalyzer`를 사용합니다.

## Provider-neutral callable

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

payload에는 현재 catalog와 response schema가 포함됩니다.

callable은 애플리케이션이 이미 사용하는 hosted model client를 사용할 수 있습니다. 예를 들어 GPT, Gemini, Claude 또는 다른 provider의 structured-output API를 연결해도 해당 SDK를 SchemaRouter 자체 dependency로 추가할 필요가 없습니다.

이는 bounded `DecisionBackend`와 별개의 surface입니다.

| Surface | Model이 보는 것 | Model이 반환할 수 있는 것 | 이후 SchemaRouter 동작 |
| --- | --- | --- | --- |
| `ModelQueryAnalyzer` | query + schema catalog + response contract | tool/endpoint preference, 선언된 argument/field, concept, evidence request | 현재 registry에 대해 모두 sanitize한 뒤 deterministic planning |
| `CallableDecisionBackend` | query + 이미 허가된 유한 option ID | bounded option selection만 | ID/count를 검증한 뒤 기존 planner 계속 |

어느 쪽도 cloud model을 agent runtime으로 만들지 않습니다. tool execution, policy, schema fingerprint, authority는 SchemaRouter 로컬에 남습니다.

지원되는 OpenAPI discriminated request body에서는 catalog가 원래 composed schema를 가진 하나의 `body` parameter를 포함합니다. hosted model은 다음처럼 반환할 수 있습니다:

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

HTTP request를 허용하기 전에 SchemaRouter가 이 object를 endpoint input schema에 대해 로컬에서 다시 검증합니다.

## Model output은 실행 권한이 아님

analyzer는 response shape를 검증한 뒤 현재 registry에 다시 projection합니다.

```text
model output
 -> strict shape validation
 -> known tool?
 -> known endpoint?
 -> declared argument?
 -> declared field?
 -> deterministic planner
```

알 수 없거나 모델이 만들어낸 schema element는 executable call이 될 수 없습니다.

애플리케이션이 명시적으로 제공한 argument가 model-produced argument보다 우선합니다.

## Remote description은 untrusted

OpenAPI description, MCP annotation, documentation text에는 prompt injection이나 오도하는 지시가 포함될 수 있습니다. analyzer prompt는 catalog description을 명시적으로 untrusted data로 취급합니다.

credential을 catalog description이나 model-visible argument에 넣지 마세요.

## Sync/async

`ModelQueryAnalyzer`는 async를 지원합니다. async analyzer를 연결했다면 `aplan()`, `ainvoke()` 또는 다른 async execution surface를 사용합니다.

async analyzer를 synchronous planning surface에서 호출하면 un-awaited coroutine을 조용히 누출하지 않고 명시적으로 실패합니다.
