from schemarouter.adapters import tool_from_mcp, tool_from_openapi


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
