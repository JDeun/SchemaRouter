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

## 선택적 No-match 실행 차단

위의 `router.ainvoke(...)`는 등록된 기능에 없는 요청을 자동으로
거부하지 않습니다. 가장 비슷한 도구가 실제로는 잘못된 도구일 수 있습니다.
독립적으로 보정한 임계값을 사용할 수 있을 때, 동일한 호스트 권한 범위에서
검색과 실행 계획을 얻은 뒤 선택적 실행 게이트를 명시적으로 사용합니다.

```python
from schemarouter import (
    PlanRequest, PolicyViolationError, RetrievalAbstentionPolicy,
    execute_selective_plan,
)

request = PlanRequest(query=user_request)
policy = RetrievalAbstentionPolicy(min_score=host_config.calibrated_min_score)
retrieval = router.retrieve_executable(request, k=3)
plan = router.plan_executable(request)
try:
    results = await execute_selective_plan(router, retrieval, plan, policy=policy)
except PolicyViolationError:
    results = []  # 게이트에서 거부하면 도구 호출 없음.
```

이 게이트는 No-match로 판단된 후보, 후보 목록 외 도구/대체 경로,
스키마 지문 불일치, 오래되거나 다른 질의의 실행 계획을 실행 전에 거부합니다.
단, **없는 기능을 정확히 식별하는 성능이 입증된 것은 아닙니다.**
지원하는 요청의 과도한 거부와 지원하지 않는 요청의 잘못된 허용은
독립된 데이터로 함께 검증해야 합니다. 기존 `ainvoke()`는
이 선택적 게이트를 거치지 않으며, 호스트 실행 권한 정책도 대체하지 않습니다.
