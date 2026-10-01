from __future__ import annotations

from pydantic import BaseModel

from schemarouter import InMemoryRegistry, PlanRequest, SchemaPlanner
from schemarouter.adapters.graphql import (
    _operation_query,
    tool_from_graphql_introspection,
)
from schemarouter.adapters.mcp import tool_from_mcp
from schemarouter.adapters.openapi import tool_from_openapi
from schemarouter.adapters.python import tool_from_callable


def _search_schema() -> dict:
    return {
        "type": "object",
        "properties": {
            "results": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "url": {"type": "string"},
                        "score": {
                            "type": "number",
                            "x-ucum-unit": "eV",
                        },
                    },
                },
            }
        },
    }


def _openapi_tool():
    document = {
        "openapi": "3.1.0",
        "info": {"title": "Search", "version": "1.0.0"},
        "paths": {
            "/search": {
                "get": {
                    "operationId": "search",
                    "responses": {
                        "200": {
                            "description": "ok",
                            "content": {
                                "application/json": {
                                    "schema": _search_schema(),
                                }
                            },
                        }
                    },
                }
            }
        },
    }
    return tool_from_openapi("search_api", document)


def test_openapi_discovers_array_item_fields() -> None:
    endpoint = _openapi_tool().endpoint("search")
    fields = {field.name: field for field in endpoint.output_fields}

    assert {
        "results",
        "results[].title",
        "results[].url",
        "results[].score",
    } <= set(fields)
    assert fields["results[].title"].path == ["results", "*", "title"]
    assert fields["results[].title"].result_path == [
        "results",
        "*",
        "title",
    ]
    assert fields["results[].score"].unit == "eV"


def test_mcp_discovers_array_item_fields() -> None:
    tool = tool_from_mcp(
        "search_server",
        [
            {
                "name": "search",
                "description": "Search",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                },
                "outputSchema": _search_schema(),
            }
        ],
    )
    fields = {
        field.name: field
        for field in tool.endpoint("search").output_fields
    }

    assert "results[].title" in fields
    assert fields["results[].title"].path == ["results", "*", "title"]
    assert fields["results[].score"].unit == "eV"


class SearchItem(BaseModel):
    title: str
    url: str | None = None


class SearchResponse(BaseModel):
    results: list[SearchItem]


def _python_search() -> SearchResponse:
    return SearchResponse(results=[])


def test_python_callable_discovers_array_item_fields() -> None:
    tool = tool_from_callable(_python_search)
    fields = {
        field.name: field
        for field in tool.endpoint("call").output_fields
    }

    assert "results[].title" in fields
    assert fields["results[].title"].path == ["results", "*", "title"]
    assert "results[].url" in fields


def _gql_ref(
    kind: str,
    name: str | None = None,
    *,
    of_type: dict | None = None,
) -> dict:
    return {
        "kind": kind,
        "name": name,
        "ofType": of_type,
    }


def _graphql_introspection() -> dict:
    result_ref = _gql_ref("OBJECT", "SearchResult")
    list_ref = _gql_ref("LIST", of_type=result_ref)
    return {
        "data": {
            "__schema": {
                "queryType": {"name": "Query"},
                "mutationType": None,
                "subscriptionType": None,
                "types": [
                    {
                        "kind": "OBJECT",
                        "name": "Query",
                        "description": None,
                        "fields": [
                            {
                                "name": "search",
                                "description": "Search",
                                "isDeprecated": False,
                                "deprecationReason": None,
                                "args": [],
                                "type": _gql_ref(
                                    "OBJECT",
                                    "SearchPayload",
                                ),
                            }
                        ],
                        "inputFields": None,
                        "enumValues": None,
                        "possibleTypes": None,
                    },
                    {
                        "kind": "OBJECT",
                        "name": "SearchPayload",
                        "description": None,
                        "fields": [
                            {
                                "name": "results",
                                "description": None,
                                "isDeprecated": False,
                                "deprecationReason": None,
                                "args": [],
                                "type": list_ref,
                            }
                        ],
                        "inputFields": None,
                        "enumValues": None,
                        "possibleTypes": None,
                    },
                    {
                        "kind": "OBJECT",
                        "name": "SearchResult",
                        "description": None,
                        "fields": [
                            {
                                "name": "title",
                                "description": None,
                                "isDeprecated": False,
                                "deprecationReason": None,
                                "args": [],
                                "type": _gql_ref(
                                    "SCALAR",
                                    "String",
                                ),
                            },
                            {
                                "name": "url",
                                "description": None,
                                "isDeprecated": False,
                                "deprecationReason": None,
                                "args": [],
                                "type": _gql_ref(
                                    "SCALAR",
                                    "String",
                                ),
                            },
                        ],
                        "inputFields": None,
                        "enumValues": None,
                        "possibleTypes": None,
                    },
                    {
                        "kind": "SCALAR",
                        "name": "String",
                        "description": None,
                        "fields": None,
                        "inputFields": None,
                        "enumValues": None,
                        "possibleTypes": None,
                    },
                ],
            }
        }
    }


def test_graphql_discovers_array_children_and_renders_selection_set() -> None:
    tool = tool_from_graphql_introspection(
        "graphql_search",
        _graphql_introspection(),
    )
    endpoint = tool.endpoint("search")
    fields = {field.name: field for field in endpoint.output_fields}

    assert "results[].title" in fields
    assert fields["results[].title"].path == [
        "results",
        "*",
        "title",
    ]

    query = _operation_query(
        endpoint,
        ["results[].title"],
    )

    assert "results { title }" in query
    assert "results[]" not in query


def test_planner_prefers_matched_array_child_over_parent() -> None:
    tool = _openapi_tool()
    registry = InMemoryRegistry()
    registry.register(tool)
    planner = SchemaPlanner(registry)

    plan = planner.plan(
        PlanRequest(
            query="results title",
            preferred_tools=[tool.key],
        )
    )

    assert plan.calls
    assert "results[].title" in plan.calls[0].fields
    assert "results" not in plan.calls[0].fields


def test_planner_keeps_parent_when_only_parent_is_requested() -> None:
    tool = _openapi_tool()
    registry = InMemoryRegistry()
    registry.register(tool)
    planner = SchemaPlanner(registry)

    plan = planner.plan(
        PlanRequest(
            query="results",
            preferred_tools=[tool.key],
        )
    )

    assert plan.calls
    assert "results" in plan.calls[0].fields
    assert "results[].title" not in plan.calls[0].fields
