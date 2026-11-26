from __future__ import annotations

import httpx
import pytest

from schemarouter import (
    EndpointSpec,
    FieldSpec,
    SchemaRouter,
    SQLiteRegistry,
    ToolSpec,
    UnitNormalizationSpec,
)
from schemarouter.amendment_overlay import (
    amendment_overlay,
    strip_amendment_overlay,
)


def _document(
    *,
    summary: str | None = None,
    properties: dict | None = None,
) -> dict:
    properties = properties or {
        "id": {"type": "string"},
        "band_gap": {"type": "number"},
    }
    return {
        "openapi": "3.1.0",
        "info": {"title": "Amendment API", "version": "1.0.0"},
        "servers": [{"url": "https://example.test"}],
        "paths": {
            "/materials": {
                "get": {
                    "operationId": "materials_search",
                    "summary": summary,
                    "responses": {
                        "200": {
                            "description": "ok",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": properties,
                                    }
                                }
                            },
                        }
                    },
                }
            }
        },
    }


def _amend_with_local_field(router: SchemaRouter, key: str) -> None:
    current = router.registry.get(key)
    endpoint = current.endpoint("materials_search")
    local = FieldSpec(
        name="formation_energy",
        semantic_id="materials.formation_energy",
        json_schema={"type": "number"},
        unit="eV/atom",
        aliases=["formation energy"],
        source_type="declared",
    )
    amended_endpoint = endpoint.model_copy(
        update={"output_fields": [*endpoint.output_fields, local]}
    )
    amended = current.model_copy(
        update={
            "endpoints": [
                amended_endpoint
                if candidate.name == endpoint.name
                else candidate
                for candidate in current.endpoints
            ]
        }
    )
    router.amend_capability(key, amended)


def _annotate_band_gap(router: SchemaRouter, key: str) -> None:
    current = router.registry.get(key)
    endpoint = current.endpoint("materials_search")
    fields = []
    for field in endpoint.output_fields:
        if field.name != "band_gap":
            fields.append(field)
            continue
        fields.append(
            field.model_copy(
                update={
                    "semantic_id": "materials.band_gap",
                    "description": "Trusted local band-gap annotation",
                    "aliases": ["band gap"],
                    "path": ["band_gap"],
                    "result_path": ["band_gap"],
                    "unit": "eV",
                    "unit_normalization": UnitNormalizationSpec(
                        dimension="energy",
                        canonical_unit="eV",
                        scale=1.0,
                        offset=0.0,
                    ),
                    "qualifiers": {"authority": "local"},
                    "source_type": "measured",
                    "license": "CC-BY-4.0",
                }
            )
        )
    amended_endpoint = endpoint.model_copy(update={"output_fields": fields})
    amended = current.model_copy(
        update={
            "endpoints": [
                amended_endpoint
                if candidate.name == endpoint.name
                else candidate
                for candidate in current.endpoints
            ]
        }
    )
    router.amend_capability(key, amended)


@pytest.mark.asyncio
async def test_unchanged_provider_with_local_field_has_no_false_breaking_drift() -> None:
    state = {"document": _document()}

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=state["document"], request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        router = SchemaRouter(http_client=client)
        tool = await router.add_url(
            "https://example.test/openapi.json",
            kind="openapi",
            name="materials",
        )
        _amend_with_local_field(router, tool.key)
        amended = router.registry.get(tool.key)
        version = router.registry.version

        result = await router.arefresh_schema(tool.key)

    assert result.action == "unchanged"
    assert result.compatibility == "identical"
    assert router.registry.version == version
    current = router.registry.get(tool.key)
    assert current.fingerprint == amended.fingerprint
    assert "formation_energy" in {
        field.name for field in current.endpoint("materials_search").output_fields
    }


@pytest.mark.asyncio
async def test_compatible_provider_change_applies_and_preserves_local_overlay() -> None:
    state = {"document": _document()}

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=state["document"], request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        router = SchemaRouter(http_client=client)
        tool = await router.add_url(
            "https://example.test/openapi.json",
            kind="openapi",
            name="materials",
        )
        _amend_with_local_field(router, tool.key)
        state["document"] = _document(summary="Provider search summary")

        result = await router.arefresh_schema(tool.key)

    assert result.action == "applied"
    assert result.compatibility == "compatible"
    current = router.registry.get(tool.key)
    endpoint = current.endpoint("materials_search")
    assert endpoint.description == "Provider search summary"
    local = next(field for field in endpoint.output_fields if field.name == "formation_energy")
    assert local.semantic_id == "materials.formation_energy"
    assert local.unit == "eV/atom"
    assert amendment_overlay(current) is not None


@pytest.mark.asyncio
async def test_provider_removing_amendment_target_goes_pending_review() -> None:
    state = {"document": _document()}

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=state["document"], request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        router = SchemaRouter(http_client=client)
        tool = await router.add_url(
            "https://example.test/openapi.json",
            kind="openapi",
            name="materials",
        )
        _annotate_band_gap(router, tool.key)
        before = router.registry.get(tool.key)
        before_version = router.registry.version
        assert router.executor.is_binding_ready_for_contract(
            tool.key,
            before.fingerprint,
        )

        state["document"] = _document(
            properties={
                "id": {"type": "string"},
                "gap_ev": {"type": "number"},
            }
        )
        result = await router.arefresh_schema(tool.key)

    assert result.action == "pending_review"
    assert result.compatibility == "breaking"
    assert any(
        change.kind == "amendment_overlay_conflict"
        for change in result.report.changes
    )
    assert router.registry.version == before_version
    assert router.registry.get(tool.key).fingerprint == before.fingerprint
    assert router.executor.is_binding_ready_for_contract(
        tool.key,
        before.fingerprint,
    )


@pytest.mark.asyncio
async def test_semantic_unit_and_path_annotations_survive_refresh() -> None:
    state = {"document": _document()}

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=state["document"], request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        router = SchemaRouter(http_client=client)
        tool = await router.add_url(
            "https://example.test/openapi.json",
            kind="openapi",
            name="materials",
        )
        _annotate_band_gap(router, tool.key)
        state["document"] = _document(summary="Compatible provider change")

        result = await router.arefresh_schema(tool.key)

    assert result.action == "applied"
    field = next(
        field
        for field in router.registry.get(tool.key)
        .endpoint("materials_search")
        .output_fields
        if field.name == "band_gap"
    )
    assert field.semantic_id == "materials.band_gap"
    assert field.path == ["band_gap"]
    assert field.result_path == ["band_gap"]
    assert field.unit == "eV"
    assert field.unit_normalization is not None
    assert field.unit_normalization.canonical_unit == "eV"
    assert field.qualifiers == {"authority": "local"}


@pytest.mark.asyncio
async def test_binding_is_restamped_only_to_final_effective_contract() -> None:
    state = {"document": _document()}

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=state["document"], request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        router = SchemaRouter(http_client=client)
        tool = await router.add_url(
            "https://example.test/openapi.json",
            kind="openapi",
            name="materials",
        )
        _amend_with_local_field(router, tool.key)
        old_effective = router.registry.get(tool.key)
        state["document"] = _document(summary="Provider update")

        result = await router.arefresh_schema(tool.key)
        current = router.registry.get(tool.key)

    assert result.action == "applied"
    assert current.fingerprint != old_effective.fingerprint
    assert router.executor.is_binding_ready_for_contract(
        tool.key,
        current.fingerprint,
    )
    assert not router.executor.is_binding_ready_for_contract(
        tool.key,
        old_effective.fingerprint,
    )
    assert "formation_energy" in {
        field.name for field in current.endpoint("materials_search").output_fields
    }


@pytest.mark.asyncio
async def test_provider_baseline_change_hidden_by_overlay_is_persisted() -> None:
    state = {"document": _document(summary="Provider original")}

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=state["document"], request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        router = SchemaRouter(http_client=client)
        tool = await router.add_url(
            "https://example.test/openapi.json",
            kind="openapi",
            name="materials",
        )
        current = router.registry.get(tool.key)
        endpoint = current.endpoint("materials_search")
        amended_endpoint = endpoint.model_copy(
            update={"description": "Trusted local description"}
        )
        amended = current.model_copy(
            update={"endpoints": [amended_endpoint]}
        )
        router.amend_capability(tool.key, amended)
        effective_fingerprint = router.registry.get(tool.key).fingerprint

        state["document"] = _document(summary="Provider changed underneath overlay")
        result = await router.arefresh_schema(tool.key)
        current = router.registry.get(tool.key)
        raw = strip_amendment_overlay(current)

    assert result.action == "applied"
    assert current.fingerprint == effective_fingerprint
    assert current.endpoint("materials_search").description == "Trusted local description"
    assert raw.endpoint("materials_search").description == (
        "Provider changed underneath overlay"
    )


def test_sqlite_registry_preserves_reproducible_amendment_provenance(tmp_path) -> None:
    path = tmp_path / "registry.sqlite3"
    with SQLiteRegistry(path) as registry:
        router = SchemaRouter(registry=registry)
        key = router.add_tool(
            ToolSpec(
                name="persisted",
                endpoints=[
                    EndpointSpec(
                        name="read",
                        description="Provider description",
                        read_only=True,
                        output_fields=[
                            FieldSpec(
                                name="value",
                                json_schema={"type": "number"},
                            )
                        ],
                        output_schema={
                            "type": "object",
                            "properties": {"value": {"type": "number"}},
                        },
                    )
                ],
            )
        )
        current = router.registry.get(key)
        endpoint = current.endpoint("read")
        annotated = endpoint.output_fields[0].model_copy(
            update={
                "semantic_id": "example.value",
                "unit": "eV",
            }
        )
        amended = current.model_copy(
            update={
                "endpoints": [
                    endpoint.model_copy(update={"output_fields": [annotated]})
                ]
            }
        )
        router.amend_capability(key, amended)

    with SQLiteRegistry(path) as reopened:
        persisted = reopened.get("persisted")
        overlay = amendment_overlay(persisted)
        raw = strip_amendment_overlay(persisted)

    assert overlay is not None
    assert persisted.endpoint("read").output_fields[0].semantic_id == "example.value"
    assert persisted.endpoint("read").output_fields[0].unit == "eV"
    assert raw.endpoint("read").output_fields[0].semantic_id is None
    assert raw.endpoint("read").output_fields[0].unit is None
