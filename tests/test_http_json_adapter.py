from __future__ import annotations

import httpx
import pytest

from schemarouter import (
    EndpointSpec,
    FieldSpec,
    ParameterSpec,
    PlanRequest,
    SchemaRouter,
    ToolSpec,
)


def _crossref_tool() -> ToolSpec:
    return ToolSpec(
        name="crossref",
        description="Crossref scholarly metadata API",
        provider="crossref",
        access_mode="rest",
        endpoints=[
            EndpointSpec(
                name="get_work",
                description="Get one work by DOI",
                method="GET",
                path="/works/{doi}",
                read_only=True,
                destructive=False,
                parameters=[
                    ParameterSpec(
                        name="doi",
                        required=True,
                        location="path",
                        json_schema={"type": "string"},
                    ),
                ],
                output_schema={
                    "type": "object",
                    "properties": {
                        "status": {"type": "string"},
                        "message": {
                            "type": "object",
                            "properties": {
                                "DOI": {"type": "string"},
                                "title": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                            },
                        },
                    },
                },
                output_fields=[
                    FieldSpec(
                        name="status",
                        json_schema={"type": "string"},
                    ),
                    FieldSpec(
                        name="message",
                        json_schema={
                            "type": "object",
                            "properties": {
                                "DOI": {"type": "string"},
                                "title": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                            },
                        },
                    ),
                    FieldSpec(
                        name="message.DOI",
                        path=["message", "DOI"],
                        result_path=["message.DOI"],
                        json_schema={"type": "string"},
                        identifier=True,
                    ),
                ],
            )
        ],
    )


@pytest.mark.asyncio
async def test_declarative_http_tool_executes_crossref_style_get() -> None:
    seen_urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_urls.append(str(request.url))
        return httpx.Response(
            200,
            json={
                "status": "ok",
                "message": {
                    "DOI": "10.1234/test",
                    "title": ["Example"],
                },
            },
            request=request,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        router = SchemaRouter(http_client=client)
        key = router.add_http_tool(
            _crossref_tool(),
            base_url="https://api.crossref.test/v1",
            provider="crossref",
        )
        plan = router.plan_executable(
            PlanRequest(
                query="crossref DOI",
                preferred_tools=[key],
                arguments={"doi": "10.1234/test"},
            )
        )
        assert plan.executable
        plan.calls[0].fields = ["message.DOI"]
        results = await router.execute(plan)

    assert seen_urls == ["https://api.crossref.test/v1/works/10%2E1234%2Ftest"]
    assert results[0].data == {"message.DOI": "10.1234/test"}


@pytest.mark.asyncio
async def test_declarative_http_tool_keeps_brave_style_api_key_trusted() -> None:
    seen_headers: list[dict[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_headers.append(dict(request.headers))
        return httpx.Response(
            200,
            json={
                "web": {
                    "results": [
                        {
                            "title": "SchemaRouter",
                            "url": "https://example.test",
                            "description": "typed routing",
                        }
                    ]
                }
            },
            request=request,
        )

    tool = ToolSpec(
        name="brave_search",
        description="Web search",
        endpoints=[
            EndpointSpec(
                name="search",
                method="GET",
                path="/res/v1/web/search",
                read_only=True,
                destructive=False,
                parameters=[
                    ParameterSpec(
                        name="q",
                        required=True,
                        location="query",
                        json_schema={"type": "string"},
                    ),
                    ParameterSpec(
                        name="count",
                        location="query",
                        json_schema={"type": "integer", "minimum": 1},
                    ),
                ],
                output_schema={
                    "type": "object",
                    "properties": {
                        "web": {
                            "type": "object",
                            "properties": {
                                "results": {
                                    "type": "array",
                                    "items": {"type": "object"},
                                }
                            },
                        }
                    },
                },
                output_fields=[
                    FieldSpec(
                        name="web",
                        json_schema={
                            "type": "object",
                            "properties": {
                                "results": {
                                    "type": "array",
                                    "items": {"type": "object"},
                                }
                            },
                        },
                    )
                ],
            )
        ],
    )

    token = "secret-brave-token"
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        router = SchemaRouter(http_client=client)
        key = router.add_http_tool(
            tool,
            base_url="https://api.search.brave.test",
            provider="brave",
            trusted_headers={"X-Subscription-Token": token},
        )
        assert token not in repr(router.registry.get(key).model_dump(mode="json"))

        results = await router.ainvoke(
            PlanRequest(
                query="web search",
                preferred_tools=[key],
                arguments={"q": "SchemaRouter", "count": 5},
            )
        )

    assert results[0].data["web"]["results"][0]["title"] == "SchemaRouter"
    assert seen_headers[0]["x-subscription-token"] == token


@pytest.mark.asyncio
async def test_declarative_http_tool_supports_tavily_style_json_body() -> None:
    seen_json: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        seen_json.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "answer": "SchemaRouter is a typed capability router.",
                "results": [],
            },
            request=request,
        )

    tool = ToolSpec(
        name="tavily_search",
        endpoints=[
            EndpointSpec(
                name="search",
                method="POST",
                path="/search",
                read_only=True,
                destructive=False,
                parameters=[
                    ParameterSpec(
                        name="query",
                        required=True,
                        location="body",
                        json_schema={"type": "string"},
                    ),
                    ParameterSpec(
                        name="max_results",
                        location="body",
                        json_schema={"type": "integer", "minimum": 1},
                    ),
                ],
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "max_results": {"type": "integer", "minimum": 1},
                    },
                    "required": ["query"],
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "answer": {"type": "string"},
                        "results": {"type": "array", "items": {"type": "object"}},
                    },
                },
                output_fields=[
                    FieldSpec(name="answer", json_schema={"type": "string"}),
                    FieldSpec(
                        name="results",
                        json_schema={"type": "array", "items": {"type": "object"}},
                    ),
                ],
            )
        ],
    )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        router = SchemaRouter(http_client=client)
        key = router.add_http_tool(
            tool,
            base_url="https://api.tavily.test",
            provider="tavily",
            trusted_headers={"Authorization": "Bearer secret"},
        )
        results = await router.ainvoke(
            PlanRequest(
                query="tavily answer",
                preferred_tools=[key],
                arguments={"query": "SchemaRouter", "max_results": 3},
            )
        )

    assert seen_json == [{"query": "SchemaRouter", "max_results": 3}]
    assert results[0].data["answer"].startswith("SchemaRouter")


def test_declarative_http_tool_requires_method_and_path() -> None:
    router = SchemaRouter()
    tool = ToolSpec(
        name="invalid",
        endpoints=[EndpointSpec(name="missing_transport")],
    )

    with pytest.raises(Exception, match="requires method and path"):
        router.add_http_tool(
            tool,
            base_url="https://example.test",
        )
