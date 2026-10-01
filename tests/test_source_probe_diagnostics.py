from __future__ import annotations

import json
from contextlib import asynccontextmanager

import httpx
import pytest

from schemarouter import (
    AdapterProbeError,
    SchemaRouter,
    SourceProbeDiagnostic,
    UnsupportedSchemaSourceError,
)
from schemarouter.cli import main


def _json_response(
    request: httpx.Request,
    payload: object,
    *,
    status_code: int = 200,
) -> httpx.Response:
    return httpx.Response(
        status_code,
        json=payload,
        headers={"content-type": "application/json"},
        request=request,
    )


@pytest.mark.asyncio
async def test_auto_html_is_not_recognized_and_active_probes_are_skipped() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            text="<html><body>ordinary site</body></html>",
            headers={"content-type": "text/html"},
            request=request,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        router = SchemaRouter(http_client=client)
        with pytest.raises(UnsupportedSchemaSourceError) as exc_info:
            await router.probe_url("https://example.test/docs")

    diagnostics = list(exc_info.value.diagnostics)
    assert diagnostics
    assert any(
        diagnostic.adapter_kind == "graphql"
        and diagnostic.status == "skipped_active"
        for diagnostic in diagnostics
    )
    assert any(
        diagnostic.adapter_kind == "mcp"
        and diagnostic.status == "skipped_active"
        for diagnostic in diagnostics
    )
    passive = [
        diagnostic
        for diagnostic in diagnostics
        if diagnostic.activity == "passive"
    ]
    assert passive
    assert all(
        diagnostic.status == "not_recognized"
        for diagnostic in passive
    )


@pytest.mark.asyncio
async def test_auto_unknown_structured_json_remains_not_recognized() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _json_response(request, {"hello": "world"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        router = SchemaRouter(http_client=client)
        with pytest.raises(UnsupportedSchemaSourceError) as exc_info:
            await router.probe_url("https://example.test/schema")

    diagnostics = list(exc_info.value.diagnostics)
    assert diagnostics
    assert not any(
        diagnostic.status in {
            "authentication_failed",
            "invalid_schema",
            "protocol_error",
        }
        for diagnostic in diagnostics
        if diagnostic.activity == "passive"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("status_code", [401, 403])
async def test_explicit_openapi_auth_failure_is_classified_without_body(
    status_code: int,
) -> None:
    private_body = "remote-private-body-marker"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code,
            text=private_body,
            request=request,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        router = SchemaRouter(http_client=client)
        with pytest.raises(AdapterProbeError) as exc_info:
            await router.probe_url(
                "https://example.test/openapi.json",
                kind="openapi",
            )

    error = exc_info.value
    assert error.category == "authentication_failed"
    assert error.status_code == status_code
    assert private_body not in str(error)


@pytest.mark.asyncio
async def test_explicit_openapi_404_is_classified() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        router = SchemaRouter(http_client=client)
        with pytest.raises(AdapterProbeError) as exc_info:
            await router.probe_url(
                "https://example.test/missing.json",
                kind="openapi",
            )

    assert exc_info.value.category == "unreachable"
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_explicit_openapi_timeout_is_unreachable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("fixture timeout", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        router = SchemaRouter(http_client=client)
        with pytest.raises(AdapterProbeError) as exc_info:
            await router.probe_url(
                "https://example.test/openapi.json",
                kind="openapi",
            )

    assert exc_info.value.category == "unreachable"
    assert exc_info.value.status_code is None
    assert "fixture timeout" not in str(exc_info.value)


@pytest.mark.asyncio
async def test_malformed_declared_openapi_is_invalid_schema() -> None:
    malformed = {
        "openapi": "3.1.0",
        "info": {"title": "Broken", "version": "1.0.0"},
        "paths": [],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return _json_response(request, malformed)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        router = SchemaRouter(http_client=client)
        with pytest.raises(AdapterProbeError) as exc_info:
            await router.probe_url(
                "https://example.test/openapi.json",
                kind="openapi",
            )

    assert exc_info.value.category == "invalid_schema"


@pytest.mark.asyncio
async def test_graphql_introspection_disabled_is_unsupported_feature() -> None:
    remote_message = "private remote introspection message"

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        return _json_response(
            request,
            {"errors": [{"message": remote_message}]},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        router = SchemaRouter(http_client=client)
        with pytest.raises(AdapterProbeError) as exc_info:
            await router.probe_url(
                "https://example.test/graphql",
                kind="graphql",
            )

    assert exc_info.value.category == "unsupported_feature"
    assert remote_message not in str(exc_info.value)


@pytest.mark.asyncio
async def test_non_mcp_endpoint_preserves_protocol_error_without_remote_payload() -> None:
    remote_marker = "private-mcp-payload-marker"

    @asynccontextmanager
    async def failing_factory(
        url: str,
        *,
        headers=None,
        timeout: float = 20.0,
    ):
        del url, headers, timeout
        raise RuntimeError(remote_marker)
        yield None  # pragma: no cover

    router = SchemaRouter()
    with pytest.raises(AdapterProbeError) as exc_info:
        await router.probe_url(
            "https://example.test/not-mcp",
            kind="mcp",
            mcp_client_factory=failing_factory,
        )

    assert exc_info.value.category == "protocol_error"
    assert remote_marker not in str(exc_info.value)


@pytest.mark.asyncio
async def test_explicit_wrong_kind_is_not_recognized_with_diagnostic() -> None:
    openapi = {
        "openapi": "3.1.0",
        "info": {"title": "API", "version": "1.0.0"},
        "paths": {},
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return _json_response(request, openapi)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        router = SchemaRouter(http_client=client)
        with pytest.raises(UnsupportedSchemaSourceError) as exc_info:
            await router.probe_url(
                "https://example.test/openapi.json",
                kind="openrpc",
            )

    diagnostics = list(exc_info.value.diagnostics)
    assert len(diagnostics) == 1
    assert diagnostics[0].adapter_kind == "openrpc"
    assert diagnostics[0].status == "not_recognized"


@pytest.mark.asyncio
async def test_probe_diagnostics_do_not_copy_query_or_header_values() -> None:
    private_query = "private-query-marker"
    private_header = "private-header-marker"
    source = f"https://example.test/openapi.json?marker={private_query}"

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["X-Test-Header"] == private_header
        return httpx.Response(401, text="private-response-marker", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        router = SchemaRouter(http_client=client)
        with pytest.raises(AdapterProbeError) as exc_info:
            await router.probe_url(
                source,
                kind="openapi",
                schema_headers={"X-Test-Header": private_header},
            )

    rendered = str(exc_info.value)
    assert private_query not in rendered
    assert private_header not in rendered
    assert "private-response-marker" not in rendered


def test_source_probe_cli_json_renders_sanitized_failure(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    async def fake_probe(self, url: str, **kwargs):
        del self, url, kwargs
        raise AdapterProbeError(
            "openapi",
            "authentication_failed",
            "OpenAPI schema fetch was refused with HTTP 401",
            status_code=401,
        )

    monkeypatch.setattr(SchemaRouter, "probe_url", fake_probe)

    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "source",
                "probe",
                "https://example.test/openapi.json",
                "--kind",
                "openapi",
                "--json",
            ]
        )

    assert exc_info.value.code == 2
    payload = json.loads(capsys.readouterr().err)
    assert payload["error"] == "source_probe_failed"
    diagnostic = payload["diagnostics"][0]
    assert diagnostic["adapter_kind"] == "openapi"
    assert diagnostic["status"] == "authentication_failed"
    assert diagnostic["status_code"] == 401


def test_source_probe_cli_json_renders_aggregate_diagnostics(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    diagnostics = (
        SourceProbeDiagnostic(
            adapter_kind="openapi",
            activity="passive",
            status="not_recognized",
        ),
        SourceProbeDiagnostic(
            adapter_kind="graphql",
            activity="active",
            status="skipped_active",
        ),
    )

    async def fake_probe(self, url: str, **kwargs):
        del self, url, kwargs
        raise UnsupportedSchemaSourceError(
            "source was not recognized",
            diagnostics=diagnostics,
        )

    monkeypatch.setattr(SchemaRouter, "probe_url", fake_probe)

    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "source",
                "probe",
                "https://example.test/docs",
                "--json",
            ]
        )

    assert exc_info.value.code == 2
    payload = json.loads(capsys.readouterr().err)
    assert payload["error"] == "unsupported_source"
    assert payload["diagnostics"][0]["status"] == "not_recognized"
    assert payload["diagnostics"][1]["status"] == "skipped_active"
