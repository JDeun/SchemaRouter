"""Minimal runnable LangGraph StateGraph integration example."""

from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from schemarouter import SchemaRouter, schema_tool
from schemarouter.integrations import to_langgraph_node


@schema_tool(read_only=True)
def add(a: int, b: int) -> int:
    """Add two integers through the SchemaRouter execution boundary."""
    return a + b


class State(TypedDict, total=False):
    query: str
    arguments: dict[str, Any]
    schemarouter_results: list[dict[str, Any]]


def main() -> None:
    router = SchemaRouter()
    router.add_callable(add)

    builder = StateGraph(State)
    builder.add_node("schema_router", to_langgraph_node(router))
    builder.add_edge(START, "schema_router")
    builder.add_edge("schema_router", END)
    graph = builder.compile()

    state = graph.invoke(
        {
            "query": "add two integers",
            "arguments": {"a": 2, "b": 3},
        }
    )

    assert state["schemarouter_results"][0]["data"] == 5
    print(state["schemarouter_results"][0]["data"])


if __name__ == "__main__":
    main()
