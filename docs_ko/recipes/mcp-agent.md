# MCP 에이전트 실행 경계

애플리케이션이 MCP 서버에서 기능을 탐색하되 원격 서버의 주석(annotation)을 실행 권한의 근거로 받아들이지 않으려는 경우에 사용하는 패턴입니다.

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

## 운영 환경에서의 주의사항

`allow_unclassified_remote=True`는 허용 범위가 넓은 설정입니다. 읽기 도구와 쓰기 도구가 혼재하는 운영 환경에서는 향후 제공될 신뢰 가능한 로컬 분류 계층을 적용하거나 권한 도메인별로 MCP 서버를 분리하는 방식을 우선 고려해야 합니다.

현재 설계는 원격 서버 자체의 주석을 부작용 발생 여부에 대한 최종 판단 근거로 신뢰하지 않습니다.
