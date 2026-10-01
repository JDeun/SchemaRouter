from __future__ import annotations

import httpx
import pytest

from schemarouter import EndpointSpec, SchemaRouter, ToolSpec
from schemarouter.schema_http import (
    conditional_schema_headers,
    normalize_schema_http_validators,
)


def _openapi_document(*, summary: str | None = None) -> dict:
    return {
        "openapi": "3.1.0",
        "info": {"title": "Validator API", "version": "1.0.0"},
        "servers": [{"url": "https://example.test"}],
        "paths": {
            "/materials": {
                "get": {
                    "operationId": "materials_search",
                    "summary": summary,
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


def _openrpc_document() -> dict:
    return {
        "openrpc": "1.4.0",
        "info": {"title": "RPC", "version": "1.0.0"},
        "servers": [{"name": "default", "url": "https://rpc.test/rpc"}],
        "methods": [
            {
                "name": "ping",
                "params": [],
                "result": {
                    "name": "result",
                    "schema": {
                        "type": "object",
                        "properties": {"ok": {"type": "boolean"}},
                    },
                },
            }
        ],
    }


_ODATA_METADATA = b"""<?xml version="1.0" encoding="utf-8"?>
<edmx:Edmx Version="4.0"
  xmlns:edmx="http://docs.oasis-open.org/odata/ns/edmx">
  <edmx:DataServices>
    <Schema Namespace="Demo"
      xmlns="http://docs.oasis-open.org/odata/ns/edm">
      <EntityType Name="Material">
        <Key><PropertyRef Name="ID"/></Key>
        <Property Name="ID" Type="Edm.String" Nullable="false"/>
        <Property Name="Name" Type="Edm.String"/>
      </EntityType>
      <EntityContainer Name="Container">
        <EntitySet Name="Materials" EntityType="Demo.Material"/>
      </EntityContainer>
    </Schema>
  </edmx:DataServices>
</edmx:Edmx>
"""


def test_schema_http_validator_normalization_is_privacy_bounded() -> None:
    assert normalize_schema_http_validators(
        {
            "etag": '"v1"',
            "last_modified": "Wed, 21 Oct 2015 07:28:00 GMT",
            "authorization": "secret",
        }
    ) == {
        "etag": '"v1"',
        "last_modified": "Wed, 21 Oct 2015 07:28:00 GMT",
    }

    assert normalize_schema_http_validators(
        {
            "etag": "bad\r\nInjected: value",
            "last_modified": "",
        }
    ) == {}


def test_caller_conditional_headers_are_replaced_by_accepted_validator() -> None:
    headers = conditional_schema_headers(
        {
            "If-Modified-Since": "caller-value",
            "If-None-Match": '"caller-etag"',
            "X-Trace": "keep-me",
        },
        {"etag": '"cached"', "last_modified": "cached-date"},
    )

    assert headers == {
        "X-Trace": "keep-me",
        "If-None-Match": '"cached"',
    }

@pytest.mark.asyncio
async def test_openapi_refresh_uses_etag_and_304_without_registry_write() -> None:
    seen_headers: list[dict[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_headers.append(dict(request.headers))
        if request.headers.get("if-none-match") == '"v1"':
            return httpx.Response(
                304,
                headers={"ETag": '"v1"'},
                request=request,
            )
        return httpx.Response(
            200,
            json=_openapi_document(),
            headers={
                "ETag": '"v1"',
                "Last-Modified": "Wed, 21 Oct 2015 07:28:00 GMT",
            },
            request=request,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        router = SchemaRouter(http_client=client)
        tool = await router.add_url(
            "https://example.test/openapi.json",
            kind="openapi",
            name="materials",
        )
        version = router.registry.version

        assert router.loader.schema_http_validators_for(tool.key, tool) == {
            "etag": '"v1"',
            "last_modified": "Wed, 21 Oct 2015 07:28:00 GMT",
        }

        result = await router.arefresh_schema(tool.key)

    assert result.action == "unchanged"
    assert result.compatibility == "identical"
    assert router.registry.version == version
    assert seen_headers[-1]["if-none-match"] == '"v1"'
    assert "if-modified-since" not in seen_headers[-1]

@pytest.mark.asyncio
async def test_openapi_refresh_uses_last_modified_when_etag_missing() -> None:
    modified = "Wed, 21 Oct 2015 07:28:00 GMT"
    seen_headers: list[dict[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_headers.append(dict(request.headers))
        if request.headers.get("if-modified-since") == modified:
            return httpx.Response(
                304,
                headers={"Last-Modified": modified},
                request=request,
            )
        return httpx.Response(
            200,
            json=_openapi_document(),
            headers={"Last-Modified": modified},
            request=request,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        router = SchemaRouter(http_client=client)
        tool = await router.add_url(
            "https://example.test/openapi.json",
            kind="openapi",
            name="materials",
        )
        result = await router.arefresh_schema(tool.key)

    assert result.action == "unchanged"
    assert seen_headers[-1]["if-modified-since"] == modified
    assert "if-none-match" not in seen_headers[-1]

@pytest.mark.asyncio
async def test_stale_openapi_etag_falls_back_to_full_compare_and_updates_cache() -> None:
    state = {
        "etag": '"v1"',
        "document": _openapi_document(),
    }
    seen_etags: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_etags.append(request.headers.get("if-none-match"))
        if request.headers.get("if-none-match") == state["etag"]:
            return httpx.Response(
                304,
                headers={"ETag": state["etag"]},
                request=request,
            )
        return httpx.Response(
            200,
            json=state["document"],
            headers={"ETag": state["etag"]},
            request=request,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        router = SchemaRouter(http_client=client)
        tool = await router.add_url(
            "https://example.test/openapi.json",
            kind="openapi",
            name="materials",
        )

        state["etag"] = '"v2"'
        state["document"] = _openapi_document(summary="Updated")

        applied = await router.arefresh_schema(tool.key)
        unchanged = await router.arefresh_schema(tool.key)

    assert applied.action == "applied"
    assert applied.compatibility == "compatible"
    assert unchanged.action == "unchanged"
    assert seen_etags[-2:] == ['"v1"', '"v2"']
    assert router.loader.schema_http_validators_for(
        tool.key,
        router.registry.get(tool.key),
    ) == {
        "etag": '"v2"',
    }

@pytest.mark.asyncio
async def test_openapi_external_refs_mode_does_not_use_root_validator_shortcut() -> None:
    seen_headers: list[dict[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_headers.append(dict(request.headers))
        return httpx.Response(
            200,
            json=_openapi_document(),
            headers={"ETag": '"v1"'},
            request=request,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        router = SchemaRouter(http_client=client)
        tool = await router.add_url(
            "https://example.test/openapi.json",
            kind="openapi",
            name="materials",
            openapi_external_refs=True,
        )
        result = await router.arefresh_schema(tool.key)

    assert result.action == "unchanged"
    assert "if-none-match" not in seen_headers[-1]
    assert "if-modified-since" not in seen_headers[-1]

@pytest.mark.asyncio
async def test_openrpc_refresh_uses_etag_and_304() -> None:
    seen_headers: list[dict[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_headers.append(dict(request.headers))
        if request.headers.get("if-none-match") == '"rpc-v1"':
            return httpx.Response(
                304,
                headers={"ETag": '"rpc-v1"'},
                request=request,
            )
        return httpx.Response(
            200,
            json=_openrpc_document(),
            headers={"ETag": '"rpc-v1"'},
            request=request,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        router = SchemaRouter(http_client=client)
        tool = await router.add_url(
            "https://rpc.test/openrpc.json",
            kind="openrpc",
            name="rpc",
        )
        result = await router.arefresh_schema(tool.key)

    assert result.action == "unchanged"
    assert seen_headers[-1]["if-none-match"] == '"rpc-v1"'

@pytest.mark.asyncio
async def test_odata_refresh_uses_metadata_etag_and_304() -> None:
    seen_headers: list[dict[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/$metadata"
        seen_headers.append(dict(request.headers))
        if request.headers.get("if-none-match") == '"odata-v1"':
            return httpx.Response(
                304,
                headers={"ETag": '"odata-v1"'},
                request=request,
            )
        return httpx.Response(
            200,
            content=_ODATA_METADATA,
            headers={
                "Content-Type": "application/xml",
                "ETag": '"odata-v1"',
            },
            request=request,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        router = SchemaRouter(http_client=client)
        tool = await router.add_url(
            "https://odata.test/v1",
            kind="odata",
            name="odata",
        )
        result = await router.arefresh_schema(tool.key)

    assert result.action == "unchanged"
    assert seen_headers[-1]["if-none-match"] == '"odata-v1"'

@pytest.mark.asyncio
async def test_breaking_candidate_does_not_poison_validator_cache() -> None:
    state = {
        "etag": '"v1"',
        "document": _openapi_document(),
    }
    seen_etags: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_etags.append(request.headers.get("if-none-match"))
        if request.headers.get("if-none-match") == state["etag"]:
            return httpx.Response(
                304,
                headers={"ETag": state["etag"]},
                request=request,
            )
        return httpx.Response(
            200,
            json=state["document"],
            headers={"ETag": state["etag"]},
            request=request,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        router = SchemaRouter(http_client=client)
        tool = await router.add_url(
            "https://example.test/openapi.json",
            kind="openapi",
            name="materials",
        )

        breaking = _openapi_document()
        breaking["paths"]["/materials"]["get"]["parameters"] = [
            {
                "name": "q",
                "in": "query",
                "required": True,
                "schema": {"type": "string"},
            }
        ]
        state["etag"] = '"v2"'
        state["document"] = breaking

        first = await router.arefresh_schema(tool.key)
        second = await router.arefresh_schema(tool.key)

    assert first.action == "pending_review"
    assert second.action == "pending_review"
    assert seen_etags[-2:] == ['"v1"', '"v1"']
    assert router.loader.schema_http_validators_for(
        tool.key,
        router.registry.get(tool.key),
    ) == {
        "etag": '"v1"',
    }

@pytest.mark.asyncio
async def test_report_only_compatible_candidate_keeps_current_validator() -> None:
    state = {
        "etag": '"v1"',
        "document": _openapi_document(),
    }
    seen_etags: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_etags.append(request.headers.get("if-none-match"))
        if request.headers.get("if-none-match") == state["etag"]:
            return httpx.Response(
                304,
                headers={"ETag": state["etag"]},
                request=request,
            )
        return httpx.Response(
            200,
            json=state["document"],
            headers={"ETag": state["etag"]},
            request=request,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        router = SchemaRouter(http_client=client)
        tool = await router.add_url(
            "https://example.test/openapi.json",
            kind="openapi",
            name="materials",
        )

        state["etag"] = '"v2"'
        state["document"] = _openapi_document(summary="Updated")

        first = await router.arefresh_schema(
            tool.key,
            apply_compatible=False,
        )
        second = await router.arefresh_schema(
            tool.key,
            apply_compatible=False,
        )

    assert first.action == "report_only"
    assert second.action == "report_only"
    assert seen_etags[-2:] == ['"v1"', '"v1"']
    assert router.loader.schema_http_validators_for(
        tool.key,
        router.registry.get(tool.key),
    ) == {
        "etag": '"v1"',
    }


@pytest.mark.asyncio
async def test_same_key_source_replacement_does_not_reuse_old_etag() -> None:
    shared_etag = '"shared"'
    seen_b_headers: list[dict[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "source-a.example.test":
            return httpx.Response(
                200,
                json=_openapi_document(),
                headers={"ETag": shared_etag},
                request=request,
            )
        if request.url.host == "source-b.example.test":
            seen_b_headers.append(dict(request.headers))
            if request.headers.get("if-none-match") == shared_etag:
                return httpx.Response(
                    304,
                    headers={"ETag": shared_etag},
                    request=request,
                )
            return httpx.Response(
                200,
                json=_openapi_document(),
                headers={"ETag": shared_etag},
                request=request,
            )
        raise AssertionError(f"unexpected host: {request.url.host}")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        router = SchemaRouter(http_client=client)
        original = await router.add_url(
            "https://source-a.example.test/openapi.json",
            kind="openapi",
            name="materials",
            base_url="https://source-a.example.test",
        )

        replacement = original.model_copy(deep=True)
        replacement.metadata["source_url"] = (
            "https://source-b.example.test/openapi.json"
        )
        replacement.metadata["resolved_schema_url"] = (
            "https://source-b.example.test/openapi.json"
        )
        replacement.execution_metadata["approved_base_url"] = (
            "https://source-b.example.test"
        )

        # Deliberately retain source A's persisted validator metadata. The
        # source digest must prevent it from becoming a B validator.
        router.add_tool(replacement, replace=True)

        result = await router.arefresh_schema(original.key)

    assert result.action == "unchanged"
    assert seen_b_headers
    assert "if-none-match" not in seen_b_headers[0]

@pytest.mark.asyncio
async def test_cross_adapter_same_key_does_not_inherit_validator_cache() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=_openapi_document(),
            headers={"ETag": '"openapi-v1"'},
            request=request,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        router = SchemaRouter(http_client=client)
        original = await router.add_url(
            "https://source-a.example.test/openapi.json",
            kind="openapi",
            name="materials",
            base_url="https://source-a.example.test",
        )

        replacement = original.model_copy(deep=True)
        replacement.source_type = "openrpc"
        replacement.access_mode = "openrpc"
        replacement.execution_metadata = {
            "adapter": "openrpc",
            "execution_bound": False,
            "requires_explicit_base_url": True,
        }
        replacement.metadata["adapter"] = "openrpc"
        replacement.metadata["source_url"] = (
            "https://source-b.example.test/openrpc.json"
        )
        replacement.metadata.pop("resolved_schema_url", None)

        router.add_tool(replacement, replace=True)

        assert router.loader.schema_http_validators_for(
            replacement.key,
            router.registry.get(replacement.key),
        ) == {}


def test_validator_metadata_without_matching_source_digest_is_ignored() -> None:
    router = SchemaRouter()
    tool = ToolSpec(
        name="legacy",
        remote=True,
        execution_metadata={"adapter": "openapi"},
        metadata={
            "adapter": "openapi",
            "source_url": "https://example.test/openapi.json",
            "schema_http_validators": {"etag": '"legacy"'},
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

    assert router.loader.schema_http_validators_for(tool.key, tool) == {}


def test_validator_metadata_with_malformed_source_digest_is_ignored() -> None:
    router = SchemaRouter()
    tool = ToolSpec(
        name="malformed",
        remote=True,
        execution_metadata={"adapter": "openapi"},
        metadata={
            "adapter": "openapi",
            "source_url": "https://example.test/openapi.json",
            "schema_http_validators": {"etag": '"v1"'},
            "schema_http_validator_source": "not-a-valid-digest",
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

    assert router.loader.schema_http_validators_for(tool.key, tool) == {}


def test_validator_cache_lookup_without_current_tool_fails_closed() -> None:
    router = SchemaRouter()
    tool = ToolSpec(
        name="remote",
        remote=True,
        execution_metadata={"adapter": "openapi"},
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

    assert router.loader.schema_http_validators_for(tool.key) == {}
