import httpx
import pytest

from schemarouter import (
    EndpointSpec,
    FieldSpec,
    InMemoryRegistry,
    ParameterSpec,
    RegistryExecutor,
    SchemaValidationError,
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
        with pytest.raises(
            SchemaValidationError,
            match="elastic_modulus",
        ):
            await executor.execute_call(call)



def test_server_projection_rejects_unknown_logical_field_mapping() -> None:
    with pytest.raises(ValueError, match="undeclared output fields"):
        EndpointSpec(
            name="search",
            read_only=True,
            output_fields=[FieldSpec(name="elastic_modulus")],
            server_projection=ServerProjectionSpec(
                parameter="fields",
                field_map={"density": "raw_density"},
            ),
        )


def test_server_projection_rejects_non_query_parameter_collision() -> None:
    with pytest.raises(ValueError, match="non-query parameter"):
        EndpointSpec(
            name="search",
            read_only=True,
            parameters=[
                ParameterSpec(
                    name="fields",
                    location="body",
                )
            ],
            output_fields=[FieldSpec(name="elastic_modulus")],
            server_projection=ServerProjectionSpec(parameter="fields"),
        )


def test_server_projection_allows_declared_query_parameter_collision() -> None:
    endpoint = EndpointSpec(
        name="search",
        read_only=True,
        parameters=[
            ParameterSpec(
                name="fields",
                location="query",
            )
        ],
        output_fields=[FieldSpec(name="elastic_modulus")],
        server_projection=ServerProjectionSpec(parameter="fields"),
    )

    assert endpoint.server_projection is not None
    assert endpoint.server_projection.parameter == "fields"



@pytest.mark.asyncio
async def test_server_projection_normalizes_provider_wire_field_to_canonical_result() -> None:
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["response_fields"] = request.url.params.get("response_fields")
        return httpx.Response(
            200,
            json={
                "_provider_b_elasticity": 130.0,
                "density": 2.33,
            },
            request=request,
            headers={"content-type": "application/json"},
        )

    endpoint = EndpointSpec(
        name="search",
        method="GET",
        path="/materials",
        read_only=True,
        output_fields=[
            FieldSpec(
                name="elastic_modulus",
                semantic_id="elastic_modulus",
                aliases=["탄성계수", "elastic modulus"],
                path=["_provider_b_elasticity"],
                result_path=["elastic_modulus"],
                unit="GPa",
            ),
            FieldSpec(name="density"),
        ],
        output_schema={
            "type": "object",
            "properties": {
                "_provider_b_elasticity": {"type": "number"},
                "density": {"type": "number"},
            },
        },
        server_projection=ServerProjectionSpec(
            parameter="response_fields",
            field_map={
                "elastic_modulus": "_provider_b_elasticity",
            },
        ),
    )
    tool = ToolSpec(
        name="provider_b",
        provider="provider_b",
        access_mode="openapi",
        remote=True,
        execution_metadata={"adapter": "openapi"},
        endpoints=[endpoint],
    )
    registry = InMemoryRegistry()
    registry.register(tool)
    call = ToolCall(
        tool="provider_b",
        endpoint="search",
        fields=["elastic_modulus"],
        schema_fingerprint=endpoint.fingerprint,
        tool_fingerprint=tool.fingerprint,
    )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        executor = RegistryExecutor(registry)
        executor.bind(
            "provider_b",
            OpenAPIRemoteInvoker(
                tool,
                "https://provider-b.example",
                http_client=client,
            ),
        )
        result = await executor.execute_call(call)

    assert seen["response_fields"] == "_provider_b_elasticity"
    assert result.data == {"elastic_modulus": 130.0}


def test_field_result_path_defaults_to_existing_projection_shape() -> None:
    nested = FieldSpec(
        name="display_name",
        path=["user", "profile", "name"],
    )
    canonical = FieldSpec(
        name="elastic_modulus",
        path=["_provider_b_elasticity"],
        result_path=["elastic_modulus"],
    )

    assert nested.result_projection_path == ("user", "profile", "name")
    assert canonical.result_projection_path == ("elastic_modulus",)



def test_server_projection_remapped_source_requires_explicit_raw_output_schema() -> None:
    with pytest.raises(ValueError, match="requires an explicit output_schema"):
        EndpointSpec(
            name="search",
            read_only=True,
            output_fields=[
                FieldSpec(
                    name="elastic_modulus",
                    path=["_provider_b_elasticity"],
                    result_path=["elastic_modulus"],
                )
            ],
            server_projection=ServerProjectionSpec(
                parameter="response_fields",
                field_map={
                    "elastic_modulus": "_provider_b_elasticity",
                },
            ),
        )



@pytest.mark.asyncio
async def test_list_response_projection_removes_unselected_fields_from_every_item() -> None:
    endpoint = EndpointSpec(
        name="search",
        read_only=True,
        output_fields=[
            FieldSpec(name="elastic_modulus"),
            FieldSpec(name="density"),
        ],
        output_schema={
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "elastic_modulus": {"type": "number"},
                    "density": {"type": "number"},
                },
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
    executor = RegistryExecutor(registry)
    executor.bind(
        "materials",
        lambda endpoint_name, arguments: [
            {"elastic_modulus": 130.0, "density": 2.33},
            {"elastic_modulus": 75.0, "density": 8.96},
        ],
    )

    result = await executor.execute_call(call)

    assert result.data == [
        {"elastic_modulus": 130.0},
        {"elastic_modulus": 75.0},
    ]
