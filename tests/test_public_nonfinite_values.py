"""Schema-bound public values must survive JSON serialization without numeric corruption."""
from __future__ import annotations

import json
import math
from decimal import Decimal

import pytest

from schemarouter import (
    EndpointSpec,
    ParameterSpec,
    PlanRequest,
    SchemaRouter,
    SchemaValidationError,
    ToolSpec,
)

NONFINITE = (float("nan"), float("inf"), -float("inf"))
INVALID_NUMBERS = tuple((number, "non-finite") for number in (
    *NONFINITE, Decimal("NaN"), Decimal("sNaN"), Decimal("Infinity"), Decimal("-Infinity"),
)) + tuple((number, "non-real") for number in (complex(1, 2), complex(1, 0)))
SECRET = "provider-private-do-not-echo"


def _shape(name, number):
    if name == "scalar":
        return {"type": "number"}, number
    if name == "array":
        return {"type": "array", "items": {"type": "number"}}, [number]
    if name == "nested":
        return {
            "type": "object", "properties": {"temperature": {"type": "number"}},
        }, {"temperature": number, "provider_secret": SECRET}
    if name == "nested_array":
        return {
            "type": "array", "items": {
                "type": "object", "properties": {"temperature": {"type": "number"}},
            },
        }, [{"temperature": number, "provider_secret": SECRET}]
    raise ValueError(name)


@pytest.mark.asyncio
@pytest.mark.parametrize(("number", "reason"), INVALID_NUMBERS)
@pytest.mark.parametrize("shape", ("scalar", "array", "nested", "nested_array"))
async def test_public_nonfinite_inputs_are_rejected_before_native_dispatch(number, reason, shape):
    schema, value = _shape(shape, number)
    router = SchemaRouter()
    invoked = []

    def invoke(endpoint, arguments):
        invoked.append(arguments)
        return 42

    router.add_bound_tool(ToolSpec(name="numbers", endpoints=[EndpointSpec(
        name="read", read_only=True,
        parameters=[ParameterSpec(name="value", required=True, json_schema=schema)],
        output_schema={"type": "number"},
    )]), invoke)
    with pytest.raises(SchemaValidationError, match=reason) as error:
        await router.ainvoke(PlanRequest(
            query="temperature", preferred_tools=["numbers"], arguments={"value": value},
        ))
    assert invoked == []
    assert "arguments for numbers.read" in str(error.value)
    assert SECRET not in str(error.value)
    assert str(error.value) == (
        f"arguments for numbers.read: {reason} numeric values are not permitted"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(("number", "reason"), INVALID_NUMBERS)
@pytest.mark.parametrize("shape", ("scalar", "array", "nested", "nested_array"))
async def test_public_nonfinite_outputs_are_rejected_without_echoing_payload(number, reason, shape):
    schema, value = _shape(shape, number)
    router = SchemaRouter()
    invoked = []

    def invoke(endpoint, arguments):
        invoked.append(endpoint)
        return value

    router.add_bound_tool(ToolSpec(name="numbers", endpoints=[EndpointSpec(
        name="read", read_only=True, output_schema=schema,
    )]), invoke)
    with pytest.raises(SchemaValidationError, match=reason) as error:
        await router.ainvoke(PlanRequest(query="temperature", preferred_tools=["numbers"]))
    assert invoked == ["read"]
    assert "output from numbers.read" in str(error.value)
    assert SECRET not in str(error.value)
    assert str(error.value) == (
        f"output from numbers.read: {reason} numeric values are not permitted"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("value", (9007199254740993, 10 ** 400 + 1, -(10 ** 400 + 1), .5, None))
async def test_public_schema_bound_numbers_preserve_huge_int_precision_and_null(value):
    schema = {"type": ["number", "null"]}
    router = SchemaRouter()
    invoked = []

    def invoke(endpoint, arguments):
        invoked.append(arguments["value"])
        return arguments["value"]

    router.add_bound_tool(ToolSpec(name="numbers", endpoints=[EndpointSpec(
        name="read", read_only=True,
        parameters=[ParameterSpec(name="value", required=True, json_schema=schema)],
        output_schema=schema,
    )]), invoke)
    result, = await router.ainvoke(PlanRequest(
        query="temperature", preferred_tools=["numbers"], arguments={"value": value},
    ))
    assert invoked == [value]
    assert result.data == value and type(result.data) is type(value)
    assert json.loads(result.model_dump_json())["data"] == value


@pytest.mark.asyncio
@pytest.mark.parametrize("value", NONFINITE)
async def test_legacy_outputs_without_a_declared_schema_keep_existing_behavior(value):
    router = SchemaRouter()
    router.add_bound_tool(ToolSpec(name="legacy", endpoints=[EndpointSpec(
        name="read", read_only=True,
    )]), lambda *_: value)
    result, = await router.ainvoke(PlanRequest(query="legacy", preferred_tools=["legacy"]))
    assert not math.isfinite(result.data)


@pytest.mark.asyncio
@pytest.mark.parametrize("value", (Decimal("1.25"), Decimal("1E+10000"), Decimal("-0")))
async def test_public_finite_decimal_inputs_and_outputs_preserve_native_values(value):
    schema = {"type": ["number", "null"]}
    invoked = []

    def invoke(endpoint, arguments):
        invoked.append(arguments["value"])
        return arguments["value"]

    router = SchemaRouter()
    router.add_bound_tool(ToolSpec(name="decimal", endpoints=[EndpointSpec(
        name="read", read_only=True,
        parameters=[ParameterSpec(name="value", required=True, json_schema=schema)],
        output_schema=schema,
    )]), invoke)
    result, = await router.ainvoke(PlanRequest(
        query="decimal", preferred_tools=["decimal"], arguments={"value": value},
    ))
    assert invoked == [value]
    assert type(result.data) is Decimal and result.data == value


@pytest.mark.parametrize("value", (Decimal("NaN"), Decimal("sNaN"),
                                   Decimal("Infinity"), complex(1, 2)))
def test_empty_schema_preserves_legacy_runtime_value_policy(value):
    from schemarouter.validation import validate_json_schema_value

    validate_json_schema_value(value, {}, context="legacy")


@pytest.mark.asyncio
@pytest.mark.parametrize("value", (Decimal("NaN"), Decimal("Infinity"), complex(1, 2)))
async def test_legacy_native_outputs_without_schema_preserve_decimal_and_complex(value):
    router = SchemaRouter()
    router.add_bound_tool(ToolSpec(name="legacy", endpoints=[EndpointSpec(
        name="read", read_only=True,
    )]), lambda *_: value)
    result, = await router.ainvoke(PlanRequest(query="legacy", preferred_tools=["legacy"]))
    assert result.data is value


@pytest.mark.parametrize("value", ("NaN", "sNaN", "Infinity"))
def test_decimal_subclass_cannot_override_the_finite_value_check(value):
    from schemarouter.validation import validate_json_schema_value

    class MisleadingDecimal(Decimal):
        def is_finite(self):
            return True

    with pytest.raises(SchemaValidationError, match="probe: non-finite"):
        validate_json_schema_value(MisleadingDecimal(value), {"type": "number"}, context="probe")
