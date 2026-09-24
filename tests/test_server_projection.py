import httpx
import pytest

from schemarouter import (
    EndpointSpec,
    FieldSpec,
    InMemoryRegistry,
    RegistryExecutor,
    ServerProjectionSpec,
    ToolCall,
    ToolSpec,
)
from schemarouter.adapters import OpenAPIRemoteInvoker


@pytest.mark.asyncio
async def test_openapi_server_projection_pushes_only_selected_fields_upstream() -> None:
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["fields"] = request.url.params.get("fields")
        return httpx.Response(
            200,
            json={
                "material_id": "mp-149",
                "elastic_modulus": 130.0,
            },
            request=request,
        )

    endpoint = EndpointSpec(
        name="search",
        method="GET",
        path="/materials",
        read_only=True,
        output_fields=[
            FieldSpec(name="material_id", identifier=True),
            FieldSpec(name="elastic_modulus", aliases=["탄성계수"]),
            FieldSpec(name="density"),
        ],
        output_schema={
            "type": "object",
            "properties": {
                "material_id": {"type": "string"},
                "elastic_modulus": {"type": "number"},
                "density": {"type": "number"},
            },
            "required": ["material_id", "elastic_modulus", "density"],
        },
        server_projection=ServerProjectionSpec(parameter="fields"),
    )
    tool = ToolSpec(name="materials", endpoints=[endpoint])
    registry = InMemoryRegistry()
    registry.register(tool)
    call = ToolCall(
        tool="materials",
        endpoint="search",
        fields=["material_id", "elastic_modulus"],
        schema_fingerprint=endpoint.fingerprint,
        tool_fingerprint=tool.fingerprint,
    )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        executor = RegistryExecutor(registry)
        executor.bind(
            "materials",
            OpenAPIRemoteInvoker(
                tool,
                "https://api.example.test",
                http_client=client,
            ),
        )
        result = await executor.execute_call(call)

    assert seen["fields"] == "material_id,elastic_modulus"
    assert result.data == {
        "material_id": "mp-149",
        "elastic_modulus": 130.0,
    }


@pytest.mark.asyncio
async def test_server_projection_uses_declared_wire_field_mapping() -> None:
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["select"] = request.url.params.get("select")
        return httpx.Response(
            200,
            json={"elastic_modulus": 130.0},
            request=request,
        )

    endpoint = EndpointSpec(
        name="search",
        method="GET",
        path="/materials",
        read_only=True,
        output_fields=[
            FieldSpec(name="elastic_modulus", aliases=["탄성계수"]),
        ],
        output_schema={
            "type": "object",
            "properties": {"elastic_modulus": {"type": "number"}},
        },
        server_projection=ServerProjectionSpec(
            parameter="select",
            field_map={"elastic_modulus": "elasticity.bulk_modulus"},
        ),
    )
    tool = ToolSpec(name="materials", endpoints=[endpoint])
    call = ToolCall(
        tool="materials",
        endpoint="search",
        fields=["elastic_modulus"],
        schema_fingerprint=endpoint.fingerprint,
        tool_fingerprint=tool.fingerprint,
    )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        invoker = OpenAPIRemoteInvoker(
            tool,
            "https://api.example.test",
            http_client=client,
        )
        raw = await invoker.invoke_call(call)

    assert seen["select"] == "elasticity.bulk_modulus"
    assert raw == {"elastic_modulus": 130.0}


@pytest.mark.asyncio
async def test_openapi_without_projection_contract_does_not_guess_field_parameter() -> None:
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["query"] = dict(request.url.params)
        return httpx.Response(
            200,
            json={
                "elastic_modulus": 130.0,
                "density": 2.33,
            },
            request=request,
        )

    endpoint = EndpointSpec(
        name="search",
        method="GET",
        path="/materials",
        read_only=True,
        output_fields=[
            FieldSpec(name="elastic_modulus"),
            FieldSpec(name="density"),
        ],
        output_schema={
            "type": "object",
            "properties": {
                "elastic_modulus": {"type": "number"},
                "density": {"type": "number"},
            },
        },
    )
    tool = ToolSpec(name="materials", endpoints=[endpoint])
    registry = InMemoryRegistry()
    registry.register(tool)
    call = ToolCall(
        tool="materials",
        endpoint="search",
        fields=["elastic_modulus"],
        schema_fingerprint=endpoint.fingerprint,
        tool_fingerprint=tool.fingerprint,
    )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        executor = RegistryExecutor(registry)
        executor.bind(
            "materials",
            OpenAPIRemoteInvoker(
                tool,
                "https://api.example.test",
                http_client=client,
            ),
        )
        result = await executor.execute_call(call)

    assert seen["query"] == {}
    assert result.data == {"elastic_modulus": 130.0}


def test_server_projection_contract_is_part_of_endpoint_fingerprint() -> None:
    base = EndpointSpec(
        name="search",
        read_only=True,
        output_fields=[FieldSpec(name="elastic_modulus")],
    )
    projected = base.model_copy(
        update={
            "server_projection": ServerProjectionSpec(parameter="fields"),
        },
        deep=True,
    )

    assert base.fingerprint != projected.fingerprint



@pytest.mark.asyncio
async def test_server_projected_response_must_include_every_selected_field() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"material_id": "mp-149"},
            request=request,
        )

    endpoint = EndpointSpec(
        name="search",
        method="GET",
        path="/materials",
        read_only=True,
        output_fields=[
            FieldSpec(name="material_id", identifier=True),
            FieldSpec(name="elastic_modulus"),
        ],
        output_schema={
            "type": "object",
            "properties": {
                "material_id": {"type": "string"},
                "elastic_modulus": {"type": "number"},
            },
            "required": ["material_id", "elastic_modulus"],
        },
        server_projection=ServerProjectionSpec(parameter="fields"),
    )
    tool = ToolSpec(name="materials", endpoints=[endpoint])
    registry = InMemoryRegistry()
    registry.register(tool)
    call = ToolCall(
        tool="materials",
        endpoint="search",
        fields=["material_id", "elastic_modulus"],
        schema_fingerprint=endpoint.fingerprint,
        tool_fingerprint=tool.fingerprint,
    )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        executor = RegistryExecutor(registry)
        executor.bind(
            "materials",
            OpenAPIRemoteInvoker(
                tool,
                "https://api.example.test",
                http_client=client,
            ),
        )
        with pytest.raises(Exception, match="projected field 'elastic_modulus' is missing"):
            await executor.execute_call(call)
