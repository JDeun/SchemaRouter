import json

import httpx
import pytest

from schemarouter import ModelQueryAnalyzer, PlanRequest, SchemaRouter, SchemaValidationError
from schemarouter.adapters.openapi import OpenAPIRemoteInvoker, tool_from_openapi
from schemarouter.validation import validate_json_schema_value


def document_with_body(schema: dict, *, required: bool = True) -> dict:
    return {
        "openapi": "3.1.0",
        "info": {"title": "Root Body API"},
        "paths": {
            "/submit": {
                "post": {
                    "operationId": "submit",
                    "requestBody": {
                        "required": required,
                        "content": {
                            "application/json": {
                                "schema": schema,
                            }
                        },
                    },
                    "responses": {
                        "200": {
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {"ok": {"type": "boolean"}},
                                        "required": ["ok"],
                                    }
                                }
                            }
                        }
                    },
                }
            }
        },
    }


def test_array_json_body_becomes_typed_root_parameter() -> None:
    document = document_with_body(
        {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 1,
        }
    )

    endpoint = tool_from_openapi("root", document).endpoint("submit")

    assert len(endpoint.parameters) == 1
    body = endpoint.parameters[0]
    assert body.name == "body"
    assert body.location == "body_root"
    assert body.required is True
    assert body.json_schema["type"] == "array"
    assert endpoint.metadata["request_body_mode"] == "root_schema"
    assert endpoint.input_schema["required"] == ["body"]


def test_scalar_json_body_becomes_typed_root_parameter() -> None:
    endpoint = tool_from_openapi(
        "root",
        document_with_body({"type": "string", "minLength": 1}),
    ).endpoint("submit")

    body = endpoint.parameters[0]
    assert body.name == "body"
    assert body.location == "body_root"
    assert body.json_schema == {"type": "string", "minLength": 1}


def test_non_discriminated_oneof_body_is_preserved_as_one_root_parameter() -> None:
    schema = {
        "oneOf": [
            {
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "required": ["name"],
                "additionalProperties": False,
            },
            {
                "type": "array",
                "items": {"type": "integer"},
                "minItems": 1,
            },
        ]
    }
    endpoint = tool_from_openapi("root", document_with_body(schema)).endpoint("submit")

    assert len(endpoint.parameters) == 1
    assert endpoint.parameters[0].name == "body"
    assert endpoint.parameters[0].location == "body_root"
    assert endpoint.parameters[0].json_schema == schema
    assert endpoint.metadata["request_body_mode"] == "root_schema"


def test_generic_root_body_remains_schema_validated_locally() -> None:
    endpoint = tool_from_openapi(
        "root",
        document_with_body(
            {
                "type": "array",
                "items": {"type": "integer"},
                "minItems": 2,
            }
        ),
    ).endpoint("submit")

    validate_json_schema_value(
        {"body": [1, 2]},
        endpoint.input_schema,
        context="valid root body",
    )
    with pytest.raises(SchemaValidationError):
        validate_json_schema_value(
            {"body": [1]},
            endpoint.input_schema,
            context="invalid root body",
        )


@pytest.mark.asyncio
async def test_cloud_model_analyzer_can_supply_generic_root_body() -> None:
    captured: dict = {}

    async def model(payload: dict) -> dict:
        captured.update(payload)
        return {
            "preferred_tools": ["root"],
            "preferred_endpoints": ["root.submit"],
            "arguments": {"body": ["alpha", "beta"]},
            "fields": ["ok"],
            "concepts": [],
            "evidence": {},
        }

    router = SchemaRouter(analyzer=ModelQueryAnalyzer(model))
    router.add_tool(
        tool_from_openapi(
            "root",
            document_with_body(
                {
                    "type": "array",
                    "items": {"type": "string"},
                }
            ),
        )
    )

    plan = await router.aplan(PlanRequest(query="submit alpha and beta"))

    assert plan.executable
    assert plan.calls[0].arguments == {"body": ["alpha", "beta"]}
    catalog_body = captured["schema_catalog"][0]["endpoints"][0]["parameters"][0]
    assert catalog_body["location"] == "body_root"
    assert catalog_body["json_schema"]["type"] == "array"


@pytest.mark.asyncio
async def test_invoker_sends_array_root_without_body_wrapper() -> None:
    tool = tool_from_openapi(
        "root",
        document_with_body(
            {
                "type": "array",
                "items": {"type": "integer"},
            }
        ),
    )
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["json"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={"ok": True},
            headers={"content-type": "application/json"},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        invoker = OpenAPIRemoteInvoker(
            tool,
            "https://api.example.test",
            http_client=client,
        )
        result = await invoker("submit", {"body": [1, 2, 3]})

    assert seen["json"] == [1, 2, 3]
    assert result == {"ok": True}


def test_simple_object_body_keeps_existing_flattened_parameter_contract() -> None:
    endpoint = tool_from_openapi(
        "root",
        document_with_body(
            {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "count": {"type": "integer"},
                },
                "required": ["name"],
            }
        ),
    ).endpoint("submit")

    assert [parameter.name for parameter in endpoint.parameters] == ["name", "count"]
    assert all(parameter.location == "body" for parameter in endpoint.parameters)
    assert endpoint.metadata["request_body_mode"] == "flattened_object"


def test_schema_less_body_remains_unrepresented() -> None:
    endpoint = tool_from_openapi(
        "root",
        document_with_body({}),
    ).endpoint("submit")

    assert endpoint.parameters == []
    assert endpoint.metadata["request_body_mode"] is None
    assert endpoint.metadata["request_body_required"] is False


@pytest.mark.asyncio
async def test_invoker_preserves_json_null_root_body() -> None:
    tool = tool_from_openapi(
        "root",
        document_with_body({"type": ["null", "string"]}),
    )
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["content"] = request.content
        seen["content_type"] = request.headers.get("content-type")
        return httpx.Response(
            200,
            json={"ok": True},
            headers={"content-type": "application/json"},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        invoker = OpenAPIRemoteInvoker(
            tool,
            "https://api.example.test",
            http_client=client,
        )
        result = await invoker("submit", {"body": None})

    assert seen["content"] == b"null"
    assert seen["content_type"] == "application/json"
    assert result == {"ok": True}


@pytest.mark.asyncio
async def test_required_root_body_missing_fails_closed_even_for_direct_invoker() -> None:
    tool = tool_from_openapi(
        "root",
        document_with_body(
            {
                "type": "array",
                "items": {"type": "integer"},
            }
        ),
    )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: pytest.fail("network request must not be attempted")
        )
    ) as client:
        invoker = OpenAPIRemoteInvoker(
            tool,
            "https://api.example.test",
            http_client=client,
        )
        with pytest.raises(Exception, match="required root request body missing"):
            await invoker("submit", {})
