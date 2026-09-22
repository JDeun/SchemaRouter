from typing import Any, TypedDict

import pytest

pytest.importorskip("langgraph")

from langgraph.graph import END, START, StateGraph

from schemarouter import PlanRequest, SchemaRouter, SchemaValidationError, schema_tool
from schemarouter.integrations import to_langgraph_node


@schema_tool(read_only=True)
def add(a: int, b: int) -> int:
    """Add two integers."""
    return a + b


class GraphState(TypedDict, total=False):
    query: str
    arguments: dict[str, Any]
    schemarouter_request: dict[str, Any]
    schemarouter_results: list[Any]


def make_router() -> SchemaRouter:
    router = SchemaRouter()
    router.add_callable(add)
    return router


def make_graph(node):
    builder = StateGraph(GraphState)
    builder.add_node("schema_router", node)
    builder.add_edge(START, "schema_router")
    builder.add_edge("schema_router", END)
    return builder.compile()


def test_langgraph_node_runs_inside_stategraph_sync() -> None:
    graph = make_graph(to_langgraph_node(make_router()))

    state = graph.invoke(
        {
            "query": "add two integers",
            "arguments": {"a": 2, "b": 3},
        }
    )

    assert state["schemarouter_results"][0]["tool"] == "add"
    assert state["schemarouter_results"][0]["endpoint"] == "call"
    assert state["schemarouter_results"][0]["data"] == 5


@pytest.mark.asyncio
async def test_langgraph_node_runs_inside_stategraph_async() -> None:
    graph = make_graph(to_langgraph_node(make_router()))

    state = await graph.ainvoke(
        {
            "query": "add two integers",
            "arguments": {"a": 4, "b": 5},
        }
    )

    assert state["schemarouter_results"][0]["data"] == 9


def test_langgraph_node_accepts_full_plan_request_from_state() -> None:
    node = to_langgraph_node(make_router())

    update = node.invoke(
        {
            "schemarouter_request": PlanRequest(
                query="add two integers",
                arguments={"a": 6, "b": 7},
            )
        }
    )

    assert update["schemarouter_results"][0]["data"] == 13


def test_langgraph_node_supports_custom_request_factory_and_result_key() -> None:
    node = to_langgraph_node(
        make_router(),
        request_factory=lambda state: {
            "query": "add two integers",
            "arguments": {
                "a": state["left"],
                "b": state["right"],
            },
        },
        result_key="tool_results",
    )

    update = node.invoke({"left": 8, "right": 9})

    assert update["tool_results"][0]["data"] == 17


def test_langgraph_node_can_return_typed_tool_results() -> None:
    node = to_langgraph_node(make_router(), serialize_results=False)

    update = node.invoke(
        {
            "query": "add two integers",
            "arguments": {"a": 10, "b": 11},
        }
    )

    result = update["schemarouter_results"][0]
    assert result.data == 21
    assert result.tool == "add"


def test_langgraph_node_rejects_invalid_default_state_contract() -> None:
    node = to_langgraph_node(make_router())

    with pytest.raises(TypeError, match="non-empty string"):
        node.invoke({"arguments": {"a": 1, "b": 2}})

    with pytest.raises(TypeError, match="must be a mapping"):
        node.invoke({"query": "add two integers", "arguments": ["a", 1]})


def test_langgraph_node_still_enforces_schemarouter_validation() -> None:
    node = to_langgraph_node(make_router())

    with pytest.raises(SchemaValidationError):
        node.invoke(
            {
                "query": "add two integers",
                "arguments": {"a": "not-an-int", "b": 3},
            }
        )
