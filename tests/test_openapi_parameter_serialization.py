import httpx
import pytest

from schemarouter import NonRetryableInvocationError, analyze_openapi_compatibility
from schemarouter.adapters.openapi import OpenAPIRemoteInvoker, tool_from_openapi


def serialization_document(parameters: list[dict]) -> dict:
    return {
        "openapi": "3.1.0",
        "info": {"title": "Serialization API"},
        "paths": {
            "/items/{path_value}": {
                "get": {
                    "operationId": "read_items",
                    "parameters": parameters,
                    "responses": {"204": {"description": "ok"}},
                }
            }
        },
    }


def test_openapi_parameter_defaults_are_compiled_into_contract() -> None:
    tool = tool_from_openapi(
        "serialization",
        serialization_document(
            [
                {
                    "name": "path_value",
                    "in": "path",
                    "required": True,
                    "schema": {"type": "string"},
                },
                {
                    "name": "tags",
                    "in": "query",
                    "schema": {"type": "array", "items": {"type": "string"}},
                },
                {
                    "name": "X-Meta",
                    "in": "header",
                    "schema": {"type": "string"},
                },
            ]
        ),
    )
    endpoint = tool.endpoint("read_items")
    by_name = {parameter.name: parameter for parameter in endpoint.parameters}

    assert by_name["path_value"].style == "simple"
    assert by_name["path_value"].explode is False
    assert by_name["tags"].style == "form"
    assert by_name["tags"].explode is True
    assert by_name["X-Meta"].style == "simple"
    assert by_name["X-Meta"].explode is False


@pytest.mark.asyncio
async def test_default_query_form_array_uses_repeated_keys() -> None:
    tool = tool_from_openapi(
        "serialization",
        serialization_document(
            [
                {
                    "name": "path_value",
                    "in": "path",
                    "required": True,
                    "schema": {"type": "string"},
                },
                {
                    "name": "tag",
                    "in": "query",
                    "schema": {"type": "array", "items": {"type": "string"}},
                },
            ]
        ),
    )

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params.multi_items() == [
            ("tag", "red"),
            ("tag", "blue"),
        ]
        return httpx.Response(204, request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        invoker = OpenAPIRemoteInvoker(
            tool,
            "https://api.example.test",
            http_client=client,
        )
        await invoker(
            "read_items",
            {
                "path_value": "42",
                "tag": ["red", "blue"],
            },
        )


@pytest.mark.asyncio
async def test_query_form_explode_false_joins_array_and_object() -> None:
    document = serialization_document(
        [
            {
                "name": "path_value",
                "in": "path",
                "required": True,
                "schema": {"type": "string"},
            },
            {
                "name": "tag",
                "in": "query",
                "style": "form",
                "explode": False,
                "schema": {"type": "array", "items": {"type": "string"}},
            },
            {
                "name": "filter",
                "in": "query",
                "style": "form",
                "explode": False,
                "schema": {"type": "object"},
            },
        ]
    )
    tool = tool_from_openapi("serialization", document)

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params.get("tag") == "red,blue"
        assert request.url.params.get("filter") == "role,admin,active,true"
        return httpx.Response(204, request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        invoker = OpenAPIRemoteInvoker(
            tool,
            "https://api.example.test",
            http_client=client,
        )
        await invoker(
            "read_items",
            {
                "path_value": "42",
                "tag": ["red", "blue"],
                "filter": {"role": "admin", "active": True},
            },
        )


@pytest.mark.asyncio
async def test_query_form_explode_true_object_uses_property_names() -> None:
    document = serialization_document(
        [
            {
                "name": "path_value",
                "in": "path",
                "required": True,
                "schema": {"type": "string"},
            },
            {
                "name": "filter",
                "in": "query",
                "schema": {"type": "object"},
            },
        ]
    )
    tool = tool_from_openapi("serialization", document)

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params.multi_items() == [
            ("role", "admin"),
            ("active", "true"),
        ]
        return httpx.Response(204, request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        invoker = OpenAPIRemoteInvoker(
            tool,
            "https://api.example.test",
            http_client=client,
        )
        await invoker(
            "read_items",
            {
                "path_value": "42",
                "filter": {"role": "admin", "active": True},
            },
        )


@pytest.mark.asyncio
async def test_path_simple_serializes_array_and_object_without_python_repr() -> None:
    document = {
        "openapi": "3.1.0",
        "info": {"title": "Path Serialization API"},
        "paths": {
            "/items/{ids}/{attrs}": {
                "get": {
                    "operationId": "read_items",
                    "parameters": [
                        {
                            "name": "ids",
                            "in": "path",
                            "required": True,
                            "schema": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                        },
                        {
                            "name": "attrs",
                            "in": "path",
                            "required": True,
                            "style": "simple",
                            "explode": True,
                            "schema": {"type": "object"},
                        },
                    ],
                    "responses": {"204": {"description": "ok"}},
                }
            }
        },
    }
    tool = tool_from_openapi("serialization", document)

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.raw_path == b"/items/a,b/role=admin,active=true"
        return httpx.Response(204, request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        invoker = OpenAPIRemoteInvoker(
            tool,
            "https://api.example.test",
            http_client=client,
        )
        await invoker(
            "read_items",
            {
                "ids": ["a", "b"],
                "attrs": {"role": "admin", "active": True},
            },
        )


@pytest.mark.asyncio
async def test_header_simple_serializes_arrays_and_exploded_objects() -> None:
    document = {
        "openapi": "3.1.0",
        "info": {"title": "Header Serialization API"},
        "paths": {
            "/items": {
                "get": {
                    "operationId": "read_items",
                    "parameters": [
                        {
                            "name": "X-Tags",
                            "in": "header",
                            "schema": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                        },
                        {
                            "name": "X-Meta",
                            "in": "header",
                            "style": "simple",
                            "explode": True,
                            "schema": {"type": "object"},
                        },
                    ],
                    "responses": {"204": {"description": "ok"}},
                }
            }
        },
    }
    tool = tool_from_openapi("serialization", document)

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["X-Tags"] == "red,blue"
        assert request.headers["X-Meta"] == "role=admin,active=true"
        return httpx.Response(204, request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        invoker = OpenAPIRemoteInvoker(
            tool,
            "https://api.example.test",
            http_client=client,
        )
        await invoker(
            "read_items",
            {
                "X-Tags": ["red", "blue"],
                "X-Meta": {"role": "admin", "active": True},
            },
        )


@pytest.mark.asyncio
async def test_unsupported_parameter_style_fails_before_network() -> None:
    document = serialization_document(
        [
            {
                "name": "path_value",
                "in": "path",
                "required": True,
                "schema": {"type": "string"},
            },
            {
                "name": "filter",
                "in": "query",
                "style": "deepObject",
                "explode": True,
                "schema": {"type": "object"},
            },
        ]
    )
    tool = tool_from_openapi("serialization", document)

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
        with pytest.raises(
            NonRetryableInvocationError,
            match="unsupported query parameter style",
        ):
            await invoker(
                "read_items",
                {
                    "path_value": "42",
                    "filter": {"role": "admin"},
                },
            )

    report = analyze_openapi_compatibility(document)
    assert any(
        issue.schema_construct == "parameter_style"
        and issue.support == "unsupported"
        for issue in report.issues
    )


@pytest.mark.asyncio
async def test_allow_reserved_true_fails_before_network_and_is_reported() -> None:
    document = serialization_document(
        [
            {
                "name": "path_value",
                "in": "path",
                "required": True,
                "schema": {"type": "string"},
            },
            {
                "name": "q",
                "in": "query",
                "allowReserved": True,
                "schema": {"type": "string"},
            },
        ]
    )
    tool = tool_from_openapi("serialization", document)

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
        with pytest.raises(NonRetryableInvocationError, match="allowReserved=true"):
            await invoker(
                "read_items",
                {
                    "path_value": "42",
                    "q": "a/b?c=d",
                },
            )

    report = analyze_openapi_compatibility(document)
    assert any(
        issue.schema_construct == "allow_reserved"
        and issue.support == "unsupported"
        for issue in report.issues
    )
