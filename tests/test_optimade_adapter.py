import json

import httpx
import pytest

from schemarouter import PlanRequest, SchemaRouter, SchemaSourceError


def base_info() -> dict:
    return {
        "data": {
            "type": "info",
            "id": "/",
            "attributes": {
                "api_version": "1.3.0",
                "available_api_versions": [
                    {
                        "url": "https://materials.example/optimade/v1",
                        "version": "1.3.0",
                    }
                ],
                "formats": ["json"],
                "entry_types_by_format": {
                    "json": ["structures", "references"],
                },
                "available_endpoints": [
                    "structures",
                    "references",
                    "info",
                    "links",
                ],
                "is_index": False,
            },
        }
    }


def structures_info() -> dict:
    return {
        "data": {
            "type": "info",
            "id": "structures",
            "description": "materials structures",
            "formats": ["json"],
            "properties": {
                "chemical_formula_descriptive": {
                    "type": ["string", "null"],
                    "description": "Human-readable chemical formula.",
                    "x-optimade-type": "string",
                },
                "nelements": {
                    "type": ["integer", "null"],
                    "description": "Number of chemical elements.",
                    "x-optimade-type": "integer",
                },
                "_demo_band_gap": {
                    "type": ["number", "null"],
                    "description": "Provider-specific electronic band gap.",
                    "x-optimade-unit": "eV",
                },
            },
            "output_fields_by_format": {
                "json": [
                    "chemical_formula_descriptive",
                    "nelements",
                    "_demo_band_gap",
                ]
            },
        }
    }


def references_info() -> dict:
    return {
        "data": {
            "type": "info",
            "id": "references",
            "description": "bibliographic references",
            "formats": ["json"],
            "properties": {
                "title": {
                    "type": ["string", "null"],
                    "description": "Reference title.",
                }
            },
            "output_fields_by_format": {"json": ["title"]},
        }
    }


@pytest.mark.asyncio
async def test_optimade_discovery_planning_and_execution_use_response_fields() -> None:
    seen_queries: list[dict[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url == httpx.URL("https://materials.example/optimade/v1/info"):
            return httpx.Response(
                200,
                content=json.dumps(base_info()),
                headers={"content-type": "application/vnd.api+json"},
            )
        if request.url == httpx.URL(
            "https://materials.example/optimade/v1/info/structures"
        ):
            return httpx.Response(
                200,
                content=json.dumps(structures_info()),
                headers={"content-type": "application/vnd.api+json"},
            )
        if request.url == httpx.URL(
            "https://materials.example/optimade/v1/info/references"
        ):
            return httpx.Response(
                200,
                content=json.dumps(references_info()),
                headers={"content-type": "application/vnd.api+json"},
            )
        if request.url.path == "/optimade/v1/structures":
            seen_queries.append(dict(request.url.params))
            return httpx.Response(
                200,
                content=json.dumps(
                    {
                        "data": [
                            {
                                "id": "s-1",
                                "type": "structures",
                                "attributes": {
                                    "chemical_formula_descriptive": "O2Si",
                                },
                            }
                        ],
                        "meta": {"data_returned": 1},
                    }
                ),
                headers={"content-type": "application/vnd.api+json"},
            )
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        router = await SchemaRouter.from_url(
            "https://materials.example/optimade",
            kind="optimade",
            http_client=client,
        )

        assert router.adapter_registry.kinds() == ("mcp", "openapi", "optimade")
        tool = router.registry.get("materials.example")
        assert tool.metadata["adapter"] == "optimade"
        assert tool.metadata["api_version"] == "1.3.0"
        assert {
            endpoint.name
            for endpoint in tool.endpoints
        } == {
            "search_structures",
            "get_structures",
            "search_references",
            "get_references",
        }

        structures = router.registry.endpoint(
            "materials.example",
            "search_structures",
        )
        fields = {field.name: field for field in structures.output_fields}
        assert fields["_demo_band_gap"].unit == "eV"
        assert fields["_demo_band_gap"].source_type == "optimade"

        request = PlanRequest(
            query="chemical formula",
            preferred_tools=["materials.example"],
            arguments={
                "filter": 'elements HAS ALL "Si","O" AND nelements=2',
                "page_limit": 1,
            },
        )
        plan = router.plan(request)
        assert plan.executable
        assert plan.calls[0].endpoint == "search_structures"
        assert "chemical_formula_descriptive" in plan.calls[0].fields

        results = await router.execute(plan)

    assert results[0].data == [
        {
            "id": "s-1",
            "type": "structures",
            "chemical_formula_descriptive": "O2Si",
        }
    ]
    assert seen_queries == [
        {
            "filter": 'elements HAS ALL "Si","O" AND nelements=2',
            "page_limit": "1",
            "response_fields": "chemical_formula_descriptive",
        }
    ]


@pytest.mark.asyncio
async def test_optimade_single_entry_uses_encoded_id_and_field_projection() -> None:
    requested_urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url == httpx.URL("https://materials.example/v1/info"):
            return httpx.Response(200, json=base_info())
        if request.url == httpx.URL("https://materials.example/v1/info/structures"):
            return httpx.Response(200, json=structures_info())
        if request.url == httpx.URL("https://materials.example/v1/info/references"):
            return httpx.Response(200, json=references_info())
        if request.url.path.startswith("/v1/structures/"):
            requested_urls.append(str(request.url))
            return httpx.Response(
                200,
                json={
                    "data": {
                        "id": "db/42",
                        "type": "structures",
                        "attributes": {"nelements": 2},
                    }
                },
            )
        raise AssertionError(f"unexpected request: {request.url}")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        router = await SchemaRouter.from_url(
            "https://materials.example/v1",
            kind="optimade",
            http_client=client,
        )
        plan = router.plan(
            PlanRequest(
                query="structure elements",
                preferred_tools=["materials.example"],
                arguments={"id": "db/42"},
            )
        )
        get_call = next(call for call in plan.calls if call.endpoint == "get_structures")
        get_call.fields = ["id", "nelements"]
        results = await router.execute(
            plan.model_copy(update={"calls": [get_call]}, deep=True)
        )

    assert results[0].data == {
        "id": "db/42",
        "type": "structures",
        "nelements": 2,
    }
    assert "%2F" in requested_urls[0]


@pytest.mark.asyncio
async def test_optimade_index_metadatabase_is_not_silently_executable() -> None:
    document = base_info()
    document["data"]["attributes"]["is_index"] = True
    document["data"]["attributes"]["entry_types_by_format"] = {"json": []}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url == httpx.URL("https://index.example/v1/info"):
            return httpx.Response(200, json=document)
        return httpx.Response(404)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        router = SchemaRouter(http_client=client)
        with pytest.raises(SchemaSourceError, match="index meta-databases"):
            await router.add_url(
                "https://index.example",
                kind="optimade",
            )


@pytest.mark.asyncio
async def test_optimade_accepts_legacy_entry_info_without_type_or_id() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url == httpx.URL("https://materials.example/v1/info"):
            return httpx.Response(200, json=base_info())
        if request.url == httpx.URL("https://materials.example/v1/info/structures"):
            document = structures_info()
            data = document["data"]
            data.pop("type")
            data.pop("id")
            return httpx.Response(200, json=document)
        if request.url == httpx.URL("https://materials.example/v1/info/references"):
            document = references_info()
            data = document["data"]
            data.pop("type")
            data.pop("id")
            return httpx.Response(200, json=document)
        raise AssertionError(f"unexpected request: {request.url}")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        router = await SchemaRouter.from_url(
            "https://materials.example",
            kind="optimade",
            http_client=client,
        )

    tool = router.registry.get("materials.example")
    assert set(tool.metadata["inferred_entry_info_identity"]) == {
        "structures",
        "references",
    }
    assert router.registry.endpoint("materials.example", "search_structures")


@pytest.mark.asyncio
async def test_optimade_rejects_conflicting_entry_info_identity() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url == httpx.URL("https://materials.example/v1/info"):
            return httpx.Response(200, json=base_info())
        if request.url == httpx.URL("https://materials.example/v1/info/structures"):
            document = structures_info()
            document["data"]["id"] = "references"
            return httpx.Response(200, json=document)
        if request.url == httpx.URL("https://materials.example/v1/info/references"):
            document = references_info()
            document["data"]["type"] = "structures"
            return httpx.Response(200, json=document)
        raise AssertionError(f"unexpected request: {request.url}")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        router = SchemaRouter(http_client=client)
        with pytest.raises(SchemaSourceError, match="no usable entry schemas"):
            await router.add_url(
                "https://materials.example",
                kind="optimade",
            )
