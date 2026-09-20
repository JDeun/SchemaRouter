import json

import httpx
import pytest

from schemarouter import PlanRequest, SchemaRouter, UnsupportedSchemaSourceError


def openapi_document() -> dict:
    return {
        "openapi": "3.1.0",
        "info": {"title": "Users API", "description": "User directory"},
        "servers": [{"url": "https://service.example.com/api/"}],
        "paths": {
            "/users/{user_id}": {
                "get": {
                    "operationId": "get_user",
                    "summary": "Get a user by id",
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
                                            "email": {"type": "string"},
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


@pytest.mark.asyncio
async def test_from_url_auto_ingests_openapi() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == httpx.URL("https://docs.example.com/openapi.json")
        return httpx.Response(
            200,
            content=json.dumps(openapi_document()),
            headers={"content-type": "application/json"},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        router = await SchemaRouter.from_url(
            "https://docs.example.com/openapi.json",
            http_client=client,
        )

    assert router.registry.keys() == ("users_api",)
    endpoint = router.registry.endpoint("users_api", "get_user")
    assert endpoint.method == "GET"
    assert endpoint.path == "/users/{user_id}"
    assert [field.name for field in endpoint.output_fields] == [
        "user_id",
        "name",
        "email",
    ]

    plan = router.plan(
        PlanRequest(
            query="get user name",
            arguments={"user_id": "42"},
        )
    )
    assert plan.executable
    assert plan.calls[0].endpoint == "get_user"
    assert plan.calls[0].arguments == {"user_id": "42"}
    assert "name" in plan.calls[0].fields


@pytest.mark.asyncio
async def test_openapi_yaml_url_is_supported() -> None:
    yaml_body = """
openapi: 3.1.0
info:
  title: Ping API
paths:
  /ping:
    get:
      operationId: ping
      responses:
        "200":
          content:
            application/json:
              schema:
                type: object
                properties:
                  status:
                    type: string
"""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=yaml_body, headers={"content-type": "application/yaml"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        router = SchemaRouter(http_client=client)
        tool = await router.add_url(
            "https://docs.example.com/openapi.yaml",
            kind="openapi",
        )

    assert tool.key == "ping_api"
    assert tool.endpoints[0].name == "ping"
    assert tool.endpoints[0].output_fields[0].name == "status"


@pytest.mark.asyncio
async def test_html_is_not_silently_inferred_as_openapi() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            text="<html><body>API documentation</body></html>",
            headers={"content-type": "text/html"},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        router = SchemaRouter(http_client=client)
        with pytest.raises(UnsupportedSchemaSourceError):
            await router.add_url(
                "https://docs.example.com/api",
                kind="openapi",
            )
