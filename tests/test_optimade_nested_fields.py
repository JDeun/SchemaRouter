from __future__ import annotations

import httpx
import pytest

from schemarouter import (
    EndpointSpec,
    FieldSpec,
    PlanRequest,
    SchemaRouter,
    ToolSpec,
)


def _base_info() -> dict:
    return {
        "data": {
            "type": "info",
            "id": "/",
            "attributes": {
                "api_version": "1.3.0",
                "available_api_versions": [
                    {
                        "url": "https://materials.example/v1",
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


def _structures_info() -> dict:
    return {
        "data": {
            "type": "info",
            "id": "structures",
            "description": "materials structures",
            "formats": ["json"],
            "properties": {
                "metadata": {
                    "type": ["dictionary", "null"],
                    "description": "Provider metadata",
                    "properties": {
                        "score": {
                            "type": "float",
                            "description": "Model score",
                            "x-optimade-unit": "eV",
                        },
                        "label": {
                            "type": "string",
                            "description": "Model label",
                        },
                    },
                },
                "trajectories": {
                    "type": ["list", "null"],
                    "items": {
                        "type": "dictionary",
                        "properties": {
                            "energy": {"type": "float"},
                        },
                    },
                },
            },
            "output_fields_by_format": {
                "json": ["metadata", "trajectories"],
            },
        }
    }


def _handler(
    *,
    response_attributes: dict | None = None,
    seen_queries: list[dict[str, str]] | None = None,
):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url == httpx.URL("https://materials.example/v1/info"):
            return httpx.Response(200, json=_base_info(), request=request)
        if request.url == httpx.URL("https://materials.example/v1/info/structures"):
            return httpx.Response(200, json=_structures_info(), request=request)
        if request.url.path == "/v1/structures":
            if seen_queries is not None:
                seen_queries.append(dict(request.url.params))
            return httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "id": "s-1",
                            "type": "structures",
                            "attributes": response_attributes
                            or {
                                "metadata": {
                                    "score": 1.25,
                                    "label": "stable",
                                },
                            },
                        }
                    ]
                },
                request=request,
            )
        raise AssertionError(f"unexpected request: {request.url}")

    return handler


@pytest.mark.asyncio
async def test_optimade_discovers_nested_dictionary_fields_and_units() -> None:
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(_handler())
    ) as client:
        router = await SchemaRouter.from_url(
            "https://materials.example/v1",
            kind="optimade",
            http_client=client,
        )

    endpoint = router.registry.endpoint("materials.example", "search_structures")
    fields = {field.name: field for field in endpoint.output_fields}

    assert {"metadata", "metadata.score", "metadata.label", "trajectories"} <= set(fields)
    assert "trajectories.energy" not in fields
    assert fields["metadata.score"].path == ["metadata", "score"]
    assert fields["metadata.score"].result_path == ["metadata.score"]
    assert fields["metadata.score"].json_schema["type"] == "number"
    assert fields["metadata.score"].unit == "eV"
    assert fields["metadata.score"].source_type == "optimade"

    raw_properties = endpoint.output_schema["items"]["properties"]
    assert "metadata" in raw_properties
    assert "metadata.score" not in raw_properties


@pytest.mark.asyncio
async def test_optimade_nested_projection_requests_parent_wire_field_only() -> None:
    seen_queries: list[dict[str, str]] = []

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(_handler(seen_queries=seen_queries))
    ) as client:
        router = await SchemaRouter.from_url(
            "https://materials.example/v1",
            kind="optimade",
            http_client=client,
        )
        plan = router.plan(
            PlanRequest(
                query="score",
                preferred_tools=["materials.example"],
            )
        )
        call = next(
            call
            for call in plan.calls
            if call.endpoint == "search_structures"
        )
        call.fields = ["id", "metadata.score"]

        results = await router.execute(
            plan.model_copy(update={"calls": [call]}, deep=True)
        )

    assert seen_queries == [
        {
            "response_fields": "metadata",
            "page_limit": "20",
        }
    ]
    assert results[0].data == [
        {
            "id": "s-1",
            "metadata.score": 1.25,
        }
    ]


@pytest.mark.asyncio
async def test_optimade_multiple_nested_children_deduplicate_parent_selector() -> None:
    seen_queries: list[dict[str, str]] = []

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(_handler(seen_queries=seen_queries))
    ) as client:
        router = await SchemaRouter.from_url(
            "https://materials.example/v1",
            kind="optimade",
            http_client=client,
        )
        plan = router.plan(
            PlanRequest(
                query="metadata",
                preferred_tools=["materials.example"],
            )
        )
        call = next(
            call
            for call in plan.calls
            if call.endpoint == "search_structures"
        )
        call.fields = ["metadata.score", "metadata.label"]

        results = await router.execute(
            plan.model_copy(update={"calls": [call]}, deep=True)
        )

    assert seen_queries == [
        {
            "response_fields": "metadata",
            "page_limit": "20",
        }
    ]
    assert results[0].data == [
        {
            "metadata.score": 1.25,
            "metadata.label": "stable",
        }
    ]


@pytest.mark.asyncio
async def test_optimade_nested_field_supports_trusted_enrichment() -> None:
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(_handler())
    ) as client:
        router = await SchemaRouter.from_url(
            "https://materials.example/v1",
            kind="optimade",
            http_client=client,
        )

    tool = router.registry.get("materials.example")
    endpoint = tool.endpoint("search_structures")
    fields: list[FieldSpec] = []
    for field in endpoint.output_fields:
        if field.name != "metadata.score":
            fields.append(field)
            continue
        payload = field.model_dump(mode="python")
        payload.update(
            {
                "semantic_id": "materials.model_score",
                "unit_normalization": {
                    "dimension": "energy",
                    "canonical_unit": "eV",
                    "scale": 1.0,
                    "offset": 0.0,
                },
                "qualifiers": {"temperature": "300 K"},
                "license": "CC-BY-4.0",
            }
        )
        fields.append(FieldSpec.model_validate(payload))

    endpoints: list[EndpointSpec] = []
    for item in tool.endpoints:
        if item.name != endpoint.name:
            endpoints.append(item)
            continue
        payload = item.model_dump(mode="python")
        payload["output_fields"] = fields
        endpoints.append(EndpointSpec.model_validate(payload))

    tool_payload = tool.model_dump(mode="python")
    tool_payload["endpoints"] = endpoints
    amended = ToolSpec.model_validate(tool_payload)

    router.amend_capability(tool.key, amended)

    enriched = {
        field.name: field
        for field in router.registry.endpoint(
            tool.key,
            "search_structures",
        ).output_fields
    }["metadata.score"]

    assert enriched.semantic_id == "materials.model_score"
    assert enriched.unit == "eV"
    assert enriched.unit_normalization is not None
    assert enriched.unit_normalization.dimension == "energy"
    assert enriched.qualifiers == {"temperature": "300 K"}
    assert enriched.license == "CC-BY-4.0"
