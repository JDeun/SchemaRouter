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
from schemarouter.adapters import tool_from_graphql_introspection


def _ref(kind: str, name: str | None = None, of_type: dict | None = None) -> dict:
    return {"kind": kind, "name": name, "ofType": of_type}


def introspection() -> dict:
    material_type = {
        "kind": "OBJECT",
        "name": "Material",
        "description": None,
        "fields": [
            {
                "name": "id",
                "description": "Material identifier",
                "isDeprecated": False,
                "deprecationReason": None,
                "args": [],
                "type": _ref("NON_NULL", of_type=_ref("SCALAR", "ID")),
            },
            {
                "name": "bandGap",
                "description": "Band gap",
                "isDeprecated": False,
                "deprecationReason": None,
                "args": [],
                "type": _ref("SCALAR", "Float"),
            },
            {
                "name": "metadata",
                "description": None,
                "isDeprecated": False,
                "deprecationReason": None,
                "args": [],
                "type": _ref("OBJECT", "Metadata"),
            },
        ],
        "inputFields": None,
        "enumValues": None,
        "possibleTypes": None,
    }
    metadata_type = {
        "kind": "OBJECT",
        "name": "Metadata",
        "description": None,
        "fields": [
            {
                "name": "source",
                "description": None,
                "isDeprecated": False,
                "deprecationReason": None,
                "args": [],
                "type": _ref("SCALAR", "String"),
            }
        ],
        "inputFields": None,
        "enumValues": None,
        "possibleTypes": None,
    }
    query_type = {
        "kind": "OBJECT",
        "name": "Query",
        "description": None,
        "fields": [
            {
                "name": "material",
                "description": "Get one material",
                "isDeprecated": False,
                "deprecationReason": None,
                "args": [
                    {
                        "name": "id",
                        "description": "Material id",
                        "defaultValue": None,
                        "type": _ref(
                            "NON_NULL",
                            of_type=_ref("SCALAR", "ID"),
                        ),
                    }
                ],
                "type": _ref("OBJECT", "Material"),
            }
        ],
        "inputFields": None,
        "enumValues": None,
        "possibleTypes": None,
    }
    mutation_type = {
        "kind": "OBJECT",
        "name": "Mutation",
        "description": None,
        "fields": [
            {
                "name": "deleteMaterial",
                "description": "Delete one material",
                "isDeprecated": False,
                "deprecationReason": None,
                "args": [
                    {
                        "name": "id",
                        "description": None,
                        "defaultValue": None,
                        "type": _ref(
                            "NON_NULL",
                            of_type=_ref("SCALAR", "ID"),
                        ),
                    }
                ],
                "type": _ref("SCALAR", "Boolean"),
            }
        ],
        "inputFields": None,
        "enumValues": None,
        "possibleTypes": None,
    }
    return {
        "data": {
            "__schema": {
                "queryType": {"name": "Query"},
                "mutationType": {"name": "Mutation"},
                "subscriptionType": None,
                "types": [
                    query_type,
                    mutation_type,
                    material_type,
                    metadata_type,
                    {"kind": "SCALAR", "name": "ID", "fields": None, "inputFields": None, "enumValues": None, "possibleTypes": None},
                    {"kind": "SCALAR", "name": "String", "fields": None, "inputFields": None, "enumValues": None, "possibleTypes": None},
                    {"kind": "SCALAR", "name": "Float", "fields": None, "inputFields": None, "enumValues": None, "possibleTypes": None},
                    {"kind": "SCALAR", "name": "Boolean", "fields": None, "inputFields": None, "enumValues": None, "possibleTypes": None},
                ],
            }
        }
    }


def test_graphql_introspection_compiles_query_mutation_and_nested_fields() -> None:
    tool = tool_from_graphql_introspection("materials_graphql", introspection())

    query = tool.endpoint("material")
    mutation = tool.endpoint("deleteMaterial")

    assert query.read_only is True
    assert query.destructive is False
    assert mutation.read_only is False
    assert mutation.destructive is None
    assert query.parameters[0].name == "id"
    assert query.parameters[0].required is True

    fields = {field.name: field for field in query.output_fields}
    assert {"id", "bandGap", "metadata", "metadata.source"} <= set(fields)
    assert fields["metadata.source"].path == ["metadata", "source"]
    assert fields["metadata.source"].result_path == ["metadata.source"]
    assert fields["metadata.source"].source_type == "graphql"


@pytest.mark.asyncio
async def test_graphql_selected_fields_become_selection_set() -> None:
    seen_payloads: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        seen_payloads.append(payload)
        if "__schema" in payload["query"]:
            return httpx.Response(200, json=introspection(), request=request)
        return httpx.Response(
            200,
            json={
                "data": {
                    "material": {
                        "id": "mp-1",
                        "metadata": {"source": "fixture"},
                    }
                }
            },
            request=request,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        router = await SchemaRouter.from_url(
            "https://graphql.example/graphql",
            kind="graphql",
            http_client=client,
        )
        tool = router.registry.get("graphql.example")
        endpoint = tool.endpoint("material")
        call = ToolCall(
            tool=tool.key,
            endpoint=endpoint.name,
            arguments={"id": "mp-1"},
            fields=["id", "metadata.source"],
            schema_fingerprint=endpoint.fingerprint,
            tool_fingerprint=tool.fingerprint,
        )
        plan = ExecutionPlan(
            query="material source",
            registry_version=router.registry.version,
            calls=[call],
        )
        results = await router.execute(plan)

    query = seen_payloads[-1]["query"]
    assert "material(id: $id)" in query
    assert "id" in query
    assert "metadata { source }" in query
    assert "bandGap" not in query
    assert results[0].data == {
        "id": "mp-1",
        "metadata.source": "fixture",
    }


@pytest.mark.asyncio
async def test_graphql_mutation_remains_policy_gated() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        payload = json.loads(request.content)
        if "__schema" in payload["query"]:
            return httpx.Response(200, json=introspection(), request=request)
        calls += 1
        return httpx.Response(
            200,
            json={"data": {"deleteMaterial": True}},
            request=request,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        router = await SchemaRouter.from_url(
            "https://graphql.example/graphql",
            kind="graphql",
            http_client=client,
        )
        tool = router.registry.get("graphql.example")
        endpoint = tool.endpoint("deleteMaterial")
        call = ToolCall(
            tool=tool.key,
            endpoint=endpoint.name,
            arguments={"id": "mp-1"},
            fields=[],
            schema_fingerprint=endpoint.fingerprint,
            tool_fingerprint=tool.fingerprint,
        )
        plan = ExecutionPlan(
            query="delete material",
            registry_version=router.registry.version,
            calls=[call],
        )
        with pytest.raises(Exception, match="mutating operation"):
            await router.execute(plan)

    assert calls == 0


@pytest.mark.asyncio
async def test_graphql_mutation_requires_explicit_local_policy_to_run() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        if "__schema" in payload["query"]:
            return httpx.Response(200, json=introspection(), request=request)
        return httpx.Response(
            200,
            json={"data": {"deleteMaterial": True}},
            request=request,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        router = await SchemaRouter.from_url(
            "https://graphql.example/graphql",
            kind="graphql",
            http_client=client,
            policy=ExecutionPolicy(allow_mutations=True),
        )
        tool = router.registry.get("graphql.example")
        endpoint = tool.endpoint("deleteMaterial")
        call = ToolCall(
            tool=tool.key,
            endpoint=endpoint.name,
            arguments={"id": "mp-1"},
            fields=[],
            schema_fingerprint=endpoint.fingerprint,
            tool_fingerprint=tool.fingerprint,
        )
        plan = ExecutionPlan(
            query="delete material",
            registry_version=router.registry.version,
            calls=[call],
        )
        results = await router.execute(plan)

    assert results[0].data is True
