from __future__ import annotations

import httpx
import pytest
from pydantic import BaseModel

from schemarouter import (
    EndpointSpec,
    FieldSpec,
    ParameterSpec,
    SchemaRouter,
    ToolSpec,
    tool_from_callable,
)
from schemarouter.adapters import prepare_http_json_tool, tool_from_openapi
from schemarouter.integrations import tool_from_langchain


class SearchArgs(BaseModel):
    query: str


class FakeDuckDuckGoTool:
    name = "duckduckgo_search"
    description = "Search the public web."
    args_schema = SearchArgs

    def invoke(self, arguments: dict) -> str:
        return f"result:{arguments['query']}"


class ArxivArgs(BaseModel):
    query: str
    max_results: int = 5


class ArxivResult(BaseModel):
    title: str
    entry_id: str


class FakeArxivTool:
    name = "arxiv_search"
    description = "Search scholarly papers."
    args_schema = ArxivArgs

    def get_output_jsonschema(self) -> dict:
        return ArxivResult.model_json_schema()

    def invoke(self, arguments: dict) -> dict:
        return {
            "title": arguments["query"],
            "entry_id": "arxiv:fixture",
        }


class YahooQuote(BaseModel):
    symbol: str
    price: float
    currency: str


def yahoo_quote(symbol: str) -> YahooQuote:
    return YahooQuote(
        symbol=symbol,
        price=100.0,
        currency="USD",
    )


def test_duckduckgo_shape_compiles_through_agent_tool_import() -> None:
    tool = tool_from_langchain(
        FakeDuckDuckGoTool(),
        provider="duckduckgo",
        access_mode="langchain",
        read_only=True,
        remote=True,
    )

    endpoint = tool.endpoint("invoke")
    assert tool.provider == "duckduckgo"
    assert tool.access_mode == "langchain"
    assert endpoint.read_only is True
    assert [parameter.name for parameter in endpoint.parameters] == ["query"]


def test_arxiv_shape_preserves_declared_scholarly_output_contract() -> None:
    tool = tool_from_langchain(
        FakeArxivTool(),
        provider="arxiv",
        access_mode="langchain",
        read_only=True,
        remote=True,
    )

    endpoint = tool.endpoint("invoke")
    fields = {field.name: field for field in endpoint.output_fields}

    assert {parameter.name for parameter in endpoint.parameters} == {
        "query",
        "max_results",
    }
    assert fields["title"].json_schema["type"] == "string"
    assert fields["entry_id"].json_schema["type"] == "string"
    assert fields["entry_id"].identifier is True


def test_yahoo_finance_shape_compiles_through_typed_python_callable() -> None:
    tool = tool_from_callable(
        yahoo_quote,
        name="yahoo_quote",
        provider="yahoo-finance",
        access_mode="python",
    )

    endpoint = tool.endpoint("call")
    fields = {field.name: field for field in endpoint.output_fields}

    assert tool.provider == "yahoo-finance"
    assert tool.access_mode == "python"
    assert [parameter.name for parameter in endpoint.parameters] == ["symbol"]
    assert fields["symbol"].json_schema["type"] == "string"
    assert fields["price"].json_schema["type"] == "number"
    assert fields["currency"].json_schema["type"] == "string"


def _web_search_http_tool(name: str) -> ToolSpec:
    return ToolSpec(
        name=name,
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
                    )
                ],
                input_schema={
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                    "required": ["query"],
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "answer": {"type": "string"},
                        "results": {
                            "type": "array",
                            "items": {"type": "object"},
                        },
                    },
                },
                output_fields=[
                    FieldSpec(
                        name="answer",
                        json_schema={"type": "string"},
                    ),
                    FieldSpec(
                        name="results",
                        json_schema={
                            "type": "array",
                            "items": {"type": "object"},
                        },
                    ),
                ],
            )
        ],
    )


def test_tavily_shape_compiles_through_declarative_http_json() -> None:
    tool = prepare_http_json_tool(
        _web_search_http_tool("tavily_search"),
        base_url="https://api.tavily.example",
        provider="tavily",
        access_mode="http_json",
    )

    endpoint = tool.endpoint("search")
    assert tool.provider == "tavily"
    assert tool.access_mode == "http_json"
    assert tool.remote is True
    assert endpoint.read_only is True
    assert endpoint.parameters[0].location == "body"
    assert {field.name for field in endpoint.output_fields} == {
        "answer",
        "results",
    }


def test_brave_shape_keeps_auth_outside_canonical_contract() -> None:
    brave = ToolSpec(
        name="brave_search",
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
                    )
                ],
                output_schema={
                    "type": "object",
                    "properties": {
                        "web": {"type": "object"},
                    },
                },
                output_fields=[
                    FieldSpec(
                        name="web",
                        json_schema={"type": "object"},
                    )
                ],
            )
        ],
    )
    tool = prepare_http_json_tool(
        brave,
        base_url="https://api.search.brave.example",
        provider="brave",
        access_mode="http_json",
    )

    serialized = repr(tool.model_dump(mode="json"))
    assert "subscription-token" not in serialized.lower()
    assert "authorization" not in serialized.lower()
    assert tool.provider == "brave"
    assert tool.access_mode == "http_json"


def test_crossref_shape_compiles_from_openapi() -> None:
    document = {
        "openapi": "3.1.0",
        "info": {
            "title": "Crossref fixture",
            "version": "1.0.0",
        },
        "paths": {
            "/works/{doi}": {
                "get": {
                    "operationId": "get_work",
                    "parameters": [
                        {
                            "name": "doi",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"},
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "ok",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "status": {"type": "string"},
                                            "message": {
                                                "type": "object",
                                                "properties": {
                                                    "DOI": {"type": "string"},
                                                    "title": {
                                                        "type": "array",
                                                        "items": {
                                                            "type": "string"
                                                        },
                                                    },
                                                },
                                            },
                                        },
                                    }
                                }
                            },
                        }
                    },
                }
            }
        },
    }

    tool = tool_from_openapi("crossref", document)
    tool.provider = "crossref"
    tool.access_mode = "openapi"

    endpoint = tool.endpoint("get_work")
    fields = {field.name for field in endpoint.output_fields}
    assert endpoint.parameters[0].name == "doi"
    assert endpoint.parameters[0].required is True
    assert {"status", "message", "message.DOI"} <= fields
    assert tool.provider == "crossref"
    assert tool.access_mode == "openapi"


class MaterialRecord(BaseModel):
    material_id: str
    band_gap: float


def materials_python_lookup(material_id: str) -> MaterialRecord:
    return MaterialRecord(material_id=material_id, band_gap=1.25)


@pytest.mark.asyncio
async def test_materials_project_can_coexist_through_openapi_optimade_and_python() -> None:
    optimade_base = {
        "data": {
            "type": "info",
            "id": "/",
            "attributes": {
                "api_version": "1.3.0",
                "available_api_versions": [
                    {
                        "url": "https://mp.example/v1",
                        "version": "1.3.0",
                    }
                ],
                "formats": ["json"],
                "entry_types_by_format": {"json": ["structures"]},
                "available_endpoints": ["structures", "info", "links"],
                "is_index": False,
            },
        }
    }
    optimade_structures = {
        "data": {
            "type": "info",
            "id": "structures",
            "description": "Materials",
            "formats": ["json"],
            "properties": {
                "material_id": {
                    "type": "string",
                    "description": "Material identifier",
                },
                "band_gap": {
                    "type": "float",
                    "x-optimade-unit": "eV",
                },
            },
            "output_fields_by_format": {
                "json": ["material_id", "band_gap"],
            },
        }
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/info":
            return httpx.Response(
                200,
                json=optimade_base,
                request=request,
            )
        if request.url.path == "/v1/info/structures":
            return httpx.Response(
                200,
                json=optimade_structures,
                request=request,
            )
        raise AssertionError(f"unexpected OPTIMADE request: {request.url}")

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    ) as client:
        router = await SchemaRouter.from_url(
            "https://mp.example/v1",
            kind="optimade",
            provider="materials-project",
            access_mode="optimade",
            http_client=client,
        )

    python_tool = tool_from_callable(
        materials_python_lookup,
        name="materials_python",
        provider="materials-project",
        access_mode="python",
    )

    openapi_document = {
        "openapi": "3.1.0",
        "info": {"title": "MP fixture", "version": "1.0.0"},
        "paths": {
            "/materials/{material_id}": {
                "get": {
                    "operationId": "get_material",
                    "parameters": [
                        {
                            "name": "material_id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"},
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "ok",
                            "content": {
                                "application/json": {
                                    "schema": MaterialRecord.model_json_schema()
                                }
                            },
                        }
                    },
                }
            }
        },
    }
    openapi_tool = tool_from_openapi("materials_openapi", openapi_document)
    openapi_tool.provider = "materials-project"
    openapi_tool.access_mode = "openapi"

    optimade_tool = router.registry.get("mp.example")
    assert optimade_tool.provider == "materials-project"
    assert optimade_tool.access_mode == "optimade"
    assert python_tool.provider == "materials-project"
    assert python_tool.access_mode == "python"
    assert openapi_tool.provider == "materials-project"
    assert openapi_tool.access_mode == "openapi"

    fields = {
        field.name: field
        for field in optimade_tool.endpoint("search_structures").output_fields
    }
    assert fields["band_gap"].unit == "eV"
