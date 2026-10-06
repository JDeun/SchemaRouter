from __future__ import annotations

from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest

from schemarouter import SchemaRouter
from schemarouter.errors import SchemaSourceError


class RefreshableBoundFactory:
    def __init__(self) -> None:
        self.description = "Return identity"
        self.required_query = False
        self.extra_tool = False
        self.calls = 0
        self.client = SimpleNamespace(
            server_info=SimpleNamespace(name="bound-refresh"),
            protocol_version="2026-07-28",
        )

        async def list_tools(*, cursor=None):
            properties = {}
            required = []
            if self.required_query:
                properties["query"] = {"type": "string"}
                required.append("query")
            tools = [
                {
                    "name": "whoami",
                    "description": self.description,
                    "inputSchema": {
                        "type": "object",
                        "properties": properties,
                        "required": required,
                    },
                    "outputSchema": {
                        "type": "object",
                        "properties": {
                            "subject": {"type": "string"},
                        },
                    },
                }
            ]
            if self.extra_tool:
                tools.append(
                    {
                        "name": "health",
                        "description": "Return health",
                        "inputSchema": {"type": "object", "properties": {}},
                        "outputSchema": {
                            "type": "object",
                            "properties": {"ok": {"type": "boolean"}},
                        },
                    }
                )
            return SimpleNamespace(
                tools=tools,
                next_cursor=None,
            )

        async def call_tool(endpoint, arguments):
            assert endpoint == "whoami"
            return SimpleNamespace(
                is_error=False,
                structured_content={"subject": "bound"},
            )

        self.client.list_tools = list_tools
        self.client.call_tool = call_tool

    @asynccontextmanager
    async def __call__(self, *, timeout=20.0):
        del timeout
        self.calls += 1
        yield self.client


@pytest.mark.asyncio
async def test_bound_mcp_watcher_refreshes_without_fabricating_source_url() -> None:
    factory = RefreshableBoundFactory()
    router = SchemaRouter()
    tool = await router.add_mcp_client_factory(
        factory,
        name="bound-refresh",
        transport="inprocess",
        transport_fingerprint="fixture-inprocess-v1",
    )
    original_fingerprint = tool.fingerprint

    assert "source_url" not in tool.metadata
    assert "source_url" not in tool.execution_metadata

    router.register_schema_watch(tool.key, interval_seconds=60)
    factory.description = "Return current identity"

    snapshots = await router.check_schema_watches_once()
    refreshed = router.registry.get(tool.key)

    assert snapshots[0].status == "applied"
    assert snapshots[0].last_compatibility == "compatible"
    assert refreshed.fingerprint != original_fingerprint
    assert refreshed.endpoint("whoami").description == "Return current identity"
    assert "source_url" not in refreshed.metadata
    assert "source_url" not in refreshed.execution_metadata
    assert router.executor.binding_status_for_contract(
        tool.key,
        refreshed.fingerprint,
    ) == "ready"


@pytest.mark.asyncio
async def test_bound_mcp_breaking_refresh_stays_pending_and_keeps_binding() -> None:
    factory = RefreshableBoundFactory()
    router = SchemaRouter()
    tool = await router.add_mcp_client_factory(
        factory,
        name="bound-refresh",
        transport="inprocess",
        transport_fingerprint="fixture-inprocess-v1",
    )
    accepted_fingerprint = tool.fingerprint

    router.register_schema_watch(tool.key, interval_seconds=60)
    factory.required_query = True

    snapshots = await router.check_schema_watches_once()
    current = router.registry.get(tool.key)
    pending = router.schema_watch_pending_review(tool.key)

    assert snapshots[0].status == "pending_review"
    assert snapshots[0].last_compatibility == "breaking"
    assert pending is not None
    assert pending.action == "pending_review"
    assert current.fingerprint == accepted_fingerprint
    assert router.executor.binding_status_for_contract(
        tool.key,
        accepted_fingerprint,
    ) == "ready"


@pytest.mark.asyncio
async def test_bound_mcp_pending_candidate_can_be_explicitly_accepted() -> None:
    factory = RefreshableBoundFactory()
    router = SchemaRouter()
    tool = await router.add_mcp_client_factory(
        factory,
        name="bound-refresh",
        transport="inprocess",
        transport_fingerprint="fixture-inprocess-v1",
    )
    router.register_schema_watch(tool.key, interval_seconds=60)
    factory.required_query = True

    await router.check_schema_watches_once()
    pending = router.schema_watch_pending_review(tool.key)

    assert pending is not None
    assert pending.candidate_fingerprint is not None
    result = await router.aaccept_schema_watch_pending(
        tool.key,
        expected_candidate_fingerprint=pending.candidate_fingerprint,
    )

    current = router.registry.get(tool.key)
    assert result.action == "applied"
    assert result.compatibility == "breaking"
    assert current.fingerprint == pending.candidate_fingerprint
    assert current.endpoint("whoami").parameters[0].required is True
    assert router.executor.binding_status_for_contract(
        tool.key,
        current.fingerprint,
    ) == "ready"
    assert router.schema_watch_pending_review(tool.key) is None


@pytest.mark.asyncio
async def test_bound_mcp_refresh_fails_closed_without_current_transport_binding() -> None:
    factory = RefreshableBoundFactory()
    router = SchemaRouter()
    tool = await router.add_mcp_client_factory(
        factory,
        name="bound-refresh",
        transport="inprocess",
        transport_fingerprint="fixture-inprocess-v1",
    )
    router.executor.unbind(tool.key)

    with pytest.raises(
        SchemaSourceError,
        match="no current trusted MCP transport binding",
    ):
        await router.arefresh_schema(tool.key)


@pytest.mark.asyncio
async def test_bound_mcp_refresh_preserves_discovery_tool_budget() -> None:
    factory = RefreshableBoundFactory()
    router = SchemaRouter()
    tool = await router.add_mcp_client_factory(
        factory,
        name="bounded-refresh",
        transport="inprocess",
        transport_fingerprint="fixture-inprocess-v1",
        max_tools=1,
    )
    accepted_fingerprint = tool.fingerprint
    factory.extra_tool = True

    with pytest.raises(SchemaSourceError, match="max_tools=1"):
        await router.arefresh_schema(tool.key)

    current = router.registry.get(tool.key)
    assert current.fingerprint == accepted_fingerprint
    assert [endpoint.name for endpoint in current.endpoints] == ["whoami"]
