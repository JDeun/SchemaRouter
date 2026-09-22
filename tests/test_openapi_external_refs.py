import json

import httpx
import pytest

from schemarouter import (
    PlanRequest,
    SchemaRouter,
    UnsupportedSchemaSourceError,
)


def root_document(ref: str) -> dict:
    return {
        "openapi": "3.1.0",
        "info": {"title": "External Refs API"},
        "paths": {
            "/user": {
                "get": {
                    "operationId": "get_user",
                    "responses": {
                        "200": {
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": ref},
                                }
                            }
                        }
                    },
                }
            }
        },
    }


@pytest.mark.asyncio
async def test_external_refs_remain_off_by_default() -> None:
    seen: list[httpx.URL] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url)
        assert request.url == httpx.URL(
            "https://docs.example.com/spec/openapi.json"
        )
        return httpx.Response(
            200,
            json=root_document("./schemas.json#/User"),
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        router = await SchemaRouter.from_url(
            "https://docs.example.com/spec/openapi.json",
            kind="openapi",
            http_client=client,
        )

    tool = router.registry.get("external_refs_api")
    endpoint = tool.endpoint("get_user")

    assert seen == [httpx.URL("https://docs.example.com/spec/openapi.json")]
    assert endpoint.output_fields == []
    assert tool.metadata["external_refs_enabled"] is False
    assert tool.metadata["external_ref_documents_resolved"] == 0
    assert any(
        issue["construct"] == "external_ref"
        for issue in tool.metadata["compatibility"]["issues"]
    )


@pytest.mark.asyncio
async def test_opt_in_resolves_same_origin_nested_external_refs_and_preserves_validation() -> None:
    seen: list[httpx.URL] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url)
        assert request.headers["x-doc-token"] == "schema-secret"
        if request.url == httpx.URL(
            "https://docs.example.com/spec/openapi.json"
        ):
            return httpx.Response(
                200,
                json=root_document("./schemas.json#/User"),
            )
        if request.url == httpx.URL(
            "https://docs.example.com/spec/schemas.json"
        ):
            return httpx.Response(
                200,
                json={
                    "User": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string"},
                            "profile": {
                                "$ref": "./profile.yaml#/Profile",
                            },
                        },
                        "required": ["id", "profile"],
                    }
                },
            )
        if request.url == httpx.URL(
            "https://docs.example.com/spec/profile.yaml"
        ):
            return httpx.Response(
                200,
                text=(
                    "Profile:\n"
                    "  type: object\n"
                    "  properties:\n"
                    "    name:\n"
                    "      type: string\n"
                    "  required: [name]\n"
                ),
                headers={"content-type": "application/yaml"},
            )
        raise AssertionError(f"unexpected URL: {request.url}")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        router = await SchemaRouter.from_url(
            "https://docs.example.com/spec/openapi.json",
            kind="openapi",
            schema_headers={"X-Doc-Token": "schema-secret"},
            openapi_external_refs=True,
            http_client=client,
        )

    tool = router.registry.get("external_refs_api")
    endpoint = tool.endpoint("get_user")

    assert [field.name for field in endpoint.output_fields] == ["id", "profile"]
    assert tool.metadata["external_refs_enabled"] is True
    assert tool.metadata["external_ref_documents_resolved"] == 2
    assert tool.metadata["external_ref_bytes_fetched"] > 0
    assert not any(
        issue["construct"] == "external_ref"
        for issue in tool.metadata["compatibility"]["issues"]
    )
    assert "x-schemarouter-external-refs" in endpoint.output_schema
    assert seen == [
        httpx.URL("https://docs.example.com/spec/openapi.json"),
        httpx.URL("https://docs.example.com/spec/schemas.json"),
        httpx.URL("https://docs.example.com/spec/profile.yaml"),
    ]

    router.executor.bind(
        "external_refs_api",
        lambda endpoint_name, arguments: {
            "id": "42",
            "profile": {"name": "Ada"},
        },
    )
    result = await router.ainvoke(PlanRequest(query="user id profile"))

    assert result[0].data == {
        "id": "42",
        "profile": {"name": "Ada"},
    }


@pytest.mark.asyncio
async def test_external_ref_cross_origin_is_rejected_before_target_fetch() -> None:
    seen: list[httpx.URL] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url)
        if request.url == httpx.URL(
            "https://docs.example.com/openapi.json"
        ):
            return httpx.Response(
                200,
                json=root_document(
                    "https://evil.example.com/schema.json#/User"
                ),
            )
        raise AssertionError("cross-origin target must never be fetched")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(
            UnsupportedSchemaSourceError,
            match="cross-origin external OpenAPI",
        ):
            await SchemaRouter.from_url(
                "https://docs.example.com/openapi.json",
                kind="openapi",
                openapi_external_refs=True,
                http_client=client,
            )

    assert seen == [httpx.URL("https://docs.example.com/openapi.json")]


@pytest.mark.asyncio
async def test_external_ref_depth_limit_fails_before_deeper_fetch() -> None:
    seen: list[httpx.URL] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url)
        if request.url == httpx.URL(
            "https://docs.example.com/openapi.json"
        ):
            return httpx.Response(
                200,
                json=root_document("./a.json#/A"),
            )
        if request.url == httpx.URL("https://docs.example.com/a.json"):
            return httpx.Response(
                200,
                json={
                    "A": {
                        "allOf": [
                            {"$ref": "./b.json#/B"},
                        ]
                    }
                },
            )
        raise AssertionError("depth-limited target must never be fetched")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(
            UnsupportedSchemaSourceError,
            match="depth limit",
        ):
            await SchemaRouter.from_url(
                "https://docs.example.com/openapi.json",
                kind="openapi",
                openapi_external_refs=True,
                openapi_ref_max_depth=1,
                http_client=client,
            )

    assert seen == [
        httpx.URL("https://docs.example.com/openapi.json"),
        httpx.URL("https://docs.example.com/a.json"),
    ]


@pytest.mark.asyncio
async def test_external_ref_document_limit_is_enforced() -> None:
    seen: list[httpx.URL] = []
    document = root_document("./a.json#/A")
    document["components"] = {
        "schemas": {
            "Other": {"$ref": "./b.json#/B"},
        }
    }

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url)
        if request.url == httpx.URL(
            "https://docs.example.com/openapi.json"
        ):
            return httpx.Response(200, json=document)
        if request.url == httpx.URL("https://docs.example.com/a.json"):
            return httpx.Response(
                200,
                json={"A": {"type": "object"}},
            )
        raise AssertionError("document-limited target must never be fetched")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(
            UnsupportedSchemaSourceError,
            match="document limit",
        ):
            await SchemaRouter.from_url(
                "https://docs.example.com/openapi.json",
                kind="openapi",
                openapi_external_refs=True,
                openapi_ref_max_documents=1,
                http_client=client,
            )

    assert seen == [
        httpx.URL("https://docs.example.com/openapi.json"),
        httpx.URL("https://docs.example.com/a.json"),
    ]


@pytest.mark.asyncio
async def test_external_ref_byte_budget_is_enforced() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url == httpx.URL(
            "https://docs.example.com/openapi.json"
        ):
            return httpx.Response(
                200,
                json=root_document("./large.json#/User"),
            )
        if request.url == httpx.URL("https://docs.example.com/large.json"):
            return httpx.Response(
                200,
                content=b"x" * 256,
                headers={"content-type": "application/json"},
            )
        raise AssertionError(f"unexpected URL: {request.url}")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(
            UnsupportedSchemaSourceError,
            match="byte safety limit|byte budget",
        ):
            await SchemaRouter.from_url(
                "https://docs.example.com/openapi.json",
                kind="openapi",
                openapi_external_refs=True,
                openapi_ref_max_bytes=128,
                http_client=client,
            )


@pytest.mark.asyncio
async def test_external_ref_rejects_schema_id_rebasing() -> None:
    seen: list[httpx.URL] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url)
        if request.url == httpx.URL(
            "https://docs.example.com/openapi.json"
        ):
            return httpx.Response(
                200,
                json=root_document("./schema.json#/User"),
            )
        if request.url == httpx.URL("https://docs.example.com/schema.json"):
            return httpx.Response(
                200,
                json={
                    "$id": "https://schemas.example.com/base",
                    "User": {"type": "object"},
                },
            )
        raise AssertionError(f"unexpected URL: {request.url}")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(
            UnsupportedSchemaSourceError,
            match=r"\$id-based base URI rebasing",
        ):
            await SchemaRouter.from_url(
                "https://docs.example.com/openapi.json",
                kind="openapi",
                openapi_external_refs=True,
                http_client=client,
            )

    assert seen == [
        httpx.URL("https://docs.example.com/openapi.json"),
        httpx.URL("https://docs.example.com/schema.json"),
    ]


@pytest.mark.asyncio
async def test_external_ref_rejects_non_json_pointer_anchor_without_fetch() -> None:
    seen: list[httpx.URL] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url)
        return httpx.Response(
            200,
            json=root_document("./schema.json#User"),
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(
            UnsupportedSchemaSourceError,
            match="JSON-Pointer fragments",
        ):
            await SchemaRouter.from_url(
                "https://docs.example.com/openapi.json",
                kind="openapi",
                openapi_external_refs=True,
                http_client=client,
            )

    assert seen == [httpx.URL("https://docs.example.com/openapi.json")]


@pytest.mark.asyncio
async def test_external_ref_cycle_uses_cached_documents_without_refetching() -> None:
    seen: list[httpx.URL] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url)
        if request.url == httpx.URL(
            "https://docs.example.com/openapi.json"
        ):
            return httpx.Response(
                200,
                json=root_document("./a.json#/A"),
            )
        if request.url == httpx.URL("https://docs.example.com/a.json"):
            return httpx.Response(
                200,
                json={
                    "A": {
                        "type": "object",
                        "properties": {"id": {"type": "string"}},
                        "allOf": [{"$ref": "./b.json#/B"}],
                    }
                },
            )
        if request.url == httpx.URL("https://docs.example.com/b.json"):
            return httpx.Response(
                200,
                json={
                    "B": {
                        "allOf": [{"$ref": "./a.json#/A"}],
                    }
                },
            )
        raise AssertionError(f"unexpected URL: {request.url}")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        router = await SchemaRouter.from_url(
            "https://docs.example.com/openapi.json",
            kind="openapi",
            openapi_external_refs=True,
            http_client=client,
        )

    tool = router.registry.get("external_refs_api")
    assert tool.metadata["external_ref_documents_resolved"] == 2
    assert [field.name for field in tool.endpoint("get_user").output_fields] == ["id"]
    assert seen == [
        httpx.URL("https://docs.example.com/openapi.json"),
        httpx.URL("https://docs.example.com/a.json"),
        httpx.URL("https://docs.example.com/b.json"),
    ]


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"openapi_ref_max_depth": 0}, "openapi_ref_max_depth"),
        ({"openapi_ref_max_documents": 0}, "openapi_ref_max_documents"),
        ({"openapi_ref_max_bytes": 0}, "openapi_ref_max_bytes"),
        ({"openapi_ref_max_depth": True}, "openapi_ref_max_depth"),
    ],
)
@pytest.mark.asyncio
async def test_external_ref_limits_require_positive_integers(
    kwargs: dict,
    message: str,
) -> None:
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(500, request=request)
        )
    ) as client:
        router = SchemaRouter(http_client=client)
        with pytest.raises(Exception, match=message):
            await router.add_url(
                "https://docs.example.com/openapi.json",
                kind="openapi",
                **kwargs,
            )
