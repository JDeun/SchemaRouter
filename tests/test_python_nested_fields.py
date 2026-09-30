from __future__ import annotations

from pydantic import BaseModel, Field

from schemarouter import (
    EndpointSpec,
    FieldSpec,
    InMemoryRegistry,
    PlanRequest,
    SchemaPlanner,
    SchemaRouter,
    ToolSpec,
    tool_from_callable,
)


class Metrics(BaseModel):
    band_gap: float = Field(
        description="Electronic band gap",
        json_schema_extra={"x-ucum-unit": "eV"},
    )
    density: float


class MaterialResult(BaseModel):
    material_id: str
    metrics: Metrics


def lookup_material() -> MaterialResult:
    return MaterialResult(
        material_id="mp-1",
        metrics=Metrics(
            band_gap=1.25,
            density=2.5,
        ),
    )


def test_python_adapter_discovers_nested_typed_return_fields() -> None:
    tool = tool_from_callable(lookup_material)
    fields = {field.name: field for field in tool.endpoint("call").output_fields}

    assert {"material_id", "metrics", "metrics.band_gap", "metrics.density"} <= set(fields)
    assert fields["metrics.band_gap"].path == ["metrics", "band_gap"]
    assert fields["metrics.band_gap"].result_path == ["metrics.band_gap"]
    assert fields["metrics.band_gap"].json_schema["type"] == "number"
    assert fields["metrics.band_gap"].unit == "eV"
    assert fields["metrics.band_gap"].source_type == "python"


def test_python_parent_query_does_not_implicitly_select_nested_leaf() -> None:
    tool = tool_from_callable(lookup_material)
    registry = InMemoryRegistry()
    registry.register(tool)
    planner = SchemaPlanner(registry)

    plan = planner.plan(PlanRequest(query="metrics"))

    assert "metrics" in plan.calls[0].fields
    assert "metrics.band_gap" not in plan.calls[0].fields
    assert "metrics.density" not in plan.calls[0].fields


def test_python_nested_field_supports_trusted_enrichment() -> None:
    tool = tool_from_callable(lookup_material)
    endpoint = tool.endpoint("call")
    fields: list[FieldSpec] = []
    for field in endpoint.output_fields:
        if field.name != "metrics.band_gap":
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
                "license": "internal-contract",
            }
        )
        fields.append(FieldSpec.model_validate(payload))

    endpoint_payload = endpoint.model_dump(mode="python")
    endpoint_payload["output_fields"] = fields
    amended_endpoint = EndpointSpec.model_validate(endpoint_payload)

    tool_payload = tool.model_dump(mode="python")
    tool_payload["endpoints"] = [amended_endpoint]
    amended = ToolSpec.model_validate(tool_payload)

    router = SchemaRouter()
    router.add_tool(tool)
    router.amend_capability(tool.key, amended)

    enriched = {
        field.name: field
        for field in router.registry.endpoint(tool.key, "call").output_fields
    }["metrics.band_gap"]

    assert enriched.semantic_id == "materials.band_gap"
    assert enriched.unit == "eV"
    assert enriched.unit_normalization is not None
    assert enriched.unit_normalization.dimension == "energy"
    assert enriched.qualifiers == {"temperature": "300 K"}
    assert enriched.license == "internal-contract"
