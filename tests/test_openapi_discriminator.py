import json

import httpx
import pytest

from schemarouter import (
    InMemoryRegistry,
    ModelQueryAnalyzer,
    PlanRequest,
    RegistryExecutor,
    SchemaRouter,
    SchemaValidationError,
    ToolCall,
)
from schemarouter.adapters.openapi import OpenAPIRemoteInvoker, tool_from_openapi
from schemarouter.validation import validate_json_schema_value


def discriminated_document() -> dict:
    return {
        "openapi": "3.1.0",
        "info": {"title": "Pet API"},
        "paths": {
            "/pets": {
                "post": {
                    "operationId": "create_pet",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "oneOf": [
                                        {"$ref": "#/components/schemas/Cat"},
                                        {"$ref": "#/components/schemas/Dog"},
                                    ],
                                    "discriminator": {"propertyName": "kind"},
                                }
                            }
                        },
                    },
                    "responses": {
                        "200": {
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {"id": {"type": "string"}},
                                        "required": ["id"],
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
                "Cat": {
                    "type": "object",
                    "properties": {
                        "kind": {"const": "cat"},
                        "name": {"type": "string"},
                        "lives": {"type": "integer"},
                    },
                    "required": ["kind", "name", "lives"],
                },
                "Dog": {
                    "type": "object",
                    "properties": {
                        "kind": {"enum": ["dog"]},
                        "name": {"type": "string"},
                        "breed": {"type": "string"},
                    },
                    "required": ["kind", "name", "breed"],
                },
            }
        },
    }


def test_discriminated_oneof_request_body_becomes_typed_root_parameter() -> None:
    endpoint = tool_from_openapi("pets", discriminated_document()).endpoint("create_pet")

    assert len(endpoint.parameters) == 1
    body = endpoint.parameters[0]
    assert body.name == "body"
    assert body.location == "body_root"
    assert body.required is True
    assert body.json_schema["discriminator"] == {"propertyName": "kind"}
    assert len(body.json_schema["oneOf"]) == 2

    assert endpoint.metadata["request_body_mode"] == "discriminated_root"
    assert endpoint.metadata["request_body_discriminator"] == "kind"
    assert endpoint.metadata["request_body_required"] is True
    assert endpoint.input_schema["required"] == ["body"]


def test_discriminated_body_schema_rejects_wrong_variant_locally() -> None:
    endpoint = tool_from_openapi("pets", discriminated_document()).endpoint("create_pet")

    validate_json_schema_value(
        {
            "body": {
                "kind": "dog",
                "name": "Mong",
                "breed": "retriever",
            }
        },
        endpoint.input_schema,
        context="valid body",
    )

    with pytest.raises(SchemaValidationError):
        validate_json_schema_value(
            {
                "body": {
                    "kind": "dog",
                    "name": "Mong",
                    "lives": 9,
                }
            },
            endpoint.input_schema,
            context="invalid body",
        )


def test_executor_rejects_invalid_discriminated_body_before_invocation() -> None:
    tool = tool_from_openapi("pets", discriminated_document())
    endpoint = tool.endpoint("create_pet")
    registry = InMemoryRegistry()
    registry.register(tool)
    executor = RegistryExecutor(registry)

    call = ToolCall(
        tool="pets",
        endpoint="create_pet",
        arguments={
            "body": {
                "kind": "dog",
                "name": "Mong",
                "lives": 9,
            }
        },
        fields=["id"],
        schema_fingerprint=endpoint.fingerprint,
    )

    with pytest.raises(SchemaValidationError):
        executor.validate_call(call)


@pytest.mark.asyncio
async def test_model_analyzer_can_supply_discriminated_cloud_model_body() -> None:
    captured: dict = {}

    async def cloud_model(payload: dict) -> dict:
        captured.update(payload)
        return {
            "preferred_tools": ["pets"],
            "preferred_endpoints": ["pets.create_pet"],
            "arguments": {
                "body": {
                    "kind": "dog",
                    "name": "Mong",
                    "breed": "retriever",
                }
            },
            "fields": ["id"],
            "concepts": ["create dog"],
            "evidence": {},
        }

    router = SchemaRouter(analyzer=ModelQueryAnalyzer(cloud_model))
    router.add_tool(tool_from_openapi("pets", discriminated_document()))

    plan = await router.aplan(PlanRequest(query="create a retriever named Mong"))

    assert plan.executable
    assert plan.calls[0].arguments == {
        "body": {
            "kind": "dog",
            "name": "Mong",
            "breed": "retriever",
        }
    }
    catalog_body = captured["schema_catalog"][0]["endpoints"][0]["parameters"][0]
    assert catalog_body["name"] == "body"
    assert catalog_body["location"] == "body_root"
    assert catalog_body["json_schema"]["discriminator"]["propertyName"] == "kind"


@pytest.mark.asyncio
async def test_openapi_invoker_sends_discriminated_body_as_json_root() -> None:
    tool = tool_from_openapi("pets", discriminated_document())
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["json"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={"id": "pet-1"},
            headers={"content-type": "application/json"},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        invoker = OpenAPIRemoteInvoker(
            tool,
            "https://api.example.test",
            http_client=client,
        )
        result = await invoker(
            "create_pet",
            {
                "body": {
                    "kind": "dog",
                    "name": "Mong",
                    "breed": "retriever",
                }
            },
        )

    assert seen["json"] == {
        "kind": "dog",
        "name": "Mong",
        "breed": "retriever",
    }
    assert result == {"id": "pet-1"}


def test_non_discriminated_oneof_request_body_falls_back_to_generic_root() -> None:
    document = discriminated_document()
    del document["paths"]["/pets"]["post"]["requestBody"]["content"]["application/json"]["schema"][
        "discriminator"
    ]

    endpoint = tool_from_openapi("pets", document).endpoint("create_pet")

    assert len(endpoint.parameters) == 1
    assert endpoint.parameters[0].name == "body"
    assert endpoint.parameters[0].location == "body_root"
    assert endpoint.metadata["request_body_mode"] == "root_schema"
    assert endpoint.metadata["request_body_required"] is True
    assert endpoint.metadata["request_body_discriminator"] is None


def test_unsafe_discriminator_falls_back_without_trusting_discriminator() -> None:
    document = discriminated_document()
    dog = document["components"]["schemas"]["Dog"]
    dog["required"] = ["name", "breed"]

    endpoint = tool_from_openapi("pets", document).endpoint("create_pet")

    assert len(endpoint.parameters) == 1
    assert endpoint.parameters[0].location == "body_root"
    assert endpoint.metadata["request_body_mode"] == "root_schema"
    assert endpoint.metadata["request_body_discriminator"] is None
