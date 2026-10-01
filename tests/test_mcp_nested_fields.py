from __future__ import annotations

from schemarouter import (
    EndpointSpec,
    FieldSpec,
    InMemoryRegistry,
    PlanRequest,
    SchemaPlanner,
    SchemaRouter,
    ToolSpec,
)
from schemarouter.adapters.mcp import tool_from_mcp


def _tool(output_schema: dict) -> ToolSpec:
    return tool_from_mcp(
        "materials-mcp",
        [
            {
                "name": "lookup",
                "description": "Lookup materials",
                "inputSchema": {"type": "object", "properties": {}},
                "outputSchema": output_schema,
            }
        ],
    )


def test_mcp_discovers_nested_object_fields_and_units() -> None:
    tool = _tool(
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
                        },
                        "density": {
                            "type": "number",
                            "unit": "g/cm3",
                        },
                    },
                }
            },
        }
    )

    fields = {field.name: field for field in tool.endpoint("lookup").output_fields}

    assert {"data", "data.band_gap", "data.density"} <= set(fields)
    assert fields["data.band_gap"].path == ["data", "band_gap"]
    assert fields["data.band_gap"].result_path == ["data.band_gap"]
    assert fields["data.band_gap"].unit == "eV"
    assert fields["data.band_gap"].source_type == "mcp"
    assert fields["data.band_gap"].json_schema["type"] == "number"


def test_mcp_nested_arrays_expose_record_preserving_fields() -> None:
    tool = _tool(
        {
            "type": "object",
            "properties": {
                "data": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "band_gap": {"type": "number"},
                        },
                    },
                }
            },
        }
    )

    fields = {field.name: field for field in tool.endpoint("lookup").output_fields}
    assert {"data", "data[].band_gap"} <= set(fields)
    assert fields["data[].band_gap"].path == ["data", "*", "band_gap"]
    assert fields["data[].band_gap"].result_path == ["data", "*", "band_gap"]


def test_mcp_recursive_local_ref_is_bounded_without_descendant_chain() -> None:
    tool = _tool(
        {
            "type": "object",
            "properties": {
                "node": {"$ref": "#/$defs/Node"},
            },
            "$defs": {
                "Node": {
                    "type": "object",
                    "properties": {
                        "value": {"type": "number"},
                        "next": {"$ref": "#/$defs/Node"},
                    },
                }
            },
        }
    )

    names = {field.name for field in tool.endpoint("lookup").output_fields}
    assert "node" in names
    assert "node.value" in names
    assert "node.next" in names
    assert not any(name.startswith("node.next.") for name in names)


def test_mcp_parent_query_does_not_implicitly_select_nested_leaf() -> None:
    tool = _tool(
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
    )
    registry = InMemoryRegistry()
    registry.register(tool)
    planner = SchemaPlanner(registry)

    plan = planner.plan(PlanRequest(query="profile"))

    assert plan.calls[0].fields == ["profile"]


def test_mcp_nested_field_supports_full_trusted_enrichment() -> None:
    tool = _tool(
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
    )
    endpoint = tool.endpoint("lookup")
    amended_fields: list[FieldSpec] = []
    for field in endpoint.output_fields:
        if field.name != "data.band_gap":
            amended_fields.append(field)
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
                "source_type": "mcp-materials",
                "license": "CC-BY-4.0",
            }
        )
        amended_fields.append(FieldSpec.model_validate(payload))

    endpoint_payload = endpoint.model_dump(mode="python")
    endpoint_payload["output_fields"] = amended_fields
    amended_endpoint = EndpointSpec.model_validate(endpoint_payload)

    tool_payload = tool.model_dump(mode="python")
    tool_payload["endpoints"] = [amended_endpoint]
    amended_tool = ToolSpec.model_validate(tool_payload)

    router = SchemaRouter()
    router.add_tool(tool)
    router.amend_capability(tool.key, amended_tool)

    enriched = {
        field.name: field
        for field in router.registry.get(tool.key).endpoint("lookup").output_fields
    }["data.band_gap"]

    assert enriched.semantic_id == "materials.band_gap"
    assert enriched.unit == "eV"
    assert enriched.unit_normalization is not None
    assert enriched.unit_normalization.dimension == "energy"
    assert enriched.qualifiers == {"temperature": "300 K"}
    assert enriched.source_type == "mcp-materials"
    assert enriched.license == "CC-BY-4.0"
