from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest

from schemarouter.adapters.mcp import MCPRemoteInvoker, inspect_mcp_url


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
