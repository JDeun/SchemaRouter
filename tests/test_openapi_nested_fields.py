from __future__ import annotations

from schemarouter.adapters.openapi import tool_from_openapi
from schemarouter.models import EndpointSpec, FieldSpec


def _document(response_schema: dict) -> dict:
    return {
        "openapi": "3.1.0",
        "info": {"title": "Nested materials", "version": "1.0.0"},
        "paths": {
            "/materials": {
                "get": {
                    "operationId": "get_materials",
                    "responses": {
                        "200": {
                            "description": "ok",
                            "content": {
                                "application/json": {
                                    "schema": response_schema,
                                }
                            },
                        }
                    },
                }
            }
        },
    }


def test_openapi_discovers_nested_object_fields_without_hiding_parent() -> None:
    tool = tool_from_openapi(
        "materials",
        _document(
            {
                "type": "object",
                "properties": {
                    "data": {
                        "type": "object",
                        "description": "Material properties",
                        "properties": {
                            "band_gap": {
                                "type": "number",
                                "description": "Electronic band gap",
                                "x-unit": "eV",
                            },
                            "density": {
                                "type": "number",
                                "x-unit": "g/cm^3",
                            },
                        },
                    },
                    "meta": {"type": "object"},
                },
            }
        ),
    )

    endpoint = tool.endpoint("get_materials")
    fields = {field.name: field for field in endpoint.output_fields}

    assert {"data", "meta", "data.band_gap", "data.density"} <= set(fields)
    assert fields["data.band_gap"].path == ["data", "band_gap"]
    assert fields["data.band_gap"].result_path == ["data.band_gap"]
    assert fields["data.band_gap"].json_schema["type"] == "number"
    assert fields["data.band_gap"].unit == "eV"
    assert "band gap" in fields["data.band_gap"].aliases


def test_nested_array_items_remain_opaque_until_item_projection_is_defined() -> None:
    tool = tool_from_openapi(
        "materials",
        _document(
            {
                "type": "object",
                "properties": {
                    "data": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "band_gap": {"type": "number"},
                                "density": {"type": "number"},
                            },
                        },
                    }
                },
            }
        ),
    )

    fields = {
        field.name
        for field in tool.endpoint("get_materials").output_fields
    }
    assert "data" in fields
    assert "data.band_gap" not in fields
    assert "data.density" not in fields


def test_recursive_local_ref_discovery_is_bounded() -> None:
    document = _document(
        {
            "type": "object",
            "properties": {
                "node": {"$ref": "#/components/schemas/Node"},
            },
        }
    )
    document["components"] = {
        "schemas": {
            "Node": {
                "type": "object",
                "properties": {
                    "value": {"type": "number"},
                    "next": {"$ref": "#/components/schemas/Node"},
                },
            }
        }
    }

    tool = tool_from_openapi("materials", document)
    fields = {
        field.name
        for field in tool.endpoint("get_materials").output_fields
    }

    assert "node" in fields
    assert "node.value" in fields
    assert "node.next" in fields
    assert not any(name.startswith("node.next.") for name in fields)


def test_endpoint_allows_overlapping_source_paths_with_disjoint_results() -> None:
    endpoint = EndpointSpec(
        name="nested",
        output_schema={
            "type": "object",
            "properties": {
                "data": {
                    "type": "object",
                    "properties": {
                        "band_gap": {"type": "number"},
                    },
                }
            },
        },
        output_fields=[
            FieldSpec(
                name="data",
                json_schema={
                    "type": "object",
                    "properties": {"band_gap": {"type": "number"}},
                },
            ),
            FieldSpec(
                name="data.band_gap",
                path=["data", "band_gap"],
                result_path=["data.band_gap"],
                json_schema={"type": "number"},
            ),
        ],
    )

    assert endpoint.output_fields[1].projection_path == ("data", "band_gap")
    assert endpoint.output_fields[1].result_projection_path == ("data.band_gap",)
