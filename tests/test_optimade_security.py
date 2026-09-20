import json

import httpx
import pytest

from schemarouter import PlanRequest, SchemaRouter, SchemaSourceError


def _base_info(entry_types: list[str]) -> dict:
    return {
        "data": {
            "type": "info",
            "id": "/",
            "attributes": {
                "api_version": "1.3.0",
                "available_api_versions": [],
                "formats": ["json"],
                "entry_types_by_format": {"json": entry_types},
                "available_endpoints": [*entry_types, "info", "links"],
                "is_index": False,
            },
        }
    }


@pytest.mark.asyncio
async def test_optimade_discovery_never_sends_runtime_credentials() -> None:
    seen_headers: list[httpx.Headers] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_headers.append(request.headers)
        if request.url == httpx.URL("https://materials.example/v1/info"):
            return httpx.Response(200, json=_base_info(["structures"]))
        if request.url == httpx.URL("https://materials.example/v1/info/structures"):
            return httpx.Response(
                200,
                json={
                    "data": {
                        "type": "info",
                        "id": "structures",
                        "description": "structures",
                        "formats": ["json"],
                        "properties": {
                            "nelements": {"type": ["integer", "null"]}
                        },
                        "output_fields_by_format": {"json": ["nelements"]},
                    }
                },
            )
        raise AssertionError(f"unexpected discovery request: {request.url}")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        await SchemaRouter.from_url(
            "https://materials.example",
            kind="optimade",
            schema_headers={"X-Schema-Key": "schema-secret"},
            trusted_headers={"Authorization": "Bearer runtime-secret"},
            http_client=client,
        )

    assert seen_headers
    for headers in seen_headers:
        assert headers["x-schema-key"] == "schema-secret"
        assert "authorization" not in headers


@pytest.mark.asyncio
async def test_optimade_rejects_unsafe_entry_type_paths() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url == httpx.URL("https://materials.example/v1/info"):
            return httpx.Response(200, json=_base_info(["../admin"]))
        raise AssertionError("unsafe entry type must not be requested")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        router = SchemaRouter(http_client=client)
        with pytest.raises(SchemaSourceError, match="no usable entry schemas"):
            await router.add_url(
                "https://materials.example",
                kind="optimade",
            )


@pytest.mark.asyncio
async def test_optimade_runtime_headers_are_not_model_parameters() -> None:
    discovery_done = False
    runtime_headers: list[httpx.Headers] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal discovery_done
        if request.url == httpx.URL("https://materials.example/v1/info"):
            return httpx.Response(200, json=_base_info(["structures"]))
        if request.url == httpx.URL("https://materials.example/v1/info/structures"):
            discovery_done = True
            return httpx.Response(
                200,
                json={
                    "data": {
                        "type": "info",
                        "id": "structures",
                        "description": "structures",
                        "formats": ["json"],
                        "properties": {
                            "nelements": {"type": ["integer", "null"]}
                        },
                        "output_fields_by_format": {"json": ["nelements"]},
                    }
                },
            )
        if request.url.path == "/v1/structures":
            runtime_headers.append(request.headers)
            return httpx.Response(
                200,
                content=json.dumps(
                    {
                        "data": [
                            {
                                "id": "1",
                                "type": "structures",
                                "attributes": {"nelements": 2},
                            }
                        ]
                    }
                ),
            )
        raise AssertionError(f"unexpected request: {request.url}")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        router = await SchemaRouter.from_url(
            "https://materials.example",
            kind="optimade",
            trusted_headers={"Authorization": "Bearer runtime-secret"},
            http_client=client,
        )
        endpoint = router.registry.endpoint("materials.example", "search_structures")
        assert "authorization" not in {parameter.name.casefold() for parameter in endpoint.parameters}

        plan = router.plan(
            PlanRequest(
                query="search nelements",
                arguments={"page_limit": 1},
            )
        )
        await router.execute(plan)

    assert discovery_done
    assert runtime_headers
    assert runtime_headers[0]["authorization"] == "Bearer runtime-secret"
