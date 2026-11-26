from typing import Any, TypedDict

import pytest

pytest.importorskip("langgraph")

from langgraph.graph import END, START, StateGraph
from test_paper_configured_planning import _configure, _configured

from schemarouter import PlanRequest, RunConfig, SchemaRouter, SchemaValidationError, schema_tool
from schemarouter.integrations import to_langgraph_node
from scripts.research_legacy_router import legacy_router


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
    router = legacy_router()
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

@pytest.mark.asyncio
@pytest.mark.parametrize("request_kind", ["model", "mapping", "factory"])
async def test_configured_langgraph_preserves_source_local_host_arguments(request_kind):
    ctx = _configured(count=2, needs_input=True)
    request = ctx.request
    options = {"run_config": RunConfig(principal=ctx.principal)}
    if request_kind == "factory":
        options["request_factory"] = lambda _state: request.model_dump(mode="json")
        state = {}
    else:
        state = {"schemarouter_request": (
            request if request_kind == "model" else request.model_dump(mode="json")
        )}
    result = await to_langgraph_node(ctx.router, **options).ainvoke(state)
    assert sorted(item["tool"] for item in result["schemarouter_results"]) == [
        "source_0", "source_1",
    ]
    assert all(arguments == {"sample_id": "host-7"} for _, _, arguments in ctx.seen)
    assert len(ctx.model.payloads) == 1


def test_langgraph_node_created_before_configuration_uses_current_paper_mode():
    ctx = _configured(count=1, needs_input=False, configure=False)
    node = to_langgraph_node(ctx.router, run_config=RunConfig(principal=ctx.principal))
    _configure(ctx)
    result = node.invoke({"query": ctx.request.query})
    assert [item["tool"] for item in result["schemarouter_results"]] == ["source_0"]
    assert len(ctx.model.payloads) == 1


@pytest.mark.parametrize("state", [
    {"query": "measurement value", "arguments": {"sample_id": "SECRET_CANARY"}},
    {"query": "measurement value", "host_source_arguments": {"source_0.read": {}}},
    {"schemarouter_request": {
        "query": "measurement value", "arguments": {"sample_id": "SECRET_CANARY"},
    }},
    {"schemarouter_request": PlanRequest(query="measurement value")},
])
def test_configured_langgraph_never_reinterprets_flat_arguments_or_leaks_values(state):
    ctx = _configured(count=1, needs_input=True)
    node = to_langgraph_node(ctx.router, run_config=RunConfig(principal=ctx.principal))
    with pytest.raises((TypeError, ValueError)) as caught:
        node.invoke(state)
    assert "SECRET_CANARY" not in str(caught.value)
    assert ctx.model.payloads == [] and ctx.seen == []
