import gzip
import hashlib

import httpx
import pytest

from schemarouter import (
    EndpointSpec,
    ExecutionPlan,
    ExecutionPolicy,
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
                            "name": "Accept",
                            "in": "header",
                            "schema": {"type": "string"},
                        },
                        {
                            "name": "content-type",
                            "in": "header",
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

        tool_fingerprint=tool.fingerprint,
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


def test_openapi_multiple_success_responses_compile_union_schema_and_fields() -> None:
    document = {
        "openapi": "3.1.0",
        "info": {"title": "Multi Success API"},
        "paths": {
            "/items": {
                "post": {
                    "operationId": "create_item",
                    "responses": {
                        "200": {
                            "description": "existing",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "id": {"type": "string"},
                                            "name": {"type": "string"},
                                        },
                                        "required": ["id", "name"],
                                    }
                                }
                            },
                        },
                        "201": {
                            "description": "created",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "id": {"type": "string"},
                                            "created": {"type": "boolean"},
                                        },
                                        "required": ["id", "created"],
                                    }
                                }
                            },
                        },
                        "204": {"description": "accepted without payload"},
                    },
                }
            }
        },
    }

    endpoint = tool_from_openapi("multi_success", document).endpoint("create_item")

    assert "anyOf" in endpoint.output_schema
    assert len(endpoint.output_schema["anyOf"]) == 3
    assert {"type": "null"} in endpoint.output_schema["anyOf"]
    assert [field.name for field in endpoint.output_fields] == [
        "id",
        "name",
        "created",
    ]


@pytest.mark.asyncio
async def test_openapi_later_success_json_schema_validates_at_runtime() -> None:
    document = {
        "openapi": "3.1.0",
        "info": {"title": "Multi Success API"},
        "paths": {
            "/items": {
                "post": {
                    "operationId": "create_item",
                    "responses": {
                        "200": {
                            "description": "existing",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {"name": {"type": "string"}},
                                        "required": ["name"],
                                    }
                                }
                            },
                        },
                        "201": {
                            "description": "created",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {"created": {"type": "boolean"}},
                                        "required": ["created"],
                                    }
                                }
                            },
                        },
                    },
                }
            }
        },
    }
    tool = tool_from_openapi("multi_success", document)
    endpoint = tool.endpoint("create_item")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(201, json={"created": True}, request=request)

    registry = InMemoryRegistry()
    registry.register(tool)
    call = ToolCall(
        tool=tool.key,
        endpoint=endpoint.name,
        fields=["created"],
        schema_fingerprint=endpoint.fingerprint,

        tool_fingerprint=tool.fingerprint,
    )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        executor = RegistryExecutor(
            registry,
            policy=ExecutionPolicy(allow_mutations=True),
        )
        executor.bind(
            tool.key,
            OpenAPIRemoteInvoker(
                tool,
                "https://api.example.com",
                http_client=client,
            ),
        )
        result = await executor.execute_call(call)

    assert result.data == {"created": True}


@pytest.mark.asyncio
async def test_openapi_no_content_success_returns_none_and_validates() -> None:
    document = {
        "openapi": "3.1.0",
        "info": {"title": "No Content API"},
        "paths": {
            "/items/{item_id}": {
                "delete": {
                    "operationId": "delete_item",
                    "parameters": [
                        {
                            "name": "item_id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"},
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "deleted payload",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {"deleted": {"type": "boolean"}},
                                        "required": ["deleted"],
                                    }
                                }
                            },
                        },
                        "204": {"description": "deleted without payload"},
                    },
                }
            }
        },
    }
    tool = tool_from_openapi("no_content", document)
    endpoint = tool.endpoint("delete_item")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(204, request=request)

    registry = InMemoryRegistry()
    registry.register(tool)
    call = ToolCall(
        tool=tool.key,
        endpoint=endpoint.name,
        arguments={"item_id": "42"},
        fields=["deleted"],
        schema_fingerprint=endpoint.fingerprint,

        tool_fingerprint=tool.fingerprint,
    )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        executor = RegistryExecutor(
            registry,
            policy=ExecutionPolicy(
                allow_mutations=True,
                allow_destructive=True,
            ),
        )
        executor.bind(
            tool.key,
            OpenAPIRemoteInvoker(
                tool,
                "https://api.example.com",
                http_client=client,
            ),
        )
        result = await executor.execute_call(call)

    assert result.data is None


def test_openapi_generated_operation_names_disambiguate_path_collisions() -> None:
    document = {
        "openapi": "3.1.0",
        "info": {"title": "Fallback Collision API"},
        "paths": {
            "/a_b": {
                "get": {
                    "responses": {"204": {"description": "ok"}},
                }
            },
            "/a/b": {
                "get": {
                    "responses": {"204": {"description": "ok"}},
                }
            },
        },
    }

    tool = tool_from_openapi("fallbacks", document)

    assert len(tool.endpoints) == 2
    assert len({endpoint.name for endpoint in tool.endpoints}) == 2
    assert {endpoint.path for endpoint in tool.endpoints} == {"/a_b", "/a/b"}
    assert all(
        endpoint.metadata["operation_id_generated"] is True
        for endpoint in tool.endpoints
    )
    assert all(
        endpoint.metadata["generated_operation_id_disambiguated"] is True
        for endpoint in tool.endpoints
    )
    assert all(
        endpoint.metadata["generated_operation_id_base"] == "get_a_b"
        for endpoint in tool.endpoints
    )


def test_openapi_generated_operation_name_collision_resolution_is_bounded() -> None:
    digest = hashlib.sha256(b"GET /a/b").hexdigest()[:12]
    reserved_name = f"get_a_b__{digest}"
    document = {
        "openapi": "3.1.0",
        "info": {"title": "Reserved Fallback API"},
        "paths": {
            "/explicit-base": {
                "get": {
                    "operationId": "get_a_b",
                    "responses": {"204": {"description": "ok"}},
                }
            },
            "/explicit-hash": {
                "get": {
                    "operationId": reserved_name,
                    "responses": {"204": {"description": "ok"}},
                }
            },
            "/a/b": {
                "get": {
                    "responses": {"204": {"description": "ok"}},
                }
            },
        },
    }

    tool = tool_from_openapi("fallbacks", document)
    by_path = {endpoint.path: endpoint for endpoint in tool.endpoints}

    assert by_path["/explicit-base"].name == "get_a_b"
    assert by_path["/explicit-hash"].name == reserved_name
    assert by_path["/a/b"].name == f"{reserved_name}__2"


def test_openapi_generated_operation_name_never_rewrites_explicit_operation_id() -> None:
    document = {
        "openapi": "3.1.0",
        "info": {"title": "Explicit Collision API"},
        "paths": {
            "/explicit": {
                "get": {
                    "operationId": "get_a_b",
                    "responses": {"204": {"description": "ok"}},
                }
            },
            "/a/b": {
                "get": {
                    "responses": {"204": {"description": "ok"}},
                }
            },
        },
    }

    tool = tool_from_openapi("fallbacks", document)
    by_path = {endpoint.path: endpoint for endpoint in tool.endpoints}

    assert by_path["/explicit"].name == "get_a_b"
    assert by_path["/explicit"].metadata["operation_id_generated"] is False
    assert by_path["/a/b"].name.startswith("get_a_b__")
    assert by_path["/a/b"].metadata["generated_operation_id_base"] == "get_a_b"


def test_openapi_operation_parameters_override_path_parameters() -> None:
    document = {
        "openapi": "3.1.0",
        "info": {"title": "Override API"},
        "paths": {
            "/items": {
                "parameters": [
                    {
                        "name": "limit",
                        "in": "query",
                        "required": False,
                        "description": "path-level",
                        "schema": {"type": "integer", "maximum": 100},
                    }
                ],
                "get": {
                    "operationId": "list_items",
                    "parameters": [
                        {
                            "name": "limit",
                            "in": "query",
                            "required": True,
                            "description": "operation-level",
                            "schema": {"type": "integer", "maximum": 10},
                        }
                    ],
                    "responses": {"204": {"description": "ok"}},
                },
            }
        },
    }

    endpoint = tool_from_openapi("override", document).endpoint("list_items")

    assert len(endpoint.parameters) == 1
    parameter = endpoint.parameters[0]
    assert parameter.name == "limit"
    assert parameter.description == "operation-level"
    assert parameter.required is True
    assert parameter.json_schema["maximum"] == 10
    assert endpoint.input_schema["required"] == ["limit"]
    assert endpoint.input_schema["properties"]["limit"]["maximum"] == 10


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

@pytest.mark.asyncio
async def test_openapi_required_object_body_is_sent_even_when_empty() -> None:
    document = {
        "openapi": "3.1.0",
        "info": {"title": "Required Body API"},
        "paths": {
            "/items": {
                "post": {
                    "operationId": "create_item",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "note": {"type": "string"},
                                    },
                                }
                            }
                        },
                    },
                    "responses": {"204": {"description": "created"}},
                }
            }
        },
    }
    tool = tool_from_openapi("required_body", document)
    endpoint = tool.endpoint("create_item")
    assert endpoint.metadata["request_body_required"] is True
    assert endpoint.parameters[0].name == "note"
    assert endpoint.parameters[0].required is False

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.content == b"{}"
        assert request.headers["content-type"].startswith("application/json")
        return httpx.Response(204, request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        invoker = OpenAPIRemoteInvoker(
            tool,
            "https://api.example.com",
            http_client=client,
        )
        await invoker("create_item", {})


@pytest.mark.asyncio
async def test_openapi_optional_empty_object_body_remains_omitted() -> None:
    document = {
        "openapi": "3.1.0",
        "info": {"title": "Optional Body API"},
        "paths": {
            "/items": {
                "post": {
                    "operationId": "create_item",
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "note": {"type": "string"},
                                    },
                                }
                            }
                        },
                    },
                    "responses": {"204": {"description": "created"}},
                }
            }
        },
    }
    tool = tool_from_openapi("optional_body", document)
    endpoint = tool.endpoint("create_item")
    assert endpoint.metadata["request_body_required"] is False

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.content == b""
        assert "content-type" not in request.headers
        return httpx.Response(204, request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        invoker = OpenAPIRemoteInvoker(
            tool,
            "https://api.example.com",
            http_client=client,
        )
        await invoker("create_item", {})


@pytest.mark.asyncio
async def test_openapi_required_schema_less_body_is_not_fabricated() -> None:
    document = {
        "openapi": "3.1.0",
        "info": {"title": "Schema-less Body API"},
        "paths": {
            "/items": {
                "post": {
                    "operationId": "create_item",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {},
                        },
                    },
                    "responses": {"204": {"description": "created"}},
                }
            }
        },
    }

    tool = tool_from_openapi("schema_less_body", document)
    endpoint = tool.endpoint("create_item")

    assert endpoint.metadata["request_body_required"] is False
    assert endpoint.metadata["request_body_mode"] is None
    assert endpoint.parameters == []
    assert any(
        issue["construct"] == "schema_less_request_body"
        for issue in tool.metadata["compatibility"]["issues"]
    )

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.content == b""
        assert "content-type" not in request.headers
        return httpx.Response(204, request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        invoker = OpenAPIRemoteInvoker(
            tool,
            "https://api.example.com",
            http_client=client,
        )
        await invoker("create_item", {})


def test_openapi_required_array_body_is_exposed_as_typed_root() -> None:
    document = {
        "openapi": "3.1.0",
        "info": {"title": "Array Body API"},
        "paths": {
            "/items": {
                "post": {
                    "operationId": "create_items",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                }
                            }
                        },
                    },
                    "responses": {"204": {"description": "created"}},
                }
            }
        },
    }

    endpoint = tool_from_openapi("array_body", document).endpoint("create_items")

    assert endpoint.metadata["request_body_required"] is True
    assert endpoint.metadata["request_body_mode"] == "root_schema"
    assert len(endpoint.parameters) == 1
    assert endpoint.parameters[0].name == "body"
    assert endpoint.parameters[0].location == "body_root"
    assert endpoint.parameters[0].json_schema["type"] == "array"


class ChunkedBody(httpx.AsyncByteStream):
    def __init__(self, *chunks: bytes) -> None:
        self.chunks = chunks

    async def __aiter__(self):
        for chunk in self.chunks:
            yield chunk


@pytest.mark.asyncio
async def test_openapi_invoker_rejects_oversized_declared_response() -> None:
    tool = ToolSpec(
        name="manual",
        endpoints=[
            EndpointSpec(
                name="read",
                method="GET",
                path="/read",
            )
        ],
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={
                "content-type": "application/json",
                "content-length": "1024",
            },
            content=b"{}",
            request=request,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        invoker = OpenAPIRemoteInvoker(
            tool,
            "https://api.example.com",
            max_response_bytes=16,
            http_client=client,
        )
        with pytest.raises(RuntimeError, match="exceeds 16 byte safety limit"):
            await invoker("read", {})


@pytest.mark.asyncio
async def test_openapi_invoker_rejects_streamed_response_over_limit() -> None:
    tool = ToolSpec(
        name="manual",
        endpoints=[
            EndpointSpec(
                name="read",
                method="GET",
                path="/read",
            )
        ],
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": "text/plain"},
            stream=ChunkedBody(b"12345678", b"9"),
            request=request,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        invoker = OpenAPIRemoteInvoker(
            tool,
            "https://api.example.com",
            max_response_bytes=8,
            http_client=client,
        )
        with pytest.raises(RuntimeError, match="exceeds 8 byte safety limit"):
            await invoker("read", {})


@pytest.mark.asyncio
async def test_openapi_invoker_decodes_bounded_json_response() -> None:
    tool = ToolSpec(
        name="manual",
        endpoints=[
            EndpointSpec(
                name="read",
                method="GET",
                path="/read",
            )
        ],
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": "application/json"},
            json={"ok": True},
            request=request,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        invoker = OpenAPIRemoteInvoker(
            tool,
            "https://api.example.com",
            max_response_bytes=1024,
            http_client=client,
        )
        assert await invoker("read", {}) == {"ok": True}


@pytest.mark.parametrize("max_response_bytes", [0, -1, True, 1.5])
def test_openapi_invoker_rejects_invalid_response_limit(max_response_bytes: object) -> None:
    tool = ToolSpec(
        name="manual",
        endpoints=[EndpointSpec(name="read", method="GET", path="/read")],
    )
    with pytest.raises(ValueError, match="max_response_bytes"):
        OpenAPIRemoteInvoker(
            tool,
            "https://api.example.com",
            max_response_bytes=max_response_bytes,  # type: ignore[arg-type]
        )

@pytest.mark.asyncio
async def test_openapi_invoker_handles_compressed_json_without_double_decoding() -> None:
    tool = ToolSpec(
        name="manual",
        endpoints=[EndpointSpec(name="read", method="GET", path="/read")],
    )
    compressed = gzip.compress(b'{"ok": true}')

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={
                "content-type": "application/json",
                "content-encoding": "gzip",
            },
            content=compressed,
            request=request,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        invoker = OpenAPIRemoteInvoker(
            tool,
            "https://api.example.com",
            max_response_bytes=1024,
            http_client=client,
        )
        assert await invoker("read", {}) == {"ok": True}




def test_openapi_adapter_preserves_field_type_and_unit_annotations() -> None:
    document = {
        "openapi": "3.1.0",
        "info": {"title": "Materials"},
        "paths": {
            "/materials": {
                "get": {
                    "operationId": "get_material",
                    "responses": {
                        "200": {
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "abstract": {
                                                "type": "string",
                                            },
                                            "elastic_modulus": {
                                                "type": "number",
                                                "x-ucum-unit": "GPa",
                                            },
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

    endpoint = tool_from_openapi("materials", document).endpoint("get_material")
    fields = {field.name: field for field in endpoint.output_fields}

    assert fields["abstract"].declared_json_types == ("string",)
    assert fields["abstract"].unit is None
    assert fields["elastic_modulus"].declared_json_types == ("number",)
    assert fields["elastic_modulus"].unit == "GPa"


def test_mcp_adapter_preserves_field_type_and_unit_annotations() -> None:
    tool = tool_from_mcp(
        "materials",
        {
            "tools": [
                {
                    "name": "read",
                    "inputSchema": {
                        "type": "object",
                        "properties": {},
                    },
                    "outputSchema": {
                        "type": "object",
                        "properties": {
                            "summary": {
                                "type": "string",
                            },
                            "particle_size": {
                                "type": "number",
                                "x-unit": "nm",
                            },
                        },
                    },
                    "annotations": {"readOnlyHint": True},
                }
            ]
        },
    )

    endpoint = tool.endpoint("read")
    fields = {field.name: field for field in endpoint.output_fields}

    assert fields["summary"].declared_json_types == ("string",)
    assert fields["summary"].unit is None
    assert fields["particle_size"].declared_json_types == ("number",)
    assert fields["particle_size"].unit == "nm"
