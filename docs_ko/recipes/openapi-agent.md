# OpenAPI agent 경계

상위 agent는 자유롭게 대화 추론을 수행하되 tool 실행은 schema contract 안에 제한해야 할 때 사용하는 패턴입니다.

```python
from schemarouter import (
    ExecutionPolicy,
    ModelQueryAnalyzer,
    PlanRequest,
    SchemaRouter,
)

async def structured_model(payload: dict) -> dict:
    # 모델 provider에 연결합니다.
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

## 이 경계가 유효한 이유

상위 agent는 여전히 SchemaRouter에 tool result를 **언제** 요청할지 결정할 수 있습니다. 요청 이후 실행 가능한 operation은 현재 imported schema, 명시적 caller argument, local execution policy, schema fingerprint 검사, input/output validation으로 제한됩니다.

따라서 model reasoning은 유연하게 유지하면서 transport contract까지 같은 수준으로 느슨해지는 것을 막습니다.
