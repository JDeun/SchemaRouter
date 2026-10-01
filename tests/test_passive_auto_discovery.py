from __future__ import annotations

from contextlib import asynccontextmanager

import httpx
import pytest

from schemarouter import (
    AdapterLoadResult,
    AdapterRegistry,
    DiscoveryProfile,
    EndpointSpec,
    SchemaRouter,
    ToolSpec,
    UnsupportedSchemaSourceError,
)
from schemarouter.cli import build_parser
from schemarouter.ingestion import default_adapter_registry


class _RecordingMCPFactory:
    def __init__(self) -> None:
        self.calls = 0

    def __call__(
        self,
        url: str,
        *,
        headers=None,
        timeout: float = 20.0,
    ):
        del url, headers, timeout

        @asynccontextmanager
        async def context():
            self.calls += 1
            raise RuntimeError("synthetic MCP handshake failure")
            yield None  # pragma: no cover

        return context()


@pytest.mark.asyncio
async def test_default_auto_discovery_emits_only_passive_http_traffic() -> None:
    requests: list[tuple[str, str]] = []
    mcp_factory = _RecordingMCPFactory()

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append((request.method, str(request.url)))
        return httpx.Response(
            200,
            text="<html><body>ordinary website</body></html>",
            headers={"content-type": "text/html"},
            request=request,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        router = SchemaRouter(http_client=client)
        with pytest.raises(UnsupportedSchemaSourceError) as exc_info:
            await router.probe_url(
                "https://example.test/",
                kind="auto",
                mcp_client_factory=mcp_factory,
            )

    assert requests
    assert {method for method, _ in requests} <= {"GET", "HEAD"}
    assert mcp_factory.calls == 0
    message = str(exc_info.value)
    assert "Active protocol probes were skipped by default" in message
    assert "mcp" in message
    assert "graphql" in message
    assert "allow_active_probes=True" in message


@pytest.mark.asyncio
async def test_explicit_graphql_kind_allows_active_post_probe() -> None:
    methods: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        methods.append(request.method)
        return httpx.Response(
            200,
            json={"data": {}},
            request=request,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        router = SchemaRouter(http_client=client)
        with pytest.raises(UnsupportedSchemaSourceError):
            await router.probe_url(
                "https://example.test/graphql",
                kind="graphql",
            )

    assert methods == ["POST"]


@pytest.mark.asyncio
async def test_active_auto_discovery_requires_explicit_opt_in() -> None:
    methods: list[str] = []
    mcp_factory = _RecordingMCPFactory()

    def handler(request: httpx.Request) -> httpx.Response:
        methods.append(request.method)
        if request.method == "POST":
            return httpx.Response(200, json={"data": {}}, request=request)
        return httpx.Response(
            200,
            text="<html><body>ordinary website</body></html>",
            headers={"content-type": "text/html"},
            request=request,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        router = SchemaRouter(http_client=client)
        with pytest.raises(UnsupportedSchemaSourceError):
            await router.probe_url(
                "https://example.test/",
                kind="auto",
                allow_active_probes=True,
                mcp_client_factory=mcp_factory,
            )

    assert mcp_factory.calls == 1
    assert "POST" in methods


@pytest.mark.asyncio
async def test_unprofiled_third_party_adapter_is_not_auto_probed() -> None:
    class LegacyAdapter:
        kind = "legacy"
        priority = 999

        def __init__(self) -> None:
            self.calls = 0

        async def load(self, context):
            del context
            self.calls += 1
            return None

    adapter = LegacyAdapter()
    router = SchemaRouter(adapter_registry=AdapterRegistry([adapter]))

    with pytest.raises(UnsupportedSchemaSourceError) as auto_error:
        await router.probe_url("https://example.test/schema", kind="auto")

    assert adapter.calls == 0
    assert "legacy" in str(auto_error.value)

    with pytest.raises(UnsupportedSchemaSourceError):
        await router.probe_url("https://example.test/schema", kind="legacy")

    assert adapter.calls == 1


@pytest.mark.asyncio
async def test_from_url_propagates_active_probe_opt_in() -> None:
    class ActiveAdapter:
        kind = "active_demo"
        priority = 100
        discovery = DiscoveryProfile(
            activity="active",
            http_methods=("POST",),
        )

        def __init__(self) -> None:
            self.calls = 0

        async def load(self, context):
            del context
            self.calls += 1
            return AdapterLoadResult(
                tool=ToolSpec(
                    name="active_demo",
                    endpoints=[
                        EndpointSpec(
                            name="read",
                            read_only=True,
                        )
                    ],
                )
            )

    adapter = ActiveAdapter()
    registry = AdapterRegistry([adapter])

    router = await SchemaRouter.from_url(
        "https://example.test/capability",
        adapter_registry=registry,
        allow_active_probes=True,
    )

    assert adapter.calls == 1
    assert router.registry.keys() == ("active_demo",)


def test_source_probe_cli_exposes_active_probe_opt_in() -> None:
    args = build_parser().parse_args(
        [
            "source",
            "probe",
            "https://example.test/schema",
            "--allow-active-probes",
        ]
    )

    assert args.allow_active_probes is True


def test_default_adapter_profiles_classify_active_protocols() -> None:
    registry = default_adapter_registry()

    assert registry.discovery_profile("graphql").activity == "active"
    assert registry.discovery_profile("graphql").http_methods == ("POST",)
    assert registry.discovery_profile("mcp").activity == "active"
    assert registry.discovery_profile("mcp").opens_protocol_session is True

    for kind in ("openapi", "openrpc", "optimade", "odata"):
        profile = registry.discovery_profile(kind)
        assert profile.activity == "passive"
        assert set(profile.http_methods) <= {"GET", "HEAD"}


def test_passive_profile_rejects_active_side_effect_declarations() -> None:
    with pytest.raises(ValueError, match="GET/HEAD"):
        DiscoveryProfile(activity="passive", http_methods=("POST",))

    with pytest.raises(ValueError, match="protocol session"):
        DiscoveryProfile(activity="passive", opens_protocol_session=True)
