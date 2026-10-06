from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest

from schemarouter import ExecutionPolicy, SchemaRouter
from schemarouter.adapters.mcp import (
    MCPDiscoveryLimits,
    inspect_mcp_client_factory,
)
from schemarouter.errors import SchemaSourceError


def _tool(name: str, *, description: str = "") -> dict[str, object]:
    return {
        "name": name,
        "description": description,
        "inputSchema": {"type": "object", "properties": {}},
        "outputSchema": {
            "type": "object",
            "properties": {"value": {"type": "string"}},
        },
    }


class _PagedFactory:
    def __init__(
        self,
        pages: dict[str | None, tuple[list[dict[str, object]], str | None]],
    ) -> None:
        self.pages = pages
        self.calls: list[str | None] = []
        self.client = SimpleNamespace(
            server_info=SimpleNamespace(name="paged-server"),
            protocol_version="2026-06-18",
        )

        async def list_tools(*, cursor=None):
            self.calls.append(cursor)
            tools, next_cursor = self.pages[cursor]
            return SimpleNamespace(tools=tools, next_cursor=next_cursor)

        self.client.list_tools = list_tools

    @asynccontextmanager
    async def __call__(self, *, timeout=20.0):
        del timeout
        yield self.client


@pytest.mark.asyncio
async def test_mcp_discovery_keeps_finite_pagination_compatible() -> None:
    factory = _PagedFactory(
        {
            None: ([_tool("first")], "page-a"),
            "page-a": ([_tool("second")], None),
        }
    )

    tool = await inspect_mcp_client_factory(
        factory,
        discovery_limits=MCPDiscoveryLimits(max_pages=2, max_tools=2),
    )

    assert [endpoint.name for endpoint in tool.endpoints] == ["first", "second"]
    assert factory.calls == [None, "page-a"]


@pytest.mark.asyncio
async def test_mcp_discovery_rejects_same_cursor_repetition() -> None:
    factory = _PagedFactory(
        {
            None: ([_tool("first")], "page-a"),
            "page-a": ([_tool("second")], "page-a"),
        }
    )

    with pytest.raises(SchemaSourceError, match="repeated pagination cursor"):
        await inspect_mcp_client_factory(factory)

    assert factory.calls == [None, "page-a"]


@pytest.mark.asyncio
async def test_mcp_discovery_rejects_cursor_cycle() -> None:
    factory = _PagedFactory(
        {
            None: ([_tool("first")], "page-a"),
            "page-a": ([_tool("second")], "page-b"),
            "page-b": ([_tool("third")], "page-a"),
        }
    )

    with pytest.raises(SchemaSourceError, match="repeated pagination cursor"):
        await inspect_mcp_client_factory(factory)

    assert factory.calls == [None, "page-a", "page-b"]


@pytest.mark.asyncio
async def test_mcp_discovery_bounds_endless_unique_cursors() -> None:
    calls: list[str | None] = []
    client = SimpleNamespace(
        server_info=SimpleNamespace(name="endless"),
        protocol_version="2026-06-18",
    )

    async def list_tools(*, cursor=None):
        calls.append(cursor)
        next_cursor = f"page-{len(calls)}"
        return SimpleNamespace(tools=[_tool(next_cursor)], next_cursor=next_cursor)

    client.list_tools = list_tools

    @asynccontextmanager
    async def factory(*, timeout=20.0):
        del timeout
        yield client

    with pytest.raises(SchemaSourceError, match="page limit"):
        await inspect_mcp_client_factory(
            factory,
            discovery_limits=MCPDiscoveryLimits(max_pages=3),
        )

    assert len(calls) == 3


@pytest.mark.asyncio
async def test_mcp_discovery_bounds_tool_count_before_registration() -> None:
    factory = _PagedFactory(
        {
            None: ([_tool("first"), _tool("second")], None),
        }
    )

    with pytest.raises(SchemaSourceError, match="tool limit"):
        await inspect_mcp_client_factory(
            factory,
            discovery_limits=MCPDiscoveryLimits(max_tools=1),
        )


@pytest.mark.asyncio
async def test_mcp_discovery_rejects_oversized_tool_descriptor() -> None:
    factory = _PagedFactory(
        {
            None: ([_tool("large", description="x" * 1024)], None),
        }
    )

    with pytest.raises(SchemaSourceError, match="per-tool byte limit"):
        await inspect_mcp_client_factory(
            factory,
            discovery_limits=MCPDiscoveryLimits(
                max_tool_bytes=256,
                max_total_bytes=4096,
            ),
        )


@pytest.mark.asyncio
async def test_mcp_discovery_rejects_oversized_aggregate_catalog() -> None:
    factory = _PagedFactory(
        {
            None: (
                [
                    _tool("first", description="x" * 200),
                    _tool("second", description="y" * 200),
                ],
                None,
            ),
        }
    )

    with pytest.raises(SchemaSourceError, match="aggregate byte limit"):
        await inspect_mcp_client_factory(
            factory,
            discovery_limits=MCPDiscoveryLimits(
                max_tool_bytes=1024,
                max_total_bytes=500,
            ),
        )


@pytest.mark.asyncio
async def test_mcp_discovery_applies_timeout_to_whole_catalog_walk() -> None:
    client = SimpleNamespace(
        server_info=SimpleNamespace(name="slow"),
        protocol_version="2026-06-18",
    )

    async def list_tools(*, cursor=None):
        del cursor
        await asyncio.Event().wait()

    client.list_tools = list_tools

    @asynccontextmanager
    async def factory(*, timeout=20.0):
        del timeout
        yield client

    with pytest.raises(SchemaSourceError, match="total timeout"):
        await inspect_mcp_client_factory(factory, timeout=0.01)


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"max_pages": 0}, "max_pages"),
        ({"max_tools": 0}, "max_tools"),
        ({"max_tool_bytes": 0}, "max_tool_bytes"),
        ({"max_total_bytes": 0}, "max_total_bytes"),
        (
            {"max_tool_bytes": 2048, "max_total_bytes": 1024},
            "must not exceed",
        ),
    ],
)
def test_mcp_discovery_limits_validate_positive_budgets(
    kwargs: dict[str, int],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        MCPDiscoveryLimits(**kwargs)


@pytest.mark.asyncio
async def test_router_mcp_registration_is_atomic_when_discovery_limit_fails() -> None:
    factory = _PagedFactory(
        {
            None: ([_tool("first")], "page-a"),
            "page-a": ([_tool("second")], None),
        }
    )
    router = SchemaRouter(
        policy=ExecutionPolicy(allow_unclassified_remote=True)
    )

    with pytest.raises(SchemaSourceError, match="page limit"):
        await router.add_mcp_client_factory(
            factory,
            name="bounded",
            discovery_limits=MCPDiscoveryLimits(max_pages=1),
        )

    assert router.registry.keys() == ()
    assert router.executor.bound_keys() == ()
