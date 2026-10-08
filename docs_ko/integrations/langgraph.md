# LangGraph

SchemaRouter는 planning, policy, schema validation, execution authority를 내부에 유지하면서 native LangGraph `StateGraph` node로 실행할 수 있습니다.

## 설치

Consumer:

```bash
pip install "schemarouter[langgraph]"
```

Repository development:

```bash
pip install -e ".[dev,langgraph]"
```

Core package는 LangGraph에 의존하지 않습니다.

## SchemaRouter를 graph node로 추가

```python
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph
from schemarouter.integrations import to_langgraph_node

class State(TypedDict, total=False):
    query: str
    arguments: dict[str, Any]
    schemarouter_results: list[dict[str, Any]]

builder = StateGraph(State)
builder.add_node("schema_router", to_langgraph_node(router))
builder.add_edge(START, "schema_router")
builder.add_edge("schema_router", END)
graph = builder.compile()
```

Node는 sync/async graph execution을 모두 지원합니다.

```python
state = graph.invoke({"query": "current weather", "arguments": {"city": "Seoul"}})
state = await graph.ainvoke({"query": "current weather", "arguments": {"city": "Seoul"}})
```

## Default state contract

Default node는 `state["schemarouter_request"]`의 string/`PlanRequest`/compatible mapping 또는 `state["query"]` string과 optional `state["arguments"]` mapping을 받습니다.

Result는 partial LangGraph state update로 반환합니다.

```python
{
    "schemarouter_results": [
        {"tool": "...", "endpoint": "...", "data": ..., "projected_fields": [...]}
    ]
}
```

기본적으로 checkpoint/persistence에 적합하도록 JSON serialize합니다. In-process graph에서 typed `ToolResult`가 필요하면 `serialize_results=False`를 사용합니다.

## Application-specific state 적용

`request_factory`로 arbitrary graph state를 bounded SchemaRouter request로 변환할 수 있습니다.

```python
node = to_langgraph_node(
    router,
    request_factory=lambda state: {
        "query": state["task"],
        "arguments": {"city": state["selected_city"]},
    },
    result_key="tool_results",
)
```

Factory는 string, `PlanRequest`, compatible mapping을 반환할 수 있습니다.

## Trust boundary

Graph node는 registered invoker를 직접 노출하지 않습니다.

```text
LangGraph StateGraph
 -> SchemaRouter Runnable node
 -> SchemaRouter planning
 -> current schema validation
 -> ExecutionPolicy / approval / budgets
 -> binding-drift check
 -> trusted invoker
 -> output validation
 -> partial graph-state update
```

LangGraph는 graph control flow, checkpointing, memory, runtime context, human-in-the-loop orchestration을 담당합니다. SchemaRouter는 schema-aware tool planning과 validated execution을 담당합니다.

LangGraph `RunnableConfig`와 SchemaRouter `RunConfig`는 의도적으로 합치지 않습니다. Node 생성 시 SchemaRouter `run_config`를 명시적으로 전달합니다.

## Runnable example

```bash
python examples/langgraph_quickstart.py
```

CI는 실제 `StateGraph`를 sync/async mode 모두에서 compile하고 실행합니다.
