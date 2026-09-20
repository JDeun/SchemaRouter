import pytest

from schemarouter import SchemaRouter, schema_tool
from schemarouter.integrations import to_langchain_tool, to_langchain_tools


@schema_tool(read_only=True)
def add(a: int, b: int) -> int:
    """Add two integers."""
    return a + b


def make_router() -> SchemaRouter:
    router = SchemaRouter()
    router.add_callable(add)
    return router


def test_langchain_tool_preserves_schema_and_sync_execution() -> None:
    router = make_router()
    tool = to_langchain_tool(router, "add", "call")

    assert tool.name == "schemarouter__add__call"
    assert tool.description == "Add two integers."
    assert tool.args_schema["properties"]["a"]["type"] == "integer"
    assert tool.args_schema["properties"]["b"]["type"] == "integer"
    assert tool.invoke({"a": 2, "b": 3}) == 5


@pytest.mark.asyncio
async def test_langchain_tool_supports_async_execution() -> None:
    router = make_router()
    tool = to_langchain_tool(router, "add", "call")

    assert await tool.ainvoke({"a": 4, "b": 5}) == 9


def test_langchain_tool_still_enforces_schemarouter_validation() -> None:
    router = make_router()
    tool = to_langchain_tool(router, "add", "call")

    with pytest.raises(Exception):
        tool.invoke({"a": "2", "b": 3})


def test_langchain_tool_collection_exports_registered_endpoints() -> None:
    router = make_router()
    tools = to_langchain_tools(router)

    assert [tool.name for tool in tools] == ["schemarouter__add__call"]
