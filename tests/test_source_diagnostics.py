from __future__ import annotations

from contextlib import asynccontextmanager

import httpx
import pytest

from schemarouter import SchemaRouter, SchemaSourceError


def _openapi_document() -> dict:
    return {
        "openapi": "3.1.0",
        "info": {"title": "Diagnostics", "version": "1.0.0"},
        "paths": {
            "/items": {
                "get": {
                    "operationId": "list_items",
                    "responses": {"200": {"description": "ok"}},
                }
            }
        },
    }


@pytest.mark.asyncio
async def test_diagnose_ordinary_html_is_not_recognized_and_lists_skips() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            text="<html><body>ordinary documentation</body></html>",
            headers={"content-type": "text/html"},
            request=request,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        router = SchemaRouter(http_client=client)
        version = router.registry.version
        report = await router.diagnose_url("https://docs.example.test/reference")

    assert report.status == "not_recognized"
    assert report.recognized_kind is None
    assert router.registry.version == version
    assert router.registry.keys() == ()
    assert router.executor.bound_keys() == ()

    by_kind = {item.adapter_kind: item for item in report.diagnostics}
    for kind in ("openapi", "openrpc", "optimade", "odata"):
        assert by_kind[kind].attempted is True
        assert by_kind[kind].status == "not_recognized"
        assert by_kind[kind].discovery_activity == "passive"

    for kind in ("mcp", "graphql"):
        assert by_kind[kind].attempted is False
        assert by_kind[kind].status == "skipped"
        assert by_kind[kind].discovery_activity == "active"


@pytest.mark.asyncio
async def test_diagnose_unsupported_structured_json_is_not_recognized() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"kind": "unknown-structured-document"},
            request=request,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        report = await SchemaRouter(http_client=client).diagnose_url(
            "https://example.test/schema.json"
        )

    assert report.status == "not_recognized"
    assert all(
        item.status in {"not_recognized", "skipped"}
        for item in report.diagnostics
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("status_code", [401, 403])
async def test_diagnose_openapi_authentication_failure(status_code: int) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        router = SchemaRouter(http_client=client)
        report = await router.diagnose_url(
            "https://example.test/openapi.json",
            kind="openapi",
            schema_headers={"Authorization": "Bearer private-schema-token"},
        )

    assert report.status == "failed"
    assert report.diagnostics[0].failure_category == "authentication_failed"
    serialized = report.model_dump_json()
    assert "private-schema-token" not in serialized
    assert "Authorization" not in serialized


@pytest.mark.asyncio
async def test_diagnose_openapi_not_found() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        report = await SchemaRouter(http_client=client).diagnose_url(
            "https://example.test/missing.json",
            kind="openapi",
        )

    assert report.status == "failed"
    assert report.diagnostics[0].failure_category == "not_found"


@pytest.mark.asyncio
async def test_diagnose_transport_failure_is_sanitized_unreachable() -> None:
    source = "https://example.test/openapi.json?token=private-query-value"

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout(
            "private transport detail",
            request=request,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        report = await SchemaRouter(http_client=client).diagnose_url(
            source,
            kind="openapi",
        )

    assert report.status == "failed"
    assert report.diagnostics[0].failure_category == "unreachable"
    assert report.source_url == "https://example.test/openapi.json"
    serialized = report.model_dump_json()
    assert "private-query-value" not in serialized
    assert "private transport detail" not in serialized


@pytest.mark.asyncio
async def test_diagnose_malformed_openapi_is_invalid_schema() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "openapi": "3.1.0",
                "info": {"title": "Broken", "version": "1.0.0"},
                "paths": [],
            },
            request=request,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        report = await SchemaRouter(http_client=client).diagnose_url(
            "https://example.test/openapi.json",
            kind="openapi",
        )

    assert report.status == "failed"
    assert report.diagnostics[0].failure_category == "invalid_schema"


@pytest.mark.asyncio
async def test_diagnose_graphql_introspection_disabled() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        return httpx.Response(
            200,
            json={"errors": [{"message": "private remote GraphQL payload"}]},
            request=request,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        report = await SchemaRouter(http_client=client).diagnose_url(
            "https://example.test/graphql",
            kind="graphql",
        )

    assert report.status == "failed"
    assert report.diagnostics[0].failure_category == "unsupported_feature"
    assert "private remote GraphQL payload" not in report.model_dump_json()


@pytest.mark.asyncio
async def test_diagnose_non_mcp_transport_failure_is_not_generic_nonmatch() -> None:
    def failing_factory(
        url: str,
        *,
        headers=None,
        timeout: float = 20.0,
    ):
        del url, headers, timeout

        @asynccontextmanager
        async def context():
            raise RuntimeError("private non-MCP response detail")
            yield None  # pragma: no cover

        return context()

    report = await SchemaRouter().diagnose_url(
        "https://example.test/not-mcp",
        kind="mcp",
        mcp_client_factory=failing_factory,
    )

    assert report.status == "failed"
    assert report.diagnostics[0].failure_category in {
        "invalid_schema",
        "protocol_error",
    }
    assert "private non-MCP response detail" not in report.model_dump_json()


@pytest.mark.asyncio
async def test_explicit_probe_preserves_sanitized_failure_category() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        router = SchemaRouter(http_client=client)
        with pytest.raises(
            SchemaSourceError,
            match="authentication_failed",
        ) as exc_info:
            await router.probe_url(
                "https://example.test/openapi.json?token=private-value",
                kind="openapi",
                schema_headers={"Authorization": "Bearer private-header"},
            )

    message = str(exc_info.value)
    assert "private-value" not in message
    assert "private-header" not in message


@pytest.mark.asyncio
async def test_diagnose_explicit_wrong_kind_is_actionable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return httpx.Response(405, request=request)
        return httpx.Response(200, json=_openapi_document(), request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        report = await SchemaRouter(http_client=client).diagnose_url(
            "https://example.test/openapi.json",
            kind="graphql",
        )

    assert report.status == "failed"
    assert report.diagnostics[0].adapter_kind == "graphql"
    assert report.diagnostics[0].failure_category == "protocol_error"
