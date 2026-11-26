from __future__ import annotations

import json

import httpx
import pytest

from schemarouter import (
    SchemaRouter,
    SchemaSourceError,
    SourceProbeDiagnosticError,
    SourceProbeFailureReport,
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


@pytest.mark.asyncio
async def test_probe_success_reports_adapter_activity_and_considered_path() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=_openapi_document(),
            headers={"content-type": "application/json"},
            request=request,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        router = SchemaRouter(http_client=client)
        probe = await router.probe_url(
            "https://docs.example.test/openapi.json",
            kind="openapi",
        )

    assert probe.status == "recognized"
    assert probe.probe_activity == "passive"
    assert [(item.adapter_kind, item.outcome) for item in probe.adapters_considered] == [
        ("openapi", "recognized")
    ]


@pytest.mark.asyncio
async def test_probe_html_failure_carries_safe_not_recognized_report() -> None:
    source = "https://docs.example.test/reference?token=private-value"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            text="<html><body>docs</body></html>",
            headers={"content-type": "text/html"},
            request=request,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        router = SchemaRouter(http_client=client)
        version = router.registry.version
        with pytest.raises(UnsupportedSchemaSourceError) as exc_info:
            await router.probe_url(source)

        assert router.registry.version == version
        assert router.registry.keys() == ()
        assert router.executor.bound_keys() == ()

    report = exc_info.value.probe_report
    assert isinstance(report, SourceProbeFailureReport)
    assert report.failure_category == "not_recognized"
    assert report.source_url == "https://docs.example.test/reference"
    assert "graphql" in report.skipped_active_adapters
    assert "mcp" in report.skipped_active_adapters
    assert "private-value" not in report.model_dump_json()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status_code", "category"),
    [
        (401, "authentication_failed"),
        (403, "authentication_failed"),
        (404, "not_found"),
    ],
)
async def test_probe_http_status_failures_are_classified(
    status_code: int,
    category: str,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        router = SchemaRouter(http_client=client)
        with pytest.raises(SourceProbeDiagnosticError) as exc_info:
            await router.probe_url(
                "https://docs.example.test/openapi.json",
                kind="openapi",
                schema_headers={"Authorization": "Bearer runtime-secret"},
            )

    report = exc_info.value.probe_report
    assert isinstance(report, SourceProbeFailureReport)
    assert report.failure_category == category
    assert report.adapters_considered[0].adapter_kind == "openapi"
    assert report.adapters_considered[0].outcome == category
    rendered = report.model_dump_json()
    assert "runtime-secret" not in rendered
    assert "Authorization" not in rendered
    assert isinstance(exc_info.value.__cause__, httpx.HTTPStatusError)


@pytest.mark.asyncio
async def test_probe_timeout_is_unreachable_and_preserves_root_cause() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("sensitive upstream timeout detail", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        router = SchemaRouter(http_client=client)
        with pytest.raises(SourceProbeDiagnosticError) as exc_info:
            await router.probe_url(
                "https://docs.example.test/openapi.json",
                kind="openapi",
            )

    report = exc_info.value.probe_report
    assert isinstance(report, SourceProbeFailureReport)
    assert report.failure_category == "unreachable"
    assert "sensitive upstream timeout detail" not in report.model_dump_json()
    assert "sensitive upstream timeout detail" not in str(exc_info.value)
    assert isinstance(exc_info.value.__cause__, httpx.ReadTimeout)


@pytest.mark.asyncio
async def test_probe_malformed_openapi_is_invalid_schema() -> None:
    malformed = {
        "openapi": "3.1.0",
        "info": {"title": "broken", "version": "1"},
        "paths": "not-an-object",
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=malformed,
            headers={"content-type": "application/json"},
            request=request,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        router = SchemaRouter(http_client=client)
        with pytest.raises(SourceProbeDiagnosticError) as exc_info:
            await router.probe_url(
                "https://docs.example.test/openapi.json",
                kind="openapi",
            )

    report = exc_info.value.probe_report
    assert isinstance(report, SourceProbeFailureReport)
    assert report.failure_category == "invalid_schema"
    assert report.adapters_considered[0].outcome == "invalid_schema"


@pytest.mark.asyncio
async def test_probe_unsupported_structured_json_is_not_silent() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"service": "ordinary-json", "version": 1},
            headers={"content-type": "application/json"},
            request=request,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        router = SchemaRouter(http_client=client)
        with pytest.raises(SourceProbeDiagnosticError) as exc_info:
            await router.probe_url(
                "https://docs.example.test/schema.json",
                kind="openapi",
            )

    report = exc_info.value.probe_report
    assert isinstance(report, SourceProbeFailureReport)
    assert report.failure_category == "invalid_schema"


@pytest.mark.asyncio
async def test_probe_graphql_introspection_disabled_is_unsupported_feature() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "errors": [
                    {"message": "introspection denied: bearer secret-value"}
                ]
            },
            request=request,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        router = SchemaRouter(http_client=client)
        with pytest.raises(SourceProbeDiagnosticError) as exc_info:
            await router.probe_url(
                "https://graphql.example.test/graphql",
                kind="graphql",
                schema_headers={"Authorization": "Bearer secret-value"},
            )

    report = exc_info.value.probe_report
    assert isinstance(report, SourceProbeFailureReport)
    assert report.failure_category == "unsupported_feature"
    assert report.adapters_considered[0].adapter_kind == "graphql"
    rendered = report.model_dump_json()
    assert "secret-value" not in rendered
    assert "introspection denied" not in rendered


@pytest.mark.asyncio
async def test_probe_non_mcp_handshake_is_protocol_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import schemarouter.ingestion as ingestion_module

    async def fail_mcp(*args, **kwargs):
        del args, kwargs
        raise RuntimeError("remote handshake payload contains private-token")

    monkeypatch.setattr(ingestion_module, "inspect_mcp_url", fail_mcp)
    router = SchemaRouter()
    version = router.registry.version

    with pytest.raises(SourceProbeDiagnosticError) as exc_info:
        await router.probe_url(
            "https://ordinary.example.test/not-mcp",
            kind="mcp",
        )

    report = exc_info.value.probe_report
    assert isinstance(report, SourceProbeFailureReport)
    assert report.failure_category == "protocol_error"
    assert report.adapters_considered[0].adapter_kind == "mcp"
    assert "private-token" not in report.model_dump_json()
    assert "private-token" not in str(exc_info.value)
    assert router.registry.version == version
    assert router.executor.bound_keys() == ()


def test_source_probe_cli_json_failure_is_structured_and_sanitized(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    report = SourceProbeFailureReport(
        source_url="https://example.test/openapi.json",
        failure_category="authentication_failed",
        adapters_considered=[],
    )

    async def fake_probe(self, url: str, **kwargs) -> SourceProbeResult:
        del self, url, kwargs
        raise SourceProbeDiagnosticError(
            "openapi source probe failed: authentication_failed",
            probe_report=report,
        )

    monkeypatch.setattr(SchemaRouter, "probe_url", fake_probe)

    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "source",
                "probe",
                "https://example.test/openapi.json",
                "--json",
            ]
        )

    assert exc_info.value.code == 2
    payload = json.loads(capsys.readouterr().err)
    assert payload["failure_category"] == "authentication_failed"
    assert payload["status"] == "failed"



@pytest.mark.asyncio
async def test_probe_url_wrong_explicit_kind_is_not_silently_accepted() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=_openapi_document(),
            request=request,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        router = SchemaRouter(http_client=client)
        with pytest.raises(UnsupportedSchemaSourceError) as exc_info:
            await router.probe_url(
                "https://api.example.test/openapi.json",
                kind="graphql",
            )

    report = exc_info.value.probe_report
    assert isinstance(report, SourceProbeFailureReport)
    assert report.failure_category == "not_recognized"
    assert report.adapters_considered[0].adapter_kind == "graphql"


@pytest.mark.asyncio
async def test_auto_probe_reports_considered_and_skipped_adapter_activity() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            text="<html>ordinary docs</html>",
            headers={"content-type": "text/html"},
            request=request,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        router = SchemaRouter(http_client=client)
        with pytest.raises(UnsupportedSchemaSourceError) as exc_info:
            await router.probe_url(
                "https://docs.example.test/reference",
                kind="auto",
            )

    report = exc_info.value.probe_report
    assert isinstance(report, SourceProbeFailureReport)
    assert report.failure_category == "not_recognized"
    assert report.active_probes_allowed is False
    assert "graphql" in report.skipped_active_adapters
    assert "mcp" in report.skipped_active_adapters
    assert all(
        item.activity == "passive"
        for item in report.adapters_considered
    )
