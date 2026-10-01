from __future__ import annotations

import json

import httpx
import pytest

from schemarouter import (
    SchemaRouter,
    SchemaSourceError,
    SourceProbeDiagnostic,
    SourceProbeReport,
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
    async def fake_diagnose(self, url: str, **kwargs) -> SourceProbeReport:
        del self, kwargs
        return SourceProbeReport(
            source_url=url,
            requested_kind="auto",
            status="recognized",
            recognized_kind="openapi",
            tool_key="demo",
            tool_name="Demo",
            provider="provider",
            access_mode="openapi",
            endpoint_count=2,
            execution_bindable=True,
            warnings=[],
            diagnostics=[
                SourceProbeDiagnostic(
                    adapter_kind="openapi",
                    discovery_activity="passive",
                    http_methods=["GET"],
                    attempted=True,
                    status="recognized",
                )
            ],
        )

    monkeypatch.setattr(SchemaRouter, "diagnose_url", fake_diagnose)

    assert main(["source", "probe", "https://example.test/openapi.json"]) == 0
    output = capsys.readouterr().out

    assert "Structured source: https://example.test/openapi.json" in output
    assert "status: recognized" in output
    assert "recognized kind: openapi" in output
    assert "endpoints: 2" in output
    assert "execution binding: available" in output
    assert "openapi: recognized" in output


def test_source_probe_cli_reports_unsupported_html_without_generic_failure(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    async def fake_diagnose(self, url: str, **kwargs) -> SourceProbeReport:
        del self, kwargs
        return SourceProbeReport(
            source_url=url,
            requested_kind="auto",
            status="not_recognized",
            diagnostics=[
                SourceProbeDiagnostic(
                    adapter_kind="openapi",
                    discovery_activity="passive",
                    http_methods=["GET"],
                    attempted=True,
                    status="not_recognized",
                ),
                SourceProbeDiagnostic(
                    adapter_kind="graphql",
                    discovery_activity="active",
                    http_methods=["POST"],
                    attempted=False,
                    status="skipped",
                    message=(
                        "active discovery requires an explicit kind or "
                        "allow_active_probes=True"
                    ),
                ),
            ],
        )

    monkeypatch.setattr(SchemaRouter, "diagnose_url", fake_diagnose)

    assert main(["source", "probe", "https://example.test/docs"]) == 0
    output = capsys.readouterr().out

    assert "status: not_recognized" in output
    assert "openapi: not_recognized" in output
    assert "graphql: skipped" in output
    assert "active" in output
    assert capsys.readouterr().err == ""
