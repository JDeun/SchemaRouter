import pytest

pytest.importorskip("llama_index.core")

from schemarouter import SchemaRouter, SchemaValidationError, schema_tool
from schemarouter.integrations import to_llamaindex_tool, to_llamaindex_tools


@schema_tool(read_only=True)
def add(a: int, b: int) -> int:
    """Add two integers."""
    return a + b


def make_router() -> SchemaRouter:
    router = SchemaRouter()
    router.add_callable(add)
    return router


def test_llamaindex_tool_preserves_metadata_and_sync_execution() -> None:
    router = make_router()
    tool = to_llamaindex_tool(router, "add", "call")

    assert tool.metadata.name == "schemarouter__add__call"
    assert tool.metadata.description == "Add two integers."
    assert tool(a=2, b=3).raw_output == 5


@pytest.mark.asyncio
async def test_llamaindex_tool_supports_async_execution() -> None:
    router = make_router()
    tool = to_llamaindex_tool(router, "add", "call")

    result = await tool.acall(a=4, b=5)
    assert result.raw_output == 9


def test_llamaindex_tool_still_enforces_schemarouter_validation() -> None:
    router = make_router()
    tool = to_llamaindex_tool(router, "add", "call")

    with pytest.raises(SchemaValidationError):
        tool(a="not-an-int", b=3)


def test_llamaindex_tool_collection_exports_registered_endpoints() -> None:
    tools = to_llamaindex_tools(make_router())
    assert [tool.metadata.name for tool in tools] == ["schemarouter__add__call"]
