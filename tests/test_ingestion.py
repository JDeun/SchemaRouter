import json

import httpx
import pytest

from schemarouter import (
    ExecutionError,
    PlanRequest,
    SchemaDriftError,
    SchemaRouter,
    SchemaSourceError,
    UnsupportedSchemaSourceError,
)


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
async def test_cross_origin_openapi_is_ingested_but_not_auto_bound() -> None:
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
    tool = router.registry.get("users_api")
    assert tool.metadata["execution_bound"] is False
    assert tool.metadata["requires_explicit_base_url"] is True
    assert tool.metadata["suggested_base_url"] == "https://service.example.com/api/"

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
    assert "name" in plan.calls[0].fields
    with pytest.raises(ExecutionError, match="no invoker bound"):
        await router.execute(plan)

    router.bind_openapi(
        "users_api",
        base_url="https://service.example.com/api/",
    )
    assert tool.metadata["execution_bound"] is False
    rebound = router.registry.get("users_api")
    assert rebound.metadata["execution_bound"] is True
    assert rebound.metadata["approved_base_url"] == "https://service.example.com/api/"
    assert rebound.execution_metadata["approved_base_url"] == "https://service.example.com/api/"
    assert rebound.remote is True

    with pytest.raises(SchemaDriftError, match="tool contract changed"):
        await router.execute(plan)

    replanned = router.plan(
        PlanRequest(
            query="get user name",
            arguments={"user_id": "42"},
        )
    )
    assert replanned.calls[0].tool_fingerprint == rebound.fingerprint


@pytest.mark.asyncio
async def test_explicit_base_url_can_approve_cross_origin_openapi() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=json.dumps(openapi_document()),
            headers={"content-type": "application/json"},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        router = await SchemaRouter.from_url(
            "https://docs.example.com/openapi.json",
            base_url="https://service.example.com/api/",
            http_client=client,
        )

    tool = router.registry.get("users_api")
    assert tool.metadata["execution_bound"] is True
    assert tool.metadata["approved_base_url"] == "https://service.example.com/api/"
    assert tool.execution_metadata["execution_bound"] is True
    assert tool.execution_metadata["approved_base_url"] == "https://service.example.com/api/"
    assert tool.remote is True


@pytest.mark.asyncio
async def test_runtime_credentials_are_not_sent_to_schema_host() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert "authorization" not in request.headers
        return httpx.Response(
            200,
            content=json.dumps(openapi_document()),
            headers={"content-type": "application/json"},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        router = await SchemaRouter.from_url(
            "https://docs.example.com/openapi.json",
            trusted_headers={"Authorization": "Bearer runtime-secret"},
            http_client=client,
        )

    assert router.registry.get("users_api").metadata["execution_bound"] is False


@pytest.mark.asyncio
async def test_schema_headers_are_separate_from_runtime_headers() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["x-doc-token"] == "schema-secret"
        assert "authorization" not in request.headers
        return httpx.Response(
            200,
            content=json.dumps(openapi_document()),
            headers={"content-type": "application/json"},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        await SchemaRouter.from_url(
            "https://docs.example.com/openapi.json",
            schema_headers={"X-Doc-Token": "schema-secret"},
            trusted_headers={"Authorization": "Bearer runtime-secret"},
            http_client=client,
        )


@pytest.mark.asyncio
async def test_openapi_yaml_url_is_supported_and_same_origin_is_bound() -> None:
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
    assert tool.metadata["execution_bound"] is True
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


@pytest.mark.asyncio
async def test_schema_redirects_must_stay_on_original_origin() -> None:
    seen: list[httpx.URL] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url)
        if request.url == httpx.URL("https://docs.example.com/openapi.json"):
            return httpx.Response(
                302,
                headers={"location": "https://evil.example.com/openapi.json"},
            )
        raise AssertionError("cross-origin redirect target must never be requested")

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        follow_redirects=True,
    ) as client:
        router = SchemaRouter(http_client=client)
        with pytest.raises(UnsupportedSchemaSourceError, match="cross-origin"):
            await router.add_url(
                "https://docs.example.com/openapi.json",
                kind="openapi",
                schema_headers={"X-Doc-Token": "schema-secret"},
            )

    assert seen == [httpx.URL("https://docs.example.com/openapi.json")]


@pytest.mark.asyncio
async def test_same_origin_schema_redirect_preserves_schema_headers() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["x-doc-token"] == "schema-secret"
        if request.url == httpx.URL("https://docs.example.com/openapi.json"):
            return httpx.Response(302, headers={"location": "/spec/openapi.json"})
        assert request.url == httpx.URL("https://docs.example.com/spec/openapi.json")
        document = openapi_document()
        document["servers"] = [{"url": "https://docs.example.com/api/"}]
        return httpx.Response(
            200,
            content=json.dumps(document),
            headers={"content-type": "application/json"},
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        follow_redirects=True,
    ) as client:
        router = await SchemaRouter.from_url(
            "https://docs.example.com/openapi.json",
            schema_headers={"X-Doc-Token": "schema-secret"},
            http_client=client,
        )

    tool = router.registry.get("users_api")
    assert tool.metadata["resolved_schema_url"] == (
        "https://docs.example.com/spec/openapi.json"
    )
    assert tool.metadata["execution_bound"] is True


@pytest.mark.asyncio
async def test_openapi_document_size_is_bounded() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=b"x" * (5 * 1024 * 1024 + 1),
            headers={"content-type": "application/json"},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        router = SchemaRouter(http_client=client)
        with pytest.raises(UnsupportedSchemaSourceError, match="safety limit"):
            await router.add_url(
                "https://docs.example.com/openapi.json",
                kind="openapi",
            )



@pytest.mark.asyncio
async def test_openapi_query_secret_is_fetched_but_not_persisted_in_tool_state() -> None:
    source = "https://docs.example.com/openapi.json?token=top-secret"

    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == source
        return httpx.Response(
            200,
            content=json.dumps(openapi_document()),
            headers={"content-type": "application/json"},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        router = await SchemaRouter.from_url(
            source,
            kind="openapi",
            http_client=client,
        )

    tool = router.registry.get("users_api")
    assert tool.metadata["source_url"] == "https://docs.example.com/openapi.json"
    assert tool.metadata["resolved_schema_url"] == "https://docs.example.com/openapi.json"
    assert "source_url" not in tool.execution_metadata
    assert "resolved_schema_url" not in tool.execution_metadata
    assert "top-secret" not in tool.model_dump_json()



@pytest.mark.asyncio
async def test_adapter_error_redacts_source_query_secret() -> None:
    class ExplodingAdapter:
        kind = "explode"
        priority = 1

        async def load(self, context):
            raise RuntimeError("adapter failure")

    router = SchemaRouter()
    router.register_adapter(ExplodingAdapter())
    source = "https://docs.example.com/schema?token=top-secret"

    with pytest.raises(SchemaSourceError) as exc_info:
        await router.add_url(source, kind="explode")

    message = str(exc_info.value)
    assert "https://docs.example.com/schema" in message
    assert "top-secret" not in message
    assert "token=" not in message
