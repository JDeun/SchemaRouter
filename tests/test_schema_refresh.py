from __future__ import annotations

from copy import deepcopy

import httpx
import pytest

from schemarouter import SchemaRouter


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
