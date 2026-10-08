# LangGraph

SchemaRouter는 planning, policy, schema validation, execution authority를 SchemaRouter 내부에 유지하면서 native LangGraph `StateGraph` node로 실행할 수 있습니다.

## 설치

사용자 설치:

```bash
pip install "schemarouter[langgraph]"
```

저장소 개발 환경:

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

Node는 synchronous 및 asynchronous graph execution을 모두 지원합니다.

```python
state = graph.invoke(
    {
        "query": "current weather",
        "arguments": {"city": "Seoul"},
    }
)

state = await graph.ainvoke(
    {
        "query": "current weather",
        "arguments": {"city": "Seoul"},
    }
)
```

## 기본 state contract

기본 node는 다음 두 형식 중 하나를 받습니다:

1. a complete request in `state["schemarouter_request"]` as a string, `PlanRequest`, or mapping
   compatible with `PlanRequest`; or
2. a string at `state["query"]` plus an optional mapping at `state["arguments"]`.

결과는 partial LangGraph state update로 반환됩니다:

```python
{
    "schemarouter_results": [
        {
            "tool": "...",
            "endpoint": "...",
            "data": ...,
            "projected_fields": [...],
        }
    ]
}
```

결과는 기본적으로 JSON serialize되어 checkpointing과 persistence에 적합하게 유지됩니다.
Set `serialize_results=False` when an in-process graph wants typed `ToolResult`
objects.

## Application별 state 적용

A graph does not need to adopt SchemaRouter's default keys. Use `request_factory` to translate
arbitrary graph state into a bounded SchemaRouter request:

```python
node = to_langgraph_node(
    router,
    request_factory=lambda state: {
        "query": state["task"],
        "arguments": {
            "city": state["selected_city"],
        },
    },
    result_key="tool_results",
)
```

The factory may return a string, a `PlanRequest`, or a mapping compatible with `PlanRequest`.

## Trust boundary

The graph node does not expose the registered invoker directly.

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

LangGraph is responsible for graph control flow, checkpointing, memory, runtime context, and
human-in-the-loop orchestration. SchemaRouter is responsible for schema-aware tool planning
and validated execution.

The LangGraph `RunnableConfig` and SchemaRouter `RunConfig` are intentionally not conflated.
Pass a SchemaRouter `run_config` explicitly when constructing the node.

## 실행 가능한 예제

```bash
python examples/langgraph_quickstart.py
```

CI compiles and executes a real `StateGraph` in both sync and async modes.
