# LangChain

SchemaRouter는 LangChain runtime을 대체하지 않고 optional boundary로 통합됩니다.

## 설치

```bash
pip install "schemarouter[langchain]"
```

core package는 LangChain에 의존하지 않습니다.

## 기존 LangChain tool 가져오기

LangChain `BaseTool` / `StructuredTool` object를 SchemaRouter canonical capability model로 컴파일하고 일반 execution pipeline에 바인딩할 수 있습니다.

```python
from langchain_community.tools import DuckDuckGoSearchRun
from schemarouter import SchemaRouter

router = SchemaRouter()
key = router.add_langchain_tool(
    DuckDuckGoSearchRun(),
    provider="duckduckgo",
    read_only=True,
    remote=True,
)
```

declared input/output schema를 읽되 tool description에서 read/write authority를 추론하지 않습니다. `read_only`, `destructive`, `remote`, `provider`, `access_mode`는 trusted local classification입니다.

## 등록 endpoint 내보내기

`to_langchain_tools(router)` 또는 `to_langchain_tool(router, "weather", "current")`로 SchemaRouter endpoint를 LangChain `StructuredTool`로 노출할 수 있습니다.

`AuthorizationPolicy`를 사용하는 경우 host가 검증한 principal을 `RunConfig`로 함께 전달합니다.

```python
from schemarouter import PrincipalContext, RunConfig

employee = PrincipalContext(
    subject="alice",
    roles=("employee",),
    attributes={"department": "sales"},
)

tools = to_langchain_tools(
    router,
    run_config=RunConfig(principal=employee),
)
```

이 경우 principal에게 보이는 endpoint만 export하고, DataScope가 숨기는 field/parameter는
LangChain tool schema에도 노출하지 않습니다. 실제 호출도 `SchemaRouter.execute(...)` 경로로
돌아가므로 trusted row/tenant filter와 execution-time authorization이 유지됩니다.

## Live export contract

`StructuredTool`은 export 시점에 principal에게 허용된 endpoint contract를 고정합니다.
호출 직전에는 현재 registry의 endpoint를 다시 조회하고 AuthorizationPolicy와 DataScope를
다시 적용합니다. schema, tool fingerprint, 또는 허용된 projection이 export 시점과 달라졌다면
실행 전에 `StaleExportedToolError`로 종료합니다.

schema refresh나 authorization policy 변경 뒤에는 `to_langchain_tool(...)` 또는
`to_langchain_tools(...)`로 다시 export해야 합니다. 따라서 오래된 framework tool이 현재보다
넓거나 다른 contract로 조용히 재바인딩되지 않습니다.

## 실행 경계

LangChain tool 호출도 SchemaRouter `ToolCall` → current schema validation → `ExecutionPolicy` → binding-drift check → trusted invoker → output validation을 거칩니다. 따라서 direct 사용과 같은 fail-closed contract가 적용됩니다.

agent graph/conversation/model invocation/checkpoint/memory는 LangChain/LangGraph가, tool catalog schema와 endpoint/argument/field plan, side-effect policy, execution validation은 SchemaRouter가 담당하는 구성이 권장됩니다.

bridge는 main distribution의 `langchain` extra에 유지합니다. 별도 package는 독립 release cadence나 dependency pressure, upstream 요구가 생길 때 검토합니다.
