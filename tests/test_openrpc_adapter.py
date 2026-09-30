from __future__ import annotations

import json

import httpx
import pytest

from schemarouter import (
    ExecutionPlan,
    ExecutionPolicy,
    SchemaRouter,
    ToolCall,
)
from schemarouter.adapters import tool_from_openrpc
from schemarouter.errors import NonRetryableInvocationError


def openrpc_document() -> dict:
    return {
        "openrpc": "1.4.0",
        "info": {
            "title": "Materials RPC",
            "version": "1.0.0",
            "description": "Typed JSON-RPC materials fixture",
        },
        "servers": [{"name": "default", "url": "https://rpc.example/rpc"}],
        "methods": [
            {
                "name": "materials.get",
                "description": "Get one material",
                "paramStructure": "by-name",
                "params": [
                    {
                        "name": "material_id",
                        "required": True,
                        "schema": {"type": "string"},
                    }
                ],
                "result": {
                    "name": "Material result",
                    "schema": {
                        "$ref": "#/components/schemas/MaterialResult",
                    },
                },
            }
        ],
        "components": {
            "schemas": {
                "MaterialResult": {
                    "type": "object",
                    "required": ["material_id"],
                    "properties": {
                        "material_id": {"type": "string"},
                        "properties": {
                            "type": "object",
                            "properties": {
                                "band_gap": {
                                    "type": "number",
                                    "description": "Electronic band gap",
                                    "x-ucum-unit": "eV",
                                },
                                "density": {"type": "number"},
                            },
                        },
                    },
                }
            }
        },
    }


def test_openrpc_compiles_methods_params_refs_and_nested_result_fields() -> None:
    tool = tool_from_openrpc("materials_rpc", openrpc_document())

    assert tool.source_type == "openrpc"
    endpoint = tool.endpoint("materials.get")
    assert endpoint.method == "POST"
    assert endpoint.read_only is None
    assert endpoint.destructive is None
    assert endpoint.parameters[0].name == "material_id"
    assert endpoint.parameters[0].required is True

    fields = {field.name: field for field in endpoint.output_fields}
    assert {"material_id", "properties", "properties.band_gap", "properties.density"} <= set(
        fields
    )
    assert fields["properties.band_gap"].path == ["properties", "band_gap"]
    assert fields["properties.band_gap"].result_path == ["properties.band_gap"]
    assert fields["properties.band_gap"].unit == "eV"
    assert fields["properties.band_gap"].source_type == "openrpc"


@pytest.mark.asyncio
async def test_openrpc_url_discovery_and_jsonrpc_execution() -> None:
    seen_requests: list[dict] = []
    seen_headers: list[dict[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url.path == "/openrpc.json":
            return httpx.Response(200, json=openrpc_document(), request=request)
        if request.method == "POST" and request.url.path == "/rpc":
            payload = json.loads(request.content)
            seen_requests.append(payload)
            seen_headers.append(dict(request.headers))
            return httpx.Response(
                200,
                json={
                    "jsonrpc": "2.0",
                    "id": payload["id"],
                    "result": {
                        "material_id": "mp-1",
                        "properties": {
                            "band_gap": 1.25,
                            "density": 2.4,
                        },
                    },
                },
                request=request,
            )
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    token = "secret-rpc-token"
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        router = await SchemaRouter.from_url(
            "https://rpc.example/openrpc.json",
            kind="openrpc",
            trusted_headers={"Authorization": f"Bearer {token}"},
            http_client=client,
            policy=ExecutionPolicy(allow_unclassified_remote=True),
        )
        tool = router.registry.get("materials_rpc")
        endpoint = tool.endpoint("materials.get")
        call = ToolCall(
            tool=tool.key,
            endpoint=endpoint.name,
            arguments={"material_id": "mp-1"},
            fields=["material_id", "properties.band_gap"],
            schema_fingerprint=endpoint.fingerprint,
            tool_fingerprint=tool.fingerprint,
        )
        plan = ExecutionPlan(
            query="material band gap",
            registry_version=router.registry.version,
            calls=[call],
        )
        results = await router.execute(plan)

    assert seen_requests[0]["jsonrpc"] == "2.0"
    assert seen_requests[0]["method"] == "materials.get"
    assert seen_requests[0]["params"] == {"material_id": "mp-1"}
    assert seen_headers[0]["authorization"] == f"Bearer {token}"
    assert token not in repr(tool.model_dump(mode="json"))
    assert results[0].data == {
        "material_id": "mp-1",
        "properties.band_gap": 1.25,
    }


def test_openrpc_does_not_infer_read_only_authority_from_descriptions() -> None:
    document = openrpc_document()
    document["methods"][0]["description"] = "Read-only safe lookup"

    endpoint = tool_from_openrpc("rpc", document).endpoint("materials.get")

    assert endpoint.read_only is None
    assert endpoint.destructive is None


@pytest.mark.asyncio
async def test_openrpc_positional_params_fail_on_ambiguous_optional_gap() -> None:
    document = openrpc_document()
    method = document["methods"][0]
    method["paramStructure"] = "by-position"
    method["params"] = [
        {
            "name": "first",
            "required": False,
            "schema": {"type": "string"},
        },
        {
            "name": "second",
            "required": False,
            "schema": {"type": "string"},
        },
    ]

    seen = {"post": False}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, json=document, request=request)
        seen["post"] = True
        return httpx.Response(500, request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        router = await SchemaRouter.from_url(
            "https://rpc.example/openrpc.json",
            kind="openrpc",
            base_url="https://rpc.example/rpc",
            http_client=client,
        )
        tool = router.registry.get("materials_rpc")
        endpoint = tool.endpoint("materials.get")
        call = ToolCall(
            tool=tool.key,
            endpoint=endpoint.name,
            arguments={"second": "value"},
            fields=[],
            schema_fingerprint=endpoint.fingerprint,
            tool_fingerprint=tool.fingerprint,
        )

        with pytest.raises(
            NonRetryableInvocationError,
            match="cannot skip an earlier optional parameter",
        ):
            await router.executor.execute_call(call)

    assert seen["post"] is False


@pytest.mark.asyncio
async def test_openrpc_cross_origin_server_requires_explicit_base_url() -> None:
    document = openrpc_document()
    document["servers"] = [{"url": "https://other.example/rpc"}]

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, json=document, request=request)
        raise AssertionError("cross-origin server must not be called automatically")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        router = await SchemaRouter.from_url(
            "https://rpc.example/openrpc.json",
            kind="openrpc",
            http_client=client,
        )

    tool = router.registry.get("materials_rpc")
    assert tool.execution_metadata["execution_bound"] is False
    assert tool.execution_metadata["requires_explicit_base_url"] is True
    assert tool.metadata["suggested_base_url"] == "https://other.example/rpc"
