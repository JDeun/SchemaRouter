"""Schema-bound public values must survive JSON serialization without numeric corruption."""
from __future__ import annotations

import json
import math

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
@pytest.mark.parametrize("number", NONFINITE)
@pytest.mark.parametrize("shape", ("scalar", "array", "nested", "nested_array"))
async def test_public_nonfinite_inputs_are_rejected_before_native_dispatch(number, shape):
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
    with pytest.raises(SchemaValidationError, match="non-finite") as error:
        await router.ainvoke(PlanRequest(
            query="temperature", preferred_tools=["numbers"], arguments={"value": value},
        ))
    assert invoked == []
    assert "arguments for numbers.read" in str(error.value)
    assert SECRET not in str(error.value)


@pytest.mark.asyncio
@pytest.mark.parametrize("number", NONFINITE)
@pytest.mark.parametrize("shape", ("scalar", "array", "nested", "nested_array"))
async def test_public_nonfinite_outputs_are_rejected_without_echoing_payload(number, shape):
    schema, value = _shape(shape, number)
    router = SchemaRouter()
    invoked = []

    def invoke(endpoint, arguments):
        invoked.append(endpoint)
        return value

    router.add_bound_tool(ToolSpec(name="numbers", endpoints=[EndpointSpec(
        name="read", read_only=True, output_schema=schema,
    )]), invoke)
    with pytest.raises(SchemaValidationError, match="non-finite") as error:
        await router.ainvoke(PlanRequest(query="temperature", preferred_tools=["numbers"]))
    assert invoked == ["read"]
    assert "output from numbers.read" in str(error.value)
    assert SECRET not in str(error.value)


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
