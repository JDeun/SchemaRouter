# LangGraph

SchemaRouter can run as a native LangGraph `StateGraph` node while keeping planning, policy,
schema validation, and execution authority inside SchemaRouter.

## Install

For consumers:

```bash
pip install "schemarouter[langgraph]"
```

For repository development:

```bash
pip install -e ".[dev,langgraph]"
```

The core package does not depend on LangGraph.

## Add SchemaRouter as a graph node

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

The node supports both synchronous and asynchronous graph execution:

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

## Default state contract

The default node accepts either:

1. a complete request in `state["schemarouter_request"]` as a string, `PlanRequest`, or mapping
   compatible with `PlanRequest`; or
2. a string at `state["query"]` plus an optional mapping at `state["arguments"]`.

The result is returned as a partial LangGraph state update:

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

Results are JSON-serialized by default so they remain friendly to checkpointing and persistence.
Set `serialize_results=False` when an in-process graph intentionally wants typed `ToolResult`
objects.

## Adapt an application-specific state

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

LangGraph remains responsible for graph control flow, checkpointing, memory, runtime context, and
human-in-the-loop orchestration. SchemaRouter remains responsible for schema-aware tool planning
and validated execution.

The LangGraph `RunnableConfig` and SchemaRouter `RunConfig` are intentionally not conflated.
Pass a SchemaRouter `run_config` explicitly when constructing the node.

## Runnable example

```bash
python examples/langgraph_quickstart.py
```

CI compiles and executes a real `StateGraph` in both sync and async modes.
