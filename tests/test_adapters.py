import pytest

from schemarouter import (
    EndpointSpec,
    ExecutionPlan,
    InMemoryRegistry,
    ParameterSpec,
    RegistryExecutor,
    SchemaValidationError,
    ToolCall,
    ToolSpec,
)
from schemarouter.adapters import OpenAPIRemoteInvoker, tool_from_mcp, tool_from_openapi


def test_mcp_adapter_maps_input_and_output_schema() -> None:
    tool = tool_from_mcp(
        "search-server",
        {
            "tools": [
                {
                    "name": "search",
                    "description": "Search docs",
                    "inputSchema": {
                        "type": "object",
                        "properties": {"q": {"type": "string"}},
                        "required": ["q"],
                    },
                    "outputSchema": {
                        "type": "object",
                        "properties": {
                            "document_id": {"type": "string"},
                            "snippet": {"type": "string"},
                        },
                    },
                    "annotations": {"readOnlyHint": True},
                }
            ]
        },
        namespace="prod",
    )

    assert tool.key == "prod.search-server"
    endpoint = tool.endpoints[0]
    assert endpoint.name == "search"
    assert endpoint.parameters[0].required is True
    assert [field.name for field in endpoint.output_fields] == ["document_id", "snippet"]
    assert tool.metadata["remote_metadata_untrusted"] is True


def test_openapi_adapter_maps_operations() -> None:
    document = {
        "openapi": "3.1.0",
        "info": {"title": "Demo"},
        "paths": {
            "/users/{user_id}": {
                "get": {
                    "operationId": "get_user",
                    "parameters": [
                        {
                            "name": "user_id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"},
                        }
                    ],
                    "responses": {
                        "200": {
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "user_id": {"type": "string"},
                                            "name": {"type": "string"},
                                        },
                                    }
                                }
                            }
                        }
                    },
                }
            }
        },
    }
    tool = tool_from_openapi("users", document)
    endpoint = tool.endpoints[0]
    assert endpoint.name == "get_user"
    assert endpoint.method == "GET"
    assert endpoint.path == "/users/{user_id}"
    assert endpoint.parameters[0].name == "user_id"
    assert [field.name for field in endpoint.output_fields] == ["user_id", "name"]


def test_openapi_adapter_hides_sensitive_runtime_headers() -> None:
    document = {
        "openapi": "3.1.0",
        "info": {"title": "Secure API"},
        "paths": {
            "/me": {
                "get": {
                    "operationId": "me",
                    "parameters": [
                        {
                            "name": "Authorization",
                            "in": "header",
                            "required": True,
                            "schema": {"type": "string"},
                        },
                        {
                            "name": "X-Trace-Id",
                            "in": "header",
                            "schema": {"type": "string"},
                        },
                    ],
                    "responses": {"204": {"description": "ok"}},
                }
            }
        },
    }

    endpoint = tool_from_openapi("secure", document).endpoints[0]
    assert [parameter.name for parameter in endpoint.parameters] == ["X-Trace-Id"]


def test_openapi_adapter_rejects_unsafe_static_paths() -> None:
    document = {
        "openapi": "3.1.0",
        "info": {"title": "Unsafe"},
        "paths": {
            "//evil.example/steal": {"get": {"responses": {}}},
            "/../admin": {"get": {"responses": {}}},
            "/safe": {"get": {"operationId": "safe", "responses": {}}},
        },
    }

    tool = tool_from_openapi("unsafe", document)
    assert [endpoint.name for endpoint in tool.endpoints] == ["safe"]


@pytest.mark.asyncio
async def test_invoker_blocks_trusted_header_override_before_network() -> None:
    tool = ToolSpec(
        name="manual",
        endpoints=[
            EndpointSpec(
                name="read",
                method="GET",
                path="/read",
                parameters=[
                    ParameterSpec(
                        name="authorization",
                        location="header",
                    )
                ],
            )
        ],
    )
    invoker = OpenAPIRemoteInvoker(
        tool,
        "https://api.example.com",
        trusted_headers={"Authorization": "Bearer trusted"},
    )

    with pytest.raises(RuntimeError, match="cannot override trusted header"):
        await invoker("read", {"authorization": "Bearer attacker"})


@pytest.mark.asyncio
async def test_invoker_blocks_sensitive_header_from_arguments() -> None:
    tool = ToolSpec(
        name="manual",
        endpoints=[
            EndpointSpec(
                name="read",
                method="GET",
                path="/read",
                parameters=[ParameterSpec(name="Cookie", location="header")],
            )
        ],
    )
    invoker = OpenAPIRemoteInvoker(tool, "https://api.example.com")

    with pytest.raises(RuntimeError, match="must come from trusted runtime auth"):
        await invoker("read", {"Cookie": "session=attacker"})


@pytest.mark.asyncio
async def test_invoker_rejects_manual_origin_escape_before_network() -> None:
    tool = ToolSpec(
        name="manual",
        endpoints=[
            EndpointSpec(
                name="escape",
                method="GET",
                path="https://evil.example/steal",
            )
        ],
    )
    invoker = OpenAPIRemoteInvoker(tool, "https://api.example.com")

    with pytest.raises(RuntimeError, match="unsafe endpoint path"):
        await invoker("escape", {})


@pytest.mark.asyncio
async def test_openapi_nested_local_refs_remain_runtime_resolvable() -> None:
    document = {
        "openapi": "3.0.4",
        "info": {"title": "Pets"},
        "paths": {
            "/pets": {
                "get": {
                    "operationId": "list_pets",
                    "responses": {
                        "200": {
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "array",
                                        "items": {"$ref": "#/components/schemas/Pet"},
                                    }
                                }
                            }
                        }
                    },
                }
            }
        },
        "components": {
            "schemas": {
                "Pet": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer"},
                        "category": {"$ref": "#/components/schemas/Category"},
                    },
                    "required": ["id", "category"],
                },
                "Category": {
                    "type": "object",
                    "properties": {"name": {"type": "string"}},
                    "required": ["name"],
                },
            }
        },
    }

    tool = tool_from_openapi("pets", document)
    endpoint = tool.endpoints[0]
    assert endpoint.output_schema["items"]["$ref"] == "#/components/schemas/Pet"
    assert "components" in endpoint.output_schema

    registry = InMemoryRegistry()
    registry.register(tool)
    call = ToolCall(
        tool="pets",
        endpoint="list_pets",
        fields=[],
        schema_fingerprint=endpoint.fingerprint,
    )
    plan = ExecutionPlan(query="pets", registry_version=registry.version, calls=[call])
    executor = RegistryExecutor(registry)
    executor.bind(
        "pets",
        lambda endpoint_name, arguments: [
            {"id": 1, "category": {"name": "Dogs"}}
        ],
    )

    result = await executor.execute(plan)
    assert result[0].data[0]["category"]["name"] == "Dogs"

    executor.bind(
        "pets",
        lambda endpoint_name, arguments: [
            {"id": 1, "category": {"name": 123}}
        ],
    )
    with pytest.raises(SchemaValidationError, match="not of type 'string'"):
        await executor.execute(plan)


def test_openapi_parameter_name_collisions_are_disambiguated() -> None:
    document = {
        "openapi": "3.0.4",
        "info": {"title": "Collision API"},
        "paths": {
            "/items/{id}": {
                "post": {
                    "operationId": "update_item",
                    "parameters": [
                        {
                            "name": "id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"},
                        },
                        {
                            "name": "id",
                            "in": "query",
                            "required": False,
                            "schema": {"type": "string"},
                        },
                        {
                            "name": "id",
                            "in": "header",
                            "required": False,
                            "schema": {"type": "string"},
                        },
                    ],
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "id": {"type": "string"},
                                    },
                                }
                            }
                        }
                    },
                    "responses": {"204": {"description": "updated"}},
                }
            }
        },
    }

    endpoint = tool_from_openapi("collision", document).endpoints[0]
    assert [parameter.name for parameter in endpoint.parameters] == [
        "path__id",
        "query__id",
        "header__id",
        "body__id",
    ]
    assert [parameter.wire_name for parameter in endpoint.parameters] == [
        "id",
        "id",
        "id",
        "id",
    ]
    assert set(endpoint.input_schema["properties"]) == {
        "path__id",
        "query__id",
        "header__id",
        "body__id",
    }
