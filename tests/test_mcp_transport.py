import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest

import schemarouter.runtime as runtime_module
from schemarouter import (
    EndpointSpec,
    ExecutionPolicy,
    PlanRequest,
    SchemaRouter,
    ToolSpec,
)
from schemarouter.adapters.mcp import (
    MCPRemoteInvoker,
    MCPStdioConfig,
    inspect_mcp_client_factory,
    inspect_mcp_url,
)
from schemarouter.errors import SchemaSourceError


class RecordingFactory:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []
        self.client = SimpleNamespace(
            server_info=SimpleNamespace(name="secure-server"),
            protocol_version="2026-06-18",
        )

        async def list_tools(*, cursor=None):
            return SimpleNamespace(
                tools=[
                    {
                        "name": "whoami",
                        "description": "Return identity",
                        "inputSchema": {"type": "object", "properties": {}},
                        "outputSchema": {
                            "type": "object",
                            "properties": {"subject": {"type": "string"}},
                        },
                    }
                ],
                next_cursor=None,
            )

        async def call_tool(endpoint, arguments):
            assert endpoint == "whoami"
            return SimpleNamespace(
                is_error=False,
                structured_content={"subject": "alice"},
            )

        self.client.list_tools = list_tools
        self.client.call_tool = call_tool

    @asynccontextmanager
    async def __call__(self, url, *, headers=None, timeout=20.0):
        self.calls.append(
            {
                "url": url,
                "headers": dict(headers or {}),
                "timeout": timeout,
            }
        )
        yield self.client


@pytest.mark.asyncio
async def test_mcp_trusted_headers_stay_in_transport_boundary() -> None:
    factory = RecordingFactory()
    token = "Bearer top-secret"

    tool = await inspect_mcp_url(
        "https://mcp.example.com/mcp",
        trusted_headers={"Authorization": token, "X-Tenant": "acme"},
        client_factory=factory,
    )
    invoker = MCPRemoteInvoker(
        "https://mcp.example.com/mcp",
        trusted_headers={"Authorization": token, "X-Tenant": "acme"},
        client_factory=factory,
    )
    result = await invoker("whoami", {})

    assert result == {"subject": "alice"}
    assert factory.calls[0]["headers"] == {
        "Authorization": token,
        "X-Tenant": "acme",
    }
    assert factory.calls[1]["headers"] == {
        "Authorization": token,
        "X-Tenant": "acme",
    }
    assert tool.metadata["authenticated_transport"] is True
    assert token not in repr(tool.model_dump(mode="json"))


@pytest.mark.asyncio
async def test_mcp_protocol_headers_cannot_be_overridden_by_trusted_config() -> None:
    factory = RecordingFactory()

    with pytest.raises(ValueError, match="controlled by the SDK"):
        await inspect_mcp_url(
            "https://mcp.example.com/mcp",
            trusted_headers={"Mcp-Protocol-Version": "attacker"},
            client_factory=factory,
        )

    assert factory.calls == []


@pytest.mark.parametrize(
    "headers",
    [
        {"Host": "evil.example"},
        {"Content-Length": "123"},
        {"X-Test": "bad\r\nInjected: true"},
    ],
)
def test_mcp_invoker_rejects_unsafe_trusted_headers(headers: dict[str, str]) -> None:
    with pytest.raises(ValueError):
        MCPRemoteInvoker(
            "https://mcp.example.com/mcp",
            trusted_headers=headers,
            client_factory=RecordingFactory(),
        )


@pytest.mark.asyncio
async def test_mcp_rejects_credentials_embedded_in_url_before_factory_use() -> None:
    factory = RecordingFactory()

    with pytest.raises(ValueError, match="must not contain credentials"):
        await inspect_mcp_url(
            "https://user:password@mcp.example.com/mcp",
            client_factory=factory,
        )

    assert factory.calls == []


def test_mcp_invoker_rejects_credentials_embedded_in_url() -> None:
    with pytest.raises(ValueError, match="must not contain credentials"):
        MCPRemoteInvoker(
            "https://user:password@mcp.example.com/mcp",
            client_factory=RecordingFactory(),
        )



@pytest.mark.parametrize(
    "url",
    [
        "https://mcp.example.com/mcp?token=secret",
        "https://mcp.example.com/mcp#fragment",
    ],
)
@pytest.mark.asyncio
async def test_mcp_rejects_query_or_fragment_runtime_urls(url: str) -> None:
    factory = RecordingFactory()

    with pytest.raises(ValueError, match="query or fragment"):
        await inspect_mcp_url(
            url,
            client_factory=factory,
        )

    assert factory.calls == []


@pytest.mark.parametrize(
    "url",
    [
        "https://mcp.example.com/mcp?token=secret",
        "https://mcp.example.com/mcp#fragment",
    ],
)
def test_mcp_invoker_rejects_query_or_fragment_runtime_urls(url: str) -> None:
    with pytest.raises(ValueError, match="query or fragment"):
        MCPRemoteInvoker(
            url,
            client_factory=RecordingFactory(),
        )


def _mcp_tool(name: str, *, description: str = "") -> dict[str, object]:
    return {
        "name": name,
        "description": description,
        "inputSchema": {"type": "object", "properties": {}},
        "outputSchema": {
            "type": "object",
            "properties": {"value": {"type": "string"}},
        },
    }


class PaginatedBoundFactory:
    def __init__(
        self,
        pages: dict[
            str | None,
            tuple[list[dict[str, object]], str | None],
        ],
        *,
        delay_seconds: float = 0.0,
    ) -> None:
        self.pages = pages
        self.delay_seconds = delay_seconds
        self.calls: list[str | None] = []
        self.client = SimpleNamespace(
            server_info=SimpleNamespace(name="paginated-server"),
            protocol_version="2026-07-28",
        )

        async def list_tools(*, cursor=None):
            self.calls.append(cursor)
            if self.delay_seconds:
                await asyncio.sleep(self.delay_seconds)
            tools, next_cursor = self.pages[cursor]
            return SimpleNamespace(
                tools=tools,
                next_cursor=next_cursor,
            )

        self.client.list_tools = list_tools

    @asynccontextmanager
    async def __call__(self, *, timeout=20.0):
        del timeout
        yield self.client


@pytest.mark.asyncio
async def test_mcp_discovery_accepts_finite_pagination_within_budgets() -> None:
    factory = PaginatedBoundFactory(
        {
            None: ([_mcp_tool("first")], "page-2"),
            "page-2": ([_mcp_tool("second")], None),
        }
    )

    tool = await inspect_mcp_client_factory(
        factory,
        max_pages=2,
        max_tools=2,
        max_tool_bytes=2048,
        max_total_bytes=4096,
    )

    assert factory.calls == [None, "page-2"]
    assert [endpoint.name for endpoint in tool.endpoints] == ["first", "second"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("pages", "expected_calls"),
    [
        (
            {
                None: ([], "same"),
                "same": ([], "same"),
            },
            [None, "same"],
        ),
        (
            {
                None: ([], "a"),
                "a": ([], "b"),
                "b": ([], "a"),
            },
            [None, "a", "b"],
        ),
    ],
)
async def test_mcp_discovery_rejects_repeated_or_cyclic_cursors(
    pages: dict[
        str | None,
        tuple[list[dict[str, object]], str | None],
    ],
    expected_calls: list[str | None],
) -> None:
    factory = PaginatedBoundFactory(pages)

    with pytest.raises(SchemaSourceError, match="repeated pagination cursor"):
        await inspect_mcp_client_factory(factory)

    assert factory.calls == expected_calls


@pytest.mark.asyncio
async def test_mcp_discovery_stops_before_requesting_past_page_budget() -> None:
    factory = PaginatedBoundFactory(
        {
            None: ([], "a"),
            "a": ([], "b"),
            "b": ([], None),
        }
    )

    with pytest.raises(SchemaSourceError, match="max_pages=2"):
        await inspect_mcp_client_factory(factory, max_pages=2)

    assert factory.calls == [None, "a"]


@pytest.mark.asyncio
async def test_mcp_discovery_tool_budget_fails_before_router_registration() -> None:
    factory = PaginatedBoundFactory(
        {
            None: (
                [
                    _mcp_tool("first"),
                    _mcp_tool("second"),
                    _mcp_tool("third"),
                ],
                None,
            )
        }
    )
    router = SchemaRouter()

    with pytest.raises(SchemaSourceError, match="max_tools=2"):
        await router.add_mcp_client_factory(
            factory,
            name="bounded-mcp",
            max_tools=2,
        )

    assert router.registry.keys() == ()
    assert router.executor.bound_keys() == ()


@pytest.mark.asyncio
async def test_mcp_discovery_rejects_oversized_individual_tool_document() -> None:
    factory = PaginatedBoundFactory(
        {
            None: (
                [_mcp_tool("large", description="x" * 2048)],
                None,
            )
        }
    )

    with pytest.raises(SchemaSourceError, match="oversized tool document"):
        await inspect_mcp_client_factory(
            factory,
            max_tool_bytes=512,
        )


@pytest.mark.asyncio
async def test_mcp_discovery_rejects_aggregate_tool_document_budget() -> None:
    factory = PaginatedBoundFactory(
        {
            None: (
                [
                    _mcp_tool("first", description="x" * 256),
                    _mcp_tool("second", description="y" * 256),
                ],
                None,
            )
        }
    )

    with pytest.raises(SchemaSourceError, match="aggregate tool-document budget"):
        await inspect_mcp_client_factory(
            factory,
            max_tool_bytes=2048,
            max_total_bytes=600,
        )


@pytest.mark.asyncio
async def test_mcp_discovery_enforces_total_wall_clock_timeout() -> None:
    factory = PaginatedBoundFactory(
        {
            None: ([_mcp_tool("slow")], None),
        },
        delay_seconds=0.1,
    )

    with pytest.raises(SchemaSourceError, match="configured total timeout"):
        await inspect_mcp_client_factory(
            factory,
            timeout=0.01,
        )


@pytest.mark.parametrize(
    ("keyword", "value"),
    [
        ("max_pages", 0),
        ("max_tools", -1),
        ("max_tool_bytes", True),
        ("max_total_bytes", 0),
    ],
)
@pytest.mark.asyncio
async def test_mcp_discovery_rejects_invalid_budget_configuration(
    keyword: str,
    value: object,
) -> None:
    factory = PaginatedBoundFactory(
        {
            None: ([_mcp_tool("unused")], None),
        }
    )

    with pytest.raises(ValueError, match="positive integer"):
        await inspect_mcp_client_factory(
            factory,
            **{keyword: value},
        )


class BoundRecordingFactory:
    def __init__(self) -> None:
        self.calls: list[float] = []
        self.client = SimpleNamespace(
            server_info=SimpleNamespace(name="bound-server"),
            protocol_version="2026-07-28",
        )

        async def list_tools(*, cursor=None):
            return SimpleNamespace(
                tools=[
                    {
                        "name": "whoami",
                        "description": "Return identity",
                        "inputSchema": {"type": "object", "properties": {}},
                        "outputSchema": {
                            "type": "object",
                            "properties": {"subject": {"type": "string"}},
                        },
                    }
                ],
                next_cursor=None,
            )

        async def call_tool(endpoint, arguments):
            assert endpoint == "whoami"
            assert arguments == {}
            return SimpleNamespace(
                is_error=False,
                structured_content={"subject": "bound"},
            )

        self.client.list_tools = list_tools
        self.client.call_tool = call_tool

    @asynccontextmanager
    async def __call__(self, *, timeout=20.0):
        self.calls.append(timeout)
        yield self.client


@pytest.mark.asyncio
async def test_transport_neutral_mcp_factory_needs_no_fake_url() -> None:
    factory = BoundRecordingFactory()
    router = SchemaRouter(
        policy=ExecutionPolicy(allow_unclassified_remote=True)
    )

    tool = await router.add_mcp_client_factory(
        factory,
        name="bound-mcp",
        provider="fixture",
        transport="inprocess",
        transport_fingerprint="fixture-inprocess-v1",
    )

    assert tool.remote is True
    assert tool.access_mode == "mcp_inprocess"
    assert tool.metadata["transport"] == "inprocess"
    assert tool.metadata["transport_fingerprint"] == "fixture-inprocess-v1"

    results = await router.ainvoke(
        PlanRequest(
            query="whoami subject",
            preferred_tools=[tool.key],
        )
    )
    assert results[0].data == {"subject": "bound"}
    assert len(factory.calls) == 2


@pytest.mark.asyncio
async def test_mcp_factory_bind_failure_rolls_back_registration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    router = SchemaRouter(
        policy=ExecutionPolicy(allow_unclassified_remote=True)
    )
    factory = BoundRecordingFactory()

    def fail_bind(*args, **kwargs) -> None:
        raise RuntimeError("injected MCP bind failure")

    monkeypatch.setattr(router.executor, "bind", fail_bind)

    with pytest.raises(RuntimeError, match="injected MCP bind failure"):
        await router.add_mcp_client_factory(
            factory,
            name="bound-mcp",
            transport="inprocess",
        )

    assert router.registry.keys() == ()
    assert router.executor.bound_keys() == ()


@pytest.mark.asyncio
async def test_mcp_stdio_bind_failure_rolls_back_registration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    router = SchemaRouter(
        policy=ExecutionPolicy(allow_unclassified_remote=True)
    )
    tool = ToolSpec(
        name="stdio_atomic",
        remote=True,
        execution_metadata={"adapter": "mcp"},
        endpoints=[EndpointSpec(name="whoami", read_only=True)],
    )

    async def fake_inspect(*args, **kwargs) -> ToolSpec:
        del args, kwargs
        return tool.model_copy(deep=True)

    def fail_bind(*args, **kwargs) -> None:
        raise RuntimeError("injected stdio bind failure")

    monkeypatch.setattr(runtime_module, "inspect_mcp_stdio", fake_inspect)
    monkeypatch.setattr(router.executor, "bind", fail_bind)

    with pytest.raises(RuntimeError, match="injected stdio bind failure"):
        await router.add_mcp_stdio(
            "python",
            allowed_commands=("python",),
            name="stdio_atomic",
        )

    assert router.registry.keys() == ()
    assert router.executor.bound_keys() == ()


def test_mcp_stdio_config_enforces_command_allowlist_and_hides_env_values_from_identity() -> None:
    with pytest.raises(ValueError, match="not in the trusted allowlist"):
        MCPStdioConfig(
            command="python",
            allowed_commands=("uv",),
        )

    first = MCPStdioConfig(
        command="python",
        args=("server.py",),
        env={"TOKEN": "first-secret"},
        allowed_commands=("python",),
    )
    second = MCPStdioConfig(
        command="python",
        args=("server.py",),
        env={"TOKEN": "rotated-secret"},
        allowed_commands=("python",),
    )

    assert first.transport_fingerprint == second.transport_fingerprint
    assert "first-secret" not in first.transport_fingerprint
    assert "rotated-secret" not in second.transport_fingerprint


@pytest.mark.parametrize(
    "value",
    [
        "bad\ncommand",
        "bad\rcommand",
        "bad\x00command",
    ],
)
def test_mcp_stdio_config_rejects_control_characters(value: str) -> None:
    with pytest.raises(ValueError):
        MCPStdioConfig(command=value)
