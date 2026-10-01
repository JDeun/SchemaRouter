from __future__ import annotations

import json

import httpx
import pytest

from schemarouter import (
    SchemaRouter,
    SchemaSourceError,
    SourceProbeResult,
    UnsupportedSchemaSourceError,
)
from schemarouter.cli import main


def _openapi_document(*, server_url: str = "/api") -> dict:
    return {
        "openapi": "3.1.0",
        "info": {"title": "Probe API", "version": "1.0.0"},
        "servers": [{"url": server_url}],
        "paths": {
            "/items": {
                "get": {
                    "operationId": "list_items",
                    "responses": {
                        "200": {
                            "description": "ok",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "items": {
                                                "type": "array",
                                                "items": {"type": "string"},
                                            }
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
async def test_probe_url_detects_openapi_without_registry_mutation() -> None:
    source = "https://docs.example.test/openapi.json?marker=private-value"

    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == source
        return httpx.Response(
            200,
            content=json.dumps(_openapi_document()),
            headers={"content-type": "application/json"},
            request=request,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        router = SchemaRouter(http_client=client)
        version = router.registry.version

        probe = await router.probe_url(source)

        assert router.registry.version == version
        assert router.registry.keys() == ()
        assert router.executor.bound_keys() == ()

    assert probe.adapter_kind == "openapi"
    assert probe.tool_key == "probe_api"
    assert probe.endpoint_count == 1
    assert probe.execution_bindable is True
    assert probe.warnings == []
    assert any(
        diagnostic.adapter_kind == "openapi"
        and diagnostic.status == "recognized"
        for diagnostic in probe.diagnostics
    )
    assert any(
        diagnostic.adapter_kind == "graphql"
        and diagnostic.status == "skipped_active"
        for diagnostic in probe.diagnostics
    )
    assert probe.source_url == "https://docs.example.test/openapi.json"
    assert "private-value" not in probe.model_dump_json()


@pytest.mark.asyncio
async def test_probe_url_reports_non_bindable_cross_origin_openapi() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=json.dumps(
                _openapi_document(server_url="https://api.example.test/v1")
            ),
            headers={"content-type": "application/json"},
            request=request,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        router = SchemaRouter(http_client=client)
        probe = await router.probe_url(
            "https://docs.example.test/openapi.json",
            kind="openapi",
        )

    assert probe.execution_bindable is False
    assert any("explicit trusted base_url" in warning for warning in probe.warnings)
    assert any("did not produce" in warning for warning in probe.warnings)


@pytest.mark.asyncio
async def test_probe_url_rejects_html_and_redacts_adapter_diagnostics() -> None:
    source = "https://docs.example.test/reference?marker=private-value"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            text="<html><body>human docs</body></html>",
            headers={"content-type": "text/html"},
            request=request,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        router = SchemaRouter(http_client=client)
        with pytest.raises(UnsupportedSchemaSourceError) as exc_info:
            await router.probe_url(source, kind="auto")

    message = str(exc_info.value)
    assert "not recognized" in message
    assert "private-value" not in message
    assert "marker=" not in message


@pytest.mark.asyncio
async def test_probe_url_rejects_html_under_explicit_openapi_kind() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            text="<html><body>human docs</body></html>",
            headers={"content-type": "text/html"},
            request=request,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        router = SchemaRouter(http_client=client)
        with pytest.raises(
            UnsupportedSchemaSourceError,
            match="supported openapi source",
        ):
            await router.probe_url(
                "https://docs.example.test/reference",
                kind="openapi",
            )


@pytest.mark.asyncio
async def test_probe_url_rejects_relative_url_before_adapter_io() -> None:
    router = SchemaRouter()

    with pytest.raises(SchemaSourceError, match="absolute http"):
        await router.probe_url("/relative/schema.json")


def test_source_probe_cli_renders_success_without_mutation(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    async def fake_probe(self, url: str, **kwargs) -> SourceProbeResult:
        del self, kwargs
        return SourceProbeResult(
            source_url=url,
            adapter_kind="openapi",
            tool_key="demo",
            tool_name="Demo",
            provider="provider",
            access_mode="openapi",
            endpoint_count=2,
            execution_bindable=True,
            warnings=[],
        )

    monkeypatch.setattr(SchemaRouter, "probe_url", fake_probe)

    assert main(["source", "probe", "https://example.test/openapi.json"]) == 0
    output = capsys.readouterr().out

    assert "Structured source: https://example.test/openapi.json" in output
    assert "adapter: openapi" in output
    assert "endpoints: 2" in output
    assert "execution binding: available" in output


def test_source_probe_cli_explains_unsupported_html(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    async def fake_probe(self, url: str, **kwargs) -> SourceProbeResult:
        del self, url, kwargs
        raise UnsupportedSchemaSourceError("no registered adapter recognized the source")

    monkeypatch.setattr(SchemaRouter, "probe_url", fake_probe)

    with pytest.raises(SystemExit) as exc_info:
        main(["source", "probe", "https://example.test/docs"])

    assert exc_info.value.code == 2
    error = capsys.readouterr().err
    assert "not a supported structured source" in error
    assert "normal HTML website is not auto-converted" in error
    assert "SchemaRouter.inspect_url()" in error
    assert "SchemaRouter.add_http_tool()" in error
    assert "supported source kinds:" in error
