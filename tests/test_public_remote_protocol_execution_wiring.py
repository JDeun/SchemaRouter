"""Registered public OpenRPC/OData execution: permission and binding regressions.

Deterministic local HTTP transport exercises SchemaRouter.execute end-to-end.
This is developer evidence; it is not independent provider/model E2.
"""
from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from schemarouter import (
    AuthorizationPolicy,
    AuthorizationRule,
    ExecutionPlan,
    ExecutionPolicy,
    PlanValidationError,
    PolicyViolationError,
    PrincipalContext,
    RunConfig,
    SchemaRouter,
    SchemaValidationError,
    ToolCall,
)


def _plan(
    router: SchemaRouter,
    tool_key: str,
    operation: str,
    args: dict,
    fields: list[str],
) -> ExecutionPlan:
    tool = router.registry.get(tool_key)
    endpoint = tool.endpoint(operation)
    return ExecutionPlan(
        query="read one source record",
        registry_version=router.registry.version,
        calls=[ToolCall(
            tool=tool.key,
            endpoint=endpoint.name,
            arguments=args,
            fields=fields,
            schema_fingerprint=endpoint.fingerprint,
            tool_fingerprint=tool.fingerprint,
        )],
    )


def _policy(operation: str) -> AuthorizationPolicy:
    return AuthorizationPolicy(
        rules=(AuthorizationRule(effect="allow", operation=operation, roles_any=("reader",)),),
        default_effect="deny",
    )


READER = RunConfig(principal=PrincipalContext(subject="reader", roles=("reader",)))
GUEST = RunConfig(principal=PrincipalContext(subject="guest", roles=("guest",)))


def _openrpc_document() -> dict:
    return {
        "openrpc": "1.4.0",
        "info": {"title": "Materials RPC", "version": "1.0.0"},
        "servers": [{"name": "default", "url": "https://rpc.example/rpc"}],
        "methods": [{
            "name": "materials.get",
            "paramStructure": "by-name",
            "params": [{
                "name": "material_id", "required": True, "schema": {"type": "string"},
            }],
            "result": {
                "name": "Material result",
                "schema": {
                    "type": "object",
                    "properties": {"material_id": {"type": "string"}},
                    "required": ["material_id"],
                },
            },
        }],
    }


@pytest.mark.asyncio
async def test_openrpc_public_execute_denies_guest_and_bad_input_before_http() -> None:
    execution_calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/openrpc.json":
            return httpx.Response(200, json=_openrpc_document(), request=request)
        execution_calls.append(request.url.path)
        assert request.method == "POST" and request.url.path == "/rpc"
        payload = json.loads(request.content)
        assert payload["method"] == "materials.get"
        return httpx.Response(
            200,
            json={"jsonrpc": "2.0", "id": payload["id"], "result": {"material_id": "mp-1"}},
            request=request,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        router = await SchemaRouter.from_url(
            "https://rpc.example/openrpc.json",
            kind="openrpc",
            http_client=client,
            authorization_policy=_policy("materials_rpc.materials.get"),
            policy=ExecutionPolicy(allow_unclassified_remote=True),
        )
        tool = router.registry.get("materials_rpc")
        endpoint = tool.endpoint("materials.get")
        assert endpoint.read_only is None  # Do not infer safety from method name.
        good = _plan(router, tool.key, endpoint.name, {"material_id": "mp-1"}, ["material_id"])
        bad = _plan(router, tool.key, endpoint.name, {"not_declared": 1}, ["material_id"])

        with pytest.raises(PolicyViolationError, match="authorization denied"):
            await router.execute(good, config=GUEST)
        assert execution_calls == []

        with pytest.raises((PlanValidationError, SchemaValidationError)):
            await router.execute(bad, config=READER)
        assert execution_calls == []

        result = await router.execute(good, config=READER)
        assert len(result) == 1
        assert result[0].data == {"material_id": "mp-1"}
        assert execution_calls == ["/rpc"]

        await router.aremove_tool(tool.key)
        with pytest.raises(PolicyViolationError):
            await router.execute(good, config=READER)
        assert execution_calls == ["/rpc"]


ODATA_METADATA = b"""<?xml version="1.0" encoding="utf-8"?>
<edmx:Edmx Version="4.0" xmlns:edmx="http://docs.oasis-open.org/odata/ns/edmx">
  <edmx:DataServices>
    <Schema Namespace="Demo" xmlns="http://docs.oasis-open.org/odata/ns/edm">
      <EntityType Name="Product">
        <Key><PropertyRef Name="ID" /></Key>
        <Property Name="ID" Type="Edm.Int32" Nullable="false" />
      </EntityType>
      <EntityContainer Name="Container">
        <EntitySet Name="Products" EntityType="Demo.Product" />
      </EntityContainer>
    </Schema>
  </edmx:DataServices>
</edmx:Edmx>"""


@pytest.mark.asyncio
async def test_odata_public_execute_denies_guest_and_stale_plan_before_http() -> None:
    execution_calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/odata/$metadata":
            return httpx.Response(200, content=ODATA_METADATA, request=request)
        execution_calls.append(request.url.path)
        assert request.method == "GET" and request.url.path == "/odata/Products"
        return httpx.Response(200, json={"value": [{"ID": 1}]}, request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        router = await SchemaRouter.from_url(
            "https://odata.example/odata",
            kind="odata",
            http_client=client,
            authorization_policy=_policy("odata.example.list_products"),
        )
        tool = router.registry.get("odata.example")
        endpoint = tool.endpoint("list_products")
        assert endpoint.read_only is True
        good = _plan(router, tool.key, endpoint.name, {"top": 1}, ["ID"])

        with pytest.raises(PolicyViolationError, match="authorization denied"):
            await router.execute(good, config=GUEST)
        assert execution_calls == []

        result = await router.execute(good, config=READER)
        assert len(result) == 1
        assert result[0].data == [{"ID": 1}]
        assert execution_calls == ["/odata/Products"]

        await router.aremove_tool(tool.key)
        with pytest.raises(PolicyViolationError):
            await router.execute(good, config=READER)
        assert execution_calls == ["/odata/Products"]


def test_remote_protocol_matrix_is_versioned_and_has_executable_tests() -> None:
    manifest = (
        Path(__file__).resolve().parents[1]
        / "benchmarks/public-execution-remote-protocol-v1.json"
    )
    data = json.loads(manifest.read_text(encoding="utf-8"))
    assert data["schema_version"] == 1
    assert data["qualification"] == "DEV_ONLY"
    assert {item["id"] for item in data["paths"]} == {
        "router.openrpc.public-execute",
        "router.odata.public-execute",
    }
    for entry in data["paths"]:
        assert entry["public_entrypoint"] == "schemarouter.SchemaRouter.execute"
        assert entry["evidence"] == "local-httpx-mocktransport"
        assert entry["positive_test"] == entry["denial_test"]
        assert entry["positive_test"] in globals()
        assert entry["checked"] and "denied-principal-no-http" in entry["checked"]
