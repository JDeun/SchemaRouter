# MCP agent 경계

애플리케이션이 MCP server에서 capability를 탐색하되 원격 annotation을 권한으로 받아들이고 싶지 않을 때 사용하는 패턴입니다.

```python
from schemarouter import ExecutionPolicy, PlanRequest, SchemaRouter

router = await SchemaRouter.from_url(
    "http://localhost:8000/mcp",
    kind="mcp",
    policy=ExecutionPolicy(
        allow_unclassified_remote=True,
    ),
)

results = await router.ainvoke(
    PlanRequest(
        query="add result",
        arguments={"a": 2, "b": 3},
    )
)
```

## Production 참고

`allow_unclassified_remote=True`는 허용 범위가 넓습니다. read/write MCP tool이 섞인 production 환경에서는 신뢰된 로컬 분류 계층을 사용하거나 권한 domain별로 server를 분리하는 편이 낫습니다.

현재 설계는 원격 server 자체 annotation을 최종 side-effect 판단으로 신뢰하지 않습니다.
