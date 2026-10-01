from __future__ import annotations

import httpx
import pytest

from schemarouter import (
    EndpointSpec,
    RegistrationError,
    SchemaRouter,
    SchemaSourceError,
    ToolSpec,
)
from schemarouter.adapters.base import AdapterLoadResult


def _document(
    *,
    method: str = "get",
    required_query: bool = False,
    summary: str | None = None,
) -> dict:
    return {
        "openapi": "3.1.0",
        "info": {"title": "Refresh API", "version": "1.0.0"},
        "servers": [{"url": "https://example.test"}],
        "paths": {
            "/materials": {
                method: {
                    "operationId": "materials_search",
                    "summary": summary,
                    "parameters": (
                        [
                            {
                                "name": "q",
                                "in": "query",
                                "required": required_query,
                                "schema": {"type": "string"},
                            }
                        ]
                        if required_query
                        else []
                    ),
                    "responses": {
                        "200": {
                            "description": "ok",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "id": {"type": "string"},
                                        },
                                    }
                                }
                            },
                        }
                    },
                }
            }
        },
    }


@pytest.mark.asyncio
async def test_schema_refresh_identical_is_noop() -> None:
    state = {"document": _document()}

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=state["document"], request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        router = SchemaRouter(http_client=client)
        tool = await router.add_url(
            "https://example.test/openapi.json",
            kind="openapi",
            name="materials",
        )
        version = router.registry.version

        result = await router.arefresh_schema(tool.key)

        assert result.action == "unchanged"
        assert result.applied is False
        assert result.compatibility == "identical"
        assert router.registry.version == version
        assert router.registry.get(tool.key).fingerprint == tool.fingerprint


@pytest.mark.asyncio
async def test_schema_refresh_applies_proven_compatible_description_change() -> None:
    state = {"document": _document()}

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=state["document"], request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        router = SchemaRouter(http_client=client)
        tool = await router.add_url(
            "https://example.test/openapi.json",
            kind="openapi",
            name="materials",
        )
        old_fingerprint = tool.fingerprint

        state["document"] = _document(summary="Search materials")
        result = await router.arefresh_schema(tool.key)

        assert result.action == "applied"
        assert result.applied is True
        assert result.compatibility == "compatible"
        refreshed = router.registry.get(tool.key)
        assert refreshed.fingerprint != old_fingerprint
        assert refreshed.endpoint("materials_search").description == "Search materials"


@pytest.mark.asyncio
async def test_compatible_refresh_restamps_existing_health_probe() -> None:
    state = {"document": _document()}

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=state["document"], request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        router = SchemaRouter(http_client=client)
        tool = await router.add_url(
            "https://example.test/openapi.json",
            kind="openapi",
            name="materials",
        )
        calls = 0

        def probe() -> bool:
            nonlocal calls
            calls += 1
            return True

        router.register_health_probe(tool.key, "materials_search", probe)
        state["document"] = _document(summary="Search materials")

        result = await router.arefresh_schema(tool.key)
        snapshots = await router.check_health_once()

    assert result.action == "applied"
    assert snapshots[0].status == "healthy"
    assert snapshots[0].last_error_type is None
    assert calls == 1


@pytest.mark.asyncio
async def test_schema_refresh_quarantines_breaking_required_parameter() -> None:
    state = {"document": _document()}

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=state["document"], request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        router = SchemaRouter(http_client=client)
        tool = await router.add_url(
            "https://example.test/openapi.json",
            kind="openapi",
            name="materials",
        )
        old_fingerprint = tool.fingerprint

        state["document"] = _document(required_query=True)
        result = await router.arefresh_schema(tool.key)

        assert result.action == "pending_review"
        assert result.applied is False
        assert result.compatibility == "breaking"
        assert router.registry.get(tool.key).fingerprint == old_fingerprint


@pytest.mark.asyncio
async def test_schema_refresh_quarantines_security_semantic_change() -> None:
    state = {"document": _document(method="get")}

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=state["document"], request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        router = SchemaRouter(http_client=client)
        tool = await router.add_url(
            "https://example.test/openapi.json",
            kind="openapi",
            name="materials",
        )
        old_fingerprint = tool.fingerprint

        state["document"] = _document(method="post")
        result = await router.arefresh_schema(tool.key)

        assert result.action == "pending_review"
        assert result.applied is False
        assert result.compatibility == "security_review"
        assert router.registry.get(tool.key).fingerprint == old_fingerprint


@pytest.mark.asyncio
async def test_schema_refresh_can_report_compatible_without_applying() -> None:
    state = {"document": _document()}

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=state["document"], request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        router = SchemaRouter(http_client=client)
        tool = await router.add_url(
            "https://example.test/openapi.json",
            kind="openapi",
            name="materials",
        )
        old_fingerprint = tool.fingerprint

        state["document"] = _document(summary="Search materials")

        result = await router.arefresh_schema(
            tool.key,
            apply_compatible=False,
        )

        assert result.action == "report_only"
        assert result.applied is False
        assert result.compatibility == "compatible"
        assert router.registry.get(tool.key).fingerprint == old_fingerprint


def test_schema_refresh_sync_wrapper_is_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    router = SchemaRouter()
    tool = ToolSpec(
        name="remote",
        remote=True,
        metadata={
            "adapter": "openapi",
            "source_url": "https://example.test/openapi.json",
        },
        endpoints=[
            EndpointSpec(
                name="read",
                read_only=True,
                output_schema={"type": "object"},
            )
        ],
    )
    router.add_tool(tool)

    async def inspect(*args, **kwargs):
        del args, kwargs
        return AdapterLoadResult(tool=tool.model_copy(deep=True))

    monkeypatch.setattr(router.loader, "inspect", inspect)

    result = router.refresh_schema(tool.key)

    assert result.action == "unchanged"
    assert result.compatibility == "identical"


@pytest.mark.asyncio
async def test_schema_refresh_rejects_unknown_tool() -> None:
    router = SchemaRouter()

    with pytest.raises(RegistrationError, match="unknown tool"):
        await router.arefresh_schema("missing")


@pytest.mark.asyncio
async def test_schema_refresh_rejects_non_refreshable_local_tool() -> None:
    router = SchemaRouter()
    tool = ToolSpec(
        name="local",
        endpoints=[
            EndpointSpec(
                name="read",
                read_only=True,
                output_schema={"type": "object"},
            )
        ],
    )
    router.add_tool(tool)

    with pytest.raises(SchemaSourceError, match="refreshable structured-source"):
        await router.arefresh_schema(tool.key)


@pytest.mark.asyncio
async def test_schema_refresh_rejects_missing_source_provenance() -> None:
    router = SchemaRouter()
    tool = ToolSpec(
        name="remote",
        remote=True,
        execution_metadata={"adapter": "openapi"},
        endpoints=[
            EndpointSpec(
                name="read",
                read_only=True,
                output_schema={"type": "object"},
            )
        ],
    )
    router.add_tool(tool)

    with pytest.raises(SchemaSourceError, match="missing persisted source provenance"):
        await router.arefresh_schema(tool.key)


@pytest.mark.asyncio
async def test_schema_refresh_rejects_candidate_key_change(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = {"document": _document()}

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=state["document"], request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        router = SchemaRouter(http_client=client)
        tool = await router.add_url(
            "https://example.test/openapi.json",
            kind="openapi",
            name="materials",
        )

        candidate = ToolSpec(
            name="other",
            remote=True,
            metadata={"adapter": "openapi", "source_url": "https://example.test/openapi.json"},
            endpoints=[
                EndpointSpec(
                    name="read",
                    read_only=True,
                    output_schema={"type": "object"},
                )
            ],
        )

        async def inspect(*args, **kwargs):
            del args, kwargs
            return AdapterLoadResult(tool=candidate)

        monkeypatch.setattr(router.loader, "inspect", inspect)

        with pytest.raises(
            SchemaSourceError,
            match="changed the registered tool key unexpectedly",
        ):
            await router.arefresh_schema(tool.key)


def _graphql_introspection() -> dict:
    return {
        "data": {
            "__schema": {
                "queryType": {"name": "Query"},
                "mutationType": None,
                "subscriptionType": None,
                "types": [
                    {
                        "kind": "OBJECT",
                        "name": "Query",
                        "fields": [
                            {
                                "name": "ping",
                                "description": "Ping",
                                "isDeprecated": False,
                                "deprecationReason": None,
                                "args": [],
                                "type": {"kind": "SCALAR", "name": "String", "ofType": None},
                            }
                        ],
                        "inputFields": None,
                        "enumValues": None,
                        "possibleTypes": None,
                    },
                    {
                        "kind": "SCALAR",
                        "name": "String",
                        "fields": None,
                        "inputFields": None,
                        "enumValues": None,
                        "possibleTypes": None,
                    },
                ],
            }
        }
    }


@pytest.mark.asyncio
async def test_schema_refresh_graphql_identical_is_noop() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_graphql_introspection(), request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        router = SchemaRouter(http_client=client)
        tool = await router.add_url(
            "https://graphql.example/graphql",
            kind="graphql",
            name="graphql_fixture",
        )
        result = await router.arefresh_schema(tool.key)

    assert result.action == "unchanged"
    assert result.compatibility == "identical"


def _openrpc_document() -> dict:
    return {
        "openrpc": "1.4.0",
        "info": {"title": "Fixture RPC", "version": "1.0.0"},
        "servers": [{"url": "https://rpc.example/rpc"}],
        "methods": [
            {
                "name": "ping",
                "params": [],
                "result": {
                    "name": "result",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "ok": {"type": "boolean"},
                        },
                    },
                },
            }
        ],
    }


@pytest.mark.asyncio
async def test_schema_refresh_openrpc_preserves_approved_base_url() -> None:
    seen_gets = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal seen_gets
        if request.method == "GET":
            seen_gets += 1
            return httpx.Response(200, json=_openrpc_document(), request=request)
        raise AssertionError("refresh must not execute the RPC method")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        router = SchemaRouter(http_client=client)
        tool = await router.add_url(
            "https://rpc.example/openrpc.json",
            kind="openrpc",
            name="rpc_fixture",
            base_url="https://rpc.example/rpc",
        )
        result = await router.arefresh_schema(tool.key)

    assert result.action == "unchanged"
    assert result.compatibility == "identical"
    assert seen_gets == 2
