# OpenAPI 에이전트 실행 경계

상위 에이전트가 대화와 추론은 자유롭게 수행하되 도구 실행은 스키마 계약 안에 제한해야 할 때 사용하는 패턴입니다.

```python
from schemarouter import (
    ExecutionPolicy,
    ModelQueryAnalyzer,
    PlanRequest,
    SchemaRouter,
)


async def structured_model(payload: dict) -> dict:
    # Bridge to your model provider.
    ...


router = await SchemaRouter.from_url(
    "https://docs.example.com/openapi.json",
    kind="openapi",
    analyzer=ModelQueryAnalyzer(structured_model),
    base_url="https://api.example.com/",
    trusted_headers={"Authorization": "Bearer ..."},
    policy=ExecutionPolicy(
        allow_mutations=False,
        allow_destructive=False,
    ),
)

request = PlanRequest(
    query="Find user 42 and return only the name and email",
    arguments={"user_id": "42"},
)

results = await router.ainvoke(request)
```

## 이러한 실행 경계가 유효한 이유

상위 에이전트는 SchemaRouter에 도구 실행 결과를 **언제 요청할지** 여전히 결정할 수 있습니다. 일단 요청하면 실행 가능한 작업에는 다음 제약이 적용됩니다.

- 현재 가져온 스키마
- 호출자가 명시적으로 제공한 인자
- 로컬 실행 정책
- 스키마 지문 검사
- 입력 및 출력 검증

따라서 모델의 추론은 유연하게 유지하되 전송 계층의 실행 계약까지 같은 수준으로 느슨하게 만들지는 않습니다.
