from __future__ import annotations

from pydantic import BaseModel

from schemarouter.adapters import (
    tool_from_callable,
    tool_from_graphql_introspection,
    tool_from_mcp,
    tool_from_openapi,
)


class SearchRecord(BaseModel):
    title: str
    url: str | None = None


class SearchResponse(BaseModel):
    results: list[SearchRecord]


def python_search() -> SearchResponse:
    return SearchResponse(results=[])


def _assert_result_array_fields(tool, endpoint_name: str) -> None:
    endpoint = tool.endpoint(endpoint_name)
    fields = {field.name: field for field in endpoint.output_fields}

    assert {"results", "results[].title", "results[].url"} <= set(fields)
    assert fields["results[].title"].path == ["results", "*", "title"]
    assert fields["results[].title"].result_path == ["results", "*", "title"]
    assert fields["results[].title"].json_schema["type"] == "string"


def test_openapi_discovers_array_item_fields() -> None:
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
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "results": {
                                                "type": "array",
                                                "items": {
                                                    "type": "object",
                                                    "properties": {
                                                        "title": {"type": "string"},
                                                        "url": {
                                                            "type": ["string", "null"]
                                                        },
                                                    },
                                                },
                                            }
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

    _assert_result_array_fields(
        tool_from_openapi("search", document),
        "search",
    )


def test_mcp_discovers_array_item_fields() -> None:
    tool = tool_from_mcp(
        "search",
        [
            {
                "name": "search",
                "inputSchema": {
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                },
                "outputSchema": {
                    "type": "object",
                    "properties": {
                        "results": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "title": {"type": "string"},
                                    "url": {"type": ["string", "null"]},
                                },
                            },
                        }
                    },
                },
            }
        ],
    )

    _assert_result_array_fields(tool, "search")


def test_python_callable_discovers_array_item_fields() -> None:
    _assert_result_array_fields(
        tool_from_callable(python_search),
        "call",
    )


def _graphql_ref(
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


def test_graphql_discovers_nested_list_item_fields() -> None:
    introspection = {
        "data": {
            "__schema": {
                "queryType": {"name": "Query"},
                "mutationType": None,
                "subscriptionType": None,
                "types": [
                    {
                        "kind": "OBJECT",
                        "name": "Query",
                        "fields": [
                            {
                                "name": "search",
                                "description": "search",
                                "args": [],
                                "type": _graphql_ref(
                                    "OBJECT",
                                    "SearchResponse",
                                ),
                                "isDeprecated": False,
                                "deprecationReason": None,
                            }
                        ],
                        "inputFields": None,
                        "enumValues": None,
                        "possibleTypes": None,
                    },
                    {
                        "kind": "OBJECT",
                        "name": "SearchResponse",
                        "fields": [
                            {
                                "name": "results",
                                "description": None,
                                "args": [],
                                "type": _graphql_ref(
                                    "LIST",
                                    of_type=_graphql_ref(
                                        "OBJECT",
                                        "SearchResult",
                                    ),
                                ),
                                "isDeprecated": False,
                                "deprecationReason": None,
                            }
                        ],
                        "inputFields": None,
                        "enumValues": None,
                        "possibleTypes": None,
                    },
                    {
                        "kind": "OBJECT",
                        "name": "SearchResult",
                        "fields": [
                            {
                                "name": "title",
                                "description": None,
                                "args": [],
                                "type": _graphql_ref("SCALAR", "String"),
                                "isDeprecated": False,
                                "deprecationReason": None,
                            },
                            {
                                "name": "url",
                                "description": None,
                                "args": [],
                                "type": _graphql_ref("SCALAR", "String"),
                                "isDeprecated": False,
                                "deprecationReason": None,
                            },
                        ],
                        "inputFields": None,
                        "enumValues": None,
                        "possibleTypes": None,
                    },
                    {
                        "kind": "SCALAR",
                        "name": "String",
                        "fields": None,
                        "inputFields": None,
                        "enumValues": None,
                        "possibleTypes": None,
                    },
                ],
            }
        }
    }

    tool = tool_from_graphql_introspection("search", introspection)
    _assert_result_array_fields(tool, "search")
