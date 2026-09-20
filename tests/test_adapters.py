import pytest

from schemarouter import EndpointSpec, ParameterSpec, ToolSpec
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
