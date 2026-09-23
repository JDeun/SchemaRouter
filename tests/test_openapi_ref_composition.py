import json

import httpx
import pytest

from schemarouter import PlanRequest, SchemaRouter
from schemarouter.adapters.openapi import normalize_same_document_refs, tool_from_openapi


def test_allof_flattens_body_parameters_and_response_fields_for_planning() -> None:
    document = {
        "openapi": "3.1.0",
        "info": {"title": "Composed API"},
        "paths": {
            "/users": {
                "post": {
                    "operationId": "create_user",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "allOf": [
                                        {"$ref": "#/components/schemas/BaseUser"},
                                        {"$ref": "#/components/schemas/UserDetails"},
                                    ]
                                }
                            }
                        },
                    },
                    "responses": {
                        "200": {
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "allOf": [
                                            {"$ref": "#/components/schemas/BaseUser"},
                                            {"$ref": "#/components/schemas/UserDetails"},
                                        ]
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
                "BaseUser": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "name": {"type": "string"},
                    },
                    "required": ["name"],
                },
                "UserDetails": {
                    "type": "object",
                    "properties": {
                        "email": {"type": "string", "format": "email"},
                    },
                    "required": ["email"],
                },
            }
        },
    }

    tool = tool_from_openapi("composed", document)
    endpoint = tool.endpoint("create_user")

    assert [parameter.name for parameter in endpoint.parameters] == ["id", "name", "email"]
    required = {parameter.name for parameter in endpoint.parameters if parameter.required}
    assert required == {"name", "email"}
    assert [field.name for field in endpoint.output_fields] == ["id", "name", "email"]
    assert endpoint.output_schema["allOf"]


def test_local_ref_chains_and_path_item_refs_are_resolved() -> None:
    document = {
        "openapi": "3.1.0",
        "info": {"title": "PathRef API"},
        "paths": {
            "/users/{user_id}": {
                "$ref": "#/components/pathItems/UserPathAlias",
            }
        },
        "components": {
            "pathItems": {
                "UserPathAlias": {"$ref": "#/components/pathItems/UserPath"},
                "UserPath": {
                    "parameters": [
                        {"$ref": "#/components/parameters/UserIdAlias"},
                    ],
                    "get": {
                        "operationId": "get_user",
                        "responses": {
                            "200": {
                                "$ref": "#/components/responses/UserResponseAlias",
                            }
                        },
                    },
                },
            },
            "parameters": {
                "UserIdAlias": {"$ref": "#/components/parameters/UserId"},
                "UserId": {
                    "name": "user_id",
                    "in": "path",
                    "required": True,
                    "schema": {"type": "string"},
                },
            },
            "responses": {
                "UserResponseAlias": {"$ref": "#/components/responses/UserResponse"},
                "UserResponse": {
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/UserAlias"},
                        }
                    }
                },
            },
            "schemas": {
                "UserAlias": {"$ref": "#/components/schemas/User"},
                "User": {
                    "type": "object",
                    "properties": {
                        "user_id": {"type": "string"},
                        "name": {"type": "string"},
                    },
                    "required": ["user_id", "name"],
                },
            },
        },
    }

    tool = tool_from_openapi("pathref", document)
    endpoint = tool.endpoint("get_user")

    assert [parameter.name for parameter in endpoint.parameters] == ["user_id"]
    assert [field.name for field in endpoint.output_fields] == ["user_id", "name"]
    assert tool.metadata["compatibility"]["operations_total"] == 1
    assert tool.metadata["compatibility"]["operations_importable"] == 1


def test_recursive_allof_reference_is_bounded_during_planner_flattening() -> None:
    document = {
        "openapi": "3.1.0",
        "info": {"title": "Recursive API"},
        "paths": {
            "/node": {
                "get": {
                    "operationId": "get_node",
                    "responses": {
                        "200": {
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/Node"}
                                }
                            }
                        }
                    },
                }
            }
        },
        "components": {
            "schemas": {
                "Node": {
                    "type": "object",
                    "properties": {"id": {"type": "string"}},
                    "allOf": [{"$ref": "#/components/schemas/Node"}],
                }
            }
        },
    }

    endpoint = tool_from_openapi("recursive", document).endpoint("get_node")

    assert [field.name for field in endpoint.output_fields] == ["id"]


def test_same_document_uri_refs_are_normalized_without_fetching_other_documents() -> None:
    document = {
        "openapi": "3.1.0",
        "info": {"title": "Refs"},
        "paths": {},
        "components": {
            "schemas": {
                "Local": {
                    "$ref": "./openapi.json#/components/schemas/User",
                },
                "External": {
                    "$ref": "./shared.json#/components/schemas/User",
                },
                "AbsoluteLocal": {
                    "$ref": "https://docs.example.com/spec/openapi.json#/components/schemas/User",
                },
            }
        },
    }

    normalized, count = normalize_same_document_refs(
        document,
        "https://docs.example.com/spec/openapi.json",
    )

    assert count == 2
    assert normalized["components"]["schemas"]["Local"]["$ref"] == "#/components/schemas/User"
    assert (
        normalized["components"]["schemas"]["AbsoluteLocal"]["$ref"]
        == "#/components/schemas/User"
    )
    assert (
        normalized["components"]["schemas"]["External"]["$ref"]
        == "./shared.json#/components/schemas/User"
    )


@pytest.mark.asyncio
async def test_url_ingestion_normalizes_same_document_refs_before_compatibility_analysis() -> None:
    document = {
        "openapi": "3.1.0",
        "info": {"title": "Same Document Refs"},
        "paths": {
            "/user": {
                "get": {
                    "operationId": "get_user",
                    "responses": {
                        "200": {
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "$ref": "./openapi.json#/components/schemas/User"
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
                "User": {
                    "type": "object",
                    "properties": {"name": {"type": "string"}},
                }
            }
        },
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == httpx.URL("https://docs.example.com/spec/openapi.json")
        return httpx.Response(
            200,
            content=json.dumps(document),
            headers={"content-type": "application/json"},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        router = await SchemaRouter.from_url(
            "https://docs.example.com/spec/openapi.json",
            kind="openapi",
            http_client=client,
        )

    tool = router.registry.get("same_document_refs")
    endpoint = tool.endpoint("get_user")

    assert tool.metadata["same_document_refs_normalized"] == 1
    assert endpoint.output_schema["type"] == "object"
    assert [field.name for field in endpoint.output_fields] == ["name"]
    issues = tool.metadata["compatibility"]["issues"]
    assert not any(issue["construct"] == "external_ref" for issue in issues)


def test_oneof_response_fields_are_exposed_without_flattening_runtime_schema() -> None:
    document = {
        "openapi": "3.1.0",
        "info": {"title": "Variant API"},
        "paths": {
            "/pet": {
                "get": {
                    "operationId": "get_pet",
                    "responses": {
                        "200": {
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "oneOf": [
                                            {
                                                "type": "object",
                                                "properties": {
                                                    "kind": {"const": "cat"},
                                                    "lives": {"type": "integer"},
                                                },
                                                "required": ["kind", "lives"],
                                            },
                                            {
                                                "type": "object",
                                                "properties": {
                                                    "kind": {"const": "dog"},
                                                    "breed": {"type": "string"},
                                                },
                                                "required": ["kind", "breed"],
                                            },
                                        ]
                                    }
                                }
                            }
                        }
                    },
                }
            }
        },
    }

    endpoint = tool_from_openapi("variant", document).endpoint("get_pet")
    fields = {field.name: field for field in endpoint.output_fields}

    assert list(fields) == ["kind", "lives", "breed"]
    assert fields["kind"].json_schema == {
        "anyOf": [{"const": "cat"}, {"const": "dog"}]
    }
    assert endpoint.output_schema["oneOf"]


def test_anyof_response_variant_local_refs_expose_union_of_fields() -> None:
    document = {
        "openapi": "3.1.0",
        "info": {"title": "Search API"},
        "paths": {
            "/result": {
                "get": {
                    "operationId": "get_result",
                    "responses": {
                        "200": {
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "anyOf": [
                                            {"$ref": "#/components/schemas/Success"},
                                            {"$ref": "#/components/schemas/Pending"},
                                        ]
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
                "Success": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "value": {"type": "number"},
                    },
                },
                "Pending": {
                    "allOf": [
                        {
                            "type": "object",
                            "properties": {
                                "id": {"type": "string"},
                            },
                        },
                        {
                            "type": "object",
                            "properties": {
                                "status": {"type": "string"},
                            },
                        },
                    ]
                },
            }
        },
    }

    endpoint = tool_from_openapi("search", document).endpoint("get_result")

    assert [field.name for field in endpoint.output_fields] == ["id", "value", "status"]
    assert endpoint.output_schema["anyOf"]


def test_oneof_response_conflicting_field_types_become_planner_anyof() -> None:
    document = {
        "openapi": "3.1.0",
        "info": {"title": "Conflict API"},
        "paths": {
            "/value": {
                "get": {
                    "operationId": "get_value",
                    "responses": {
                        "200": {
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "oneOf": [
                                            {
                                                "type": "object",
                                                "properties": {
                                                    "value": {"type": "string"}
                                                },
                                            },
                                            {
                                                "type": "object",
                                                "properties": {
                                                    "value": {"type": "integer"}
                                                },
                                            },
                                        ]
                                    }
                                }
                            }
                        }
                    },
                }
            }
        },
    }

    endpoint = tool_from_openapi("conflict", document).endpoint("get_value")

    assert endpoint.output_fields[0].name == "value"
    assert endpoint.output_fields[0].json_schema == {
        "anyOf": [{"type": "string"}, {"type": "integer"}]
    }


def test_oneof_request_body_remains_unflattened_and_non_executable_as_named_fields() -> None:
    document = {
        "openapi": "3.1.0",
        "info": {"title": "Variant Request API"},
        "paths": {
            "/pet": {
                "post": {
                    "operationId": "create_pet",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "oneOf": [
                                        {
                                            "type": "object",
                                            "properties": {
                                                "cat_name": {"type": "string"}
                                            },
                                            "required": ["cat_name"],
                                        },
                                        {
                                            "type": "object",
                                            "properties": {
                                                "dog_name": {"type": "string"}
                                            },
                                            "required": ["dog_name"],
                                        },
                                    ]
                                }
                            }
                        },
                    },
                    "responses": {"204": {"description": "created"}},
                }
            }
        },
    }

    endpoint = tool_from_openapi("variant_request", document).endpoint("create_pet")

    assert endpoint.parameters == []
    assert endpoint.metadata["request_body_required"] is False
    assert endpoint.input_schema["properties"] == {}


def test_planner_can_select_field_unique_to_oneof_response_variant() -> None:
    document = {
        "openapi": "3.1.0",
        "info": {"title": "Planner Variant API"},
        "paths": {
            "/pet": {
                "get": {
                    "operationId": "get_pet",
                    "responses": {
                        "200": {
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "oneOf": [
                                            {
                                                "type": "object",
                                                "properties": {
                                                    "cat_name": {"type": "string"},
                                                    "lives": {"type": "integer"},
                                                },
                                            },
                                            {
                                                "type": "object",
                                                "properties": {
                                                    "dog_name": {"type": "string"},
                                                    "breed": {
                                                        "type": "string",
                                                        "description": "Dog breed",
                                                    },
                                                },
                                            },
                                        ]
                                    }
                                }
                            }
                        }
                    },
                }
            }
        },
    }

    router = SchemaRouter()
    router.add_tool(tool_from_openapi("pets", document))

    plan = router.plan(
        PlanRequest(
            query="what breed is the dog",
            preferred_tools=["pets"],
        )
    )

    assert plan.calls[0].endpoint == "get_pet"
    assert plan.calls[0].fields == ["breed"]
