"""Raw validation and canonical contracts must describe their respective values."""
from __future__ import annotations

import json

import pytest
from jsonschema import Draft202012Validator

from schemarouter import (
    CapabilityFieldContract,
    EndpointSpec,
    FieldSpec,
    PlanRequest,
    SchemaRouter,
    SchemaValidationError,
    ToolSpec,
    UnitNormalizationSpec,
    compare_capability_fields,
)
from schemarouter.validation import canonical_field_value_schema, canonical_unit_value_schema


def _field(schema: dict, *, scale: float = .1, offset: float = 0) -> FieldSpec:
    return FieldSpec(
        name="length", semantic_id="length", json_schema=schema, unit="dm",
        unit_normalization=UnitNormalizationSpec(
            dimension="length", canonical_unit="m", scale=scale, offset=offset,
        ),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "raw_schema, raw, expected_schema",
    (
        ({"type": "integer", "minimum": 5, "maximum": 10}, 5,
         {"type": "number", "minimum": .5, "maximum": 1}),
        ({"type": "integer", "enum": [3, 5]}, 3,
         {"type": "number", "enum": [3 * .1, .5]}),
        ({"type": "integer", "const": -5}, -5,
         {"type": "number", "const": -.5}),
        ({"type": ["integer", "null"], "enum": [None, 5]}, None,
         {"type": ["number", "null"], "enum": [None, .5]}),
        ({"type": "array", "items": {"type": "integer", "minimum": 5}, "minItems": 1},
         [5], {"type": "array", "items": {"type": "number", "minimum": .5}, "minItems": 1}),
    ),
)
async def test_public_execution_round_trips_through_canonical_contract(
    raw_schema: dict, raw: object, expected_schema: dict,
) -> None:
    field = _field(raw_schema)
    endpoint = EndpointSpec(name="read", read_only=True, output_fields=[field])
    router = SchemaRouter()
    router.add_bound_tool(
        ToolSpec(name="lengths", endpoints=[endpoint]), lambda *_: {"length": raw},
    )
    plan = router.plan(PlanRequest(query="length", preferred_tools=["lengths"]))
    assert plan.executable and len(plan.calls) == 1
    result = (await router.execute(plan))[0]
    contract = CapabilityFieldContract.from_field(field)
    assert contract is not None and contract.unit == "m"
    assert contract.json_schema == expected_schema
    assert canonical_field_value_schema(endpoint, "length") == expected_schema
    Draft202012Validator(expected_schema).validate(result.data["length"])
    Draft202012Validator(result.field_contracts["length"].json_schema).validate(result.data["length"])
    assert field.json_schema == raw_schema, "Raw validation constraints must remain unchanged"


def test_canonical_bound_requirement_cannot_reuse_source_bounds() -> None:
    raw_schema = {"type": "integer", "minimum": 5, "maximum": 10}
    produced = CapabilityFieldContract.from_field(_field(raw_schema))
    assert produced is not None
    required = CapabilityFieldContract(
        semantic_id="length", unit="m", dimension="length",
        json_schema={"type": "number", "minimum": 5, "maximum": 10},
    )
    assert not compare_capability_fields(required, produced).satisfies
    required.json_schema = {"type": "number", "minimum": .5, "maximum": 1.0}
    assert compare_capability_fields(required, produced).satisfies


@pytest.mark.asyncio
async def test_public_execution_still_validates_raw_values_before_conversion() -> None:
    field = _field({"type": "integer", "minimum": 5, "maximum": 10})
    router = SchemaRouter()
    router.add_bound_tool(
        ToolSpec(name="lengths", endpoints=[
            EndpointSpec(name="read", read_only=True, output_fields=[field]),
        ]), lambda *_: {"length": .5},
    )
    plan = router.plan(PlanRequest(query="length", preferred_tools=["lengths"]))
    with pytest.raises(SchemaValidationError):
        await router.execute(plan)


@pytest.mark.parametrize(
    "schema, scale, offset, value, expected",
    (
        ({"type": "integer", "minimum": -5, "maximum": 5}, 2, -3, -5,
         {"type": "number", "minimum": -13, "maximum": 7}),
        ({"type": "integer", "const": -5}, .1, 1.3, -5,
         {"type": "number", "const": .8}),
        ({"type": ["integer", "null"], "enum": [None, -5, 5]}, .1, -1, -5,
         {"type": ["number", "null"], "enum": [None, -1.5, -.5]}),
        ({"type": "number", "minimum": 1, "exclusiveMinimum": 2}, .1, 0, 3,
         {"type": "number", "minimum": .2}),
        ({"type": "number", "exclusiveMinimum": 1}, .1, 1e20, 2,
         {"type": "number", "minimum": 1e20}),
        ({"type": "number", "exclusiveMaximum": 3}, .1, 1e20, 2,
         {"type": "number", "maximum": 1e20}),
        ({"type": "number", "minimum": 1e308, "maximum": 1e308}, 10, 0, 1,
         {"type": "number"}),
        ({"type": "number", "enum": [1e308]}, 10, 0, 1,
         {"type": "number"}),
        ({"type": "number", "const": 1e308}, 10, 0, 1,
         {"type": "number"}),
        ({"type": "number", "minimum": float("nan"), "maximum": float("inf")}, .1, 0, 1,
         {"type": "number"}),
        ({"type": "integer", "const": True}, .1, 0, 1,
         {"type": "number"}),
        ({"type": "integer", "enum": [True, 1], "minimum": False}, .1, 0, 1,
         {"type": "number"}),
    ),
)
def test_canonical_schema_is_finite_and_sound_under_rounding(
    schema: dict, scale: float, offset: float, value: float, expected: dict,
) -> None:
    field = _field(schema, scale=scale, offset=offset)
    canonical = canonical_unit_value_schema(schema, field.unit_normalization)
    assert canonical == expected
    json.dumps(canonical, allow_nan=False)
    Draft202012Validator(canonical).validate(value * scale + offset)
    assert not Draft202012Validator(canonical).is_valid(True)


@pytest.mark.parametrize("unsupported", (
    {"multipleOf": 2}, {"allOf": [{"maximum": 5}]}, {"$ref": "#/$defs/raw"},
))
def test_unproven_predicates_stay_raw_and_do_not_certify_canonical_requirements(
    unsupported: dict,
) -> None:
    field = _field({"type": "integer", **unsupported}, offset=.3)
    produced = CapabilityFieldContract.from_field(field)
    assert produced is not None and produced.json_schema == {"type": "number"}
    required = produced.model_copy(update={"json_schema": {"type": "number", **unsupported}})
    assert compare_capability_fields(required, produced).status == "unknown"
    assert field.json_schema == {"type": "integer", **unsupported}


def test_identity_normalization_preserves_integer_assertions_and_detaches_schema() -> None:
    field = _field({"type": "integer", "minimum": 5, "multipleOf": 2}, scale=1)
    contract = CapabilityFieldContract.from_field(field)
    assert contract is not None and contract.json_schema == field.json_schema
    contract.json_schema["minimum"] = 10
    assert field.json_schema["minimum"] == 5


def test_affine_rounding_does_not_reuse_raw_array_uniqueness() -> None:
    schema = {"type": "array", "items": {"type": "integer"}, "uniqueItems": True}
    field = _field(schema, offset=1e20)
    canonical = canonical_unit_value_schema(schema, field.unit_normalization)
    normalized = [value * .1 + 1e20 for value in [1, 2]]
    assert normalized[0] == normalized[1]
    assert canonical == {"type": "array", "items": {"type": "number"}}
    Draft202012Validator(canonical).validate(normalized)


@pytest.mark.asyncio
@pytest.mark.parametrize("raw", (9007199254740993, -9007199254740993, 10 ** 400))
async def test_public_identity_normalization_preserves_large_integer_const(raw: int) -> None:
    schema = {"type": "integer", "const": raw}
    field = _field(schema, scale=1)
    router = SchemaRouter()
    router.add_bound_tool(
        ToolSpec(name="lengths", endpoints=[
            EndpointSpec(name="read", read_only=True, output_fields=[field]),
        ]), lambda *_: {"length": raw},
    )
    result = (await router.ainvoke(PlanRequest(
        query="length", preferred_tools=["lengths"],
    )))[0]
    value = result.data["length"]
    assert type(value) is int and value == raw
    contract = CapabilityFieldContract.from_field(field)
    assert contract is not None and contract.json_schema == schema
    Draft202012Validator(contract.json_schema).validate(value)


@pytest.mark.asyncio
@pytest.mark.parametrize("raw", (float("nan"), float("inf"), float("-inf")))
async def test_public_identity_normalization_rejects_non_finite_provider_values(raw: float) -> None:
    field = _field({"type": "number"}, scale=1)
    router = SchemaRouter()
    router.add_bound_tool(
        ToolSpec(name="lengths", endpoints=[
            EndpointSpec(name="read", read_only=True, output_fields=[field]),
        ]), lambda *_: {"length": raw},
    )
    with pytest.raises(SchemaValidationError, match="non-finite normalized value"):
        await router.ainvoke(PlanRequest(query="length", preferred_tools=["lengths"]))
