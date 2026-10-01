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


def test_nested_array_items_are_record_preserving_first_class_fields() -> None:
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
        field.name: field
        for field in tool.endpoint("get_materials").output_fields
    }
    assert {"data", "data[].band_gap", "data[].density"} <= set(fields)
    assert fields["data[].band_gap"].path == ["data", "*", "band_gap"]
    assert fields["data[].band_gap"].result_path == ["data", "*", "band_gap"]
    assert fields["data[].band_gap"].json_schema["type"] == "number"


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


def test_nested_field_unit_and_type_contract_are_preserved() -> None:
    tool = tool_from_openapi(
        "materials",
        _document(
            {
                "type": "object",
                "properties": {
                    "data": {
                        "type": "object",
                        "properties": {
                            "band_gap": {
                                "type": "number",
                                "description": "Electronic band gap",
                                "x-ucum-unit": "eV",
                            }
                        },
                    }
                },
            }
        ),
    )

    field = {
        item.name: item
        for item in tool.endpoint("get_materials").output_fields
    }["data.band_gap"]

    assert field.json_schema["type"] == "number"
    assert field.unit == "eV"
    assert field.path == ["data", "band_gap"]


def test_parent_query_does_not_implicitly_select_nested_leaf() -> None:
    from schemarouter import InMemoryRegistry, PlanRequest, SchemaPlanner

    tool = tool_from_openapi(
        "materials",
        _document(
            {
                "type": "object",
                "properties": {
                    "profile": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                        },
                    }
                },
            }
        ),
    )
    registry = InMemoryRegistry()
    registry.register(tool)
    planner = SchemaPlanner(registry)

    plan = planner.plan(PlanRequest(query="profile"))

    assert plan.calls[0].fields == ["profile"]


def test_leaf_query_can_select_nested_leaf_without_parent_token_leakage() -> None:
    from schemarouter import InMemoryRegistry, PlanRequest, SchemaPlanner

    tool = tool_from_openapi(
        "materials",
        _document(
            {
                "type": "object",
                "properties": {
                    "profile": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                        },
                    }
                },
            }
        ),
    )
    registry = InMemoryRegistry()
    registry.register(tool)
    planner = SchemaPlanner(registry)

    plan = planner.plan(PlanRequest(query="name"))

    assert "profile.name" in plan.calls[0].fields


def test_nested_field_can_receive_full_trusted_contract_enrichment() -> None:
    from schemarouter import EndpointSpec, FieldSpec, SchemaRouter, ToolSpec

    tool = tool_from_openapi(
        "materials",
        _document(
            {
                "type": "object",
                "properties": {
                    "data": {
                        "type": "object",
                        "properties": {
                            "band_gap": {
                                "type": "number",
                                "x-ucum-unit": "eV",
                            }
                        },
                    }
                },
            }
        ),
    )
    endpoint = tool.endpoint("get_materials")
    fields = []
    for field in endpoint.output_fields:
        if field.name != "data.band_gap":
            fields.append(field)
            continue
        payload = field.model_dump(mode="python")
        payload.update(
            {
                "semantic_id": "materials.band_gap",
                "unit_normalization": {
                    "dimension": "energy",
                    "canonical_unit": "eV",
                    "scale": 1.0,
                    "offset": 0.0,
                },
                "qualifiers": {"temperature": "300 K"},
                "source_type": "materials_api",
                "license": "CC-BY-4.0",
            }
        )
        fields.append(FieldSpec.model_validate(payload))

    endpoint_payload = endpoint.model_dump(mode="python")
    endpoint_payload["output_fields"] = fields
    amended_endpoint = EndpointSpec.model_validate(endpoint_payload)

    tool_payload = tool.model_dump(mode="python")
    tool_payload["endpoints"] = [amended_endpoint]
    amended_tool = ToolSpec.model_validate(tool_payload)

    router = SchemaRouter()
    router.add_tool(tool)
    router.amend_capability(tool.key, amended_tool)

    enriched = {
        field.name: field
        for field in router.registry.get(tool.key).endpoint("get_materials").output_fields
    }["data.band_gap"]

    assert enriched.semantic_id == "materials.band_gap"
    assert enriched.unit == "eV"
    assert enriched.unit_normalization is not None
    assert enriched.unit_normalization.dimension == "energy"
    assert enriched.qualifiers == {"temperature": "300 K"}
    assert enriched.source_type == "materials_api"
    assert enriched.license == "CC-BY-4.0"
