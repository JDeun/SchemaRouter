from __future__ import annotations

import pytest

from schemarouter import (
    EndpointSpec,
    ExecutionPlan,
    FieldSpec,
    SchemaRouter,
    ToolCall,
    ToolSpec,
    UnitNormalizationSpec,
)
from schemarouter.validation import canonical_field_value_schema


def _tool() -> ToolSpec:
    return ToolSpec(
        name="array_fixture",
        endpoints=[
            EndpointSpec(
                name="read",
                read_only=True,
                destructive=False,
                output_schema={
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
                },
                output_fields=[
                    FieldSpec(
                        name="data",
                        json_schema={
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "band_gap": {"type": "number"},
                                    "density": {"type": "number"},
                                },
                            },
                        },
                    ),
                    FieldSpec(
                        name="data[].band_gap",
                        path=["data", "*", "band_gap"],
                        result_path=["data", "*", "band_gap"],
                        json_schema={"type": "number"},
                        unit="meV",
                        unit_normalization=UnitNormalizationSpec(
                            dimension="energy",
                            canonical_unit="eV",
                            scale=0.001,
                        ),
                    ),
                    FieldSpec(
                        name="data[].density",
                        path=["data", "*", "density"],
                        result_path=["data", "*", "density"],
                        json_schema={"type": "number"},
                    ),
                ],
            )
        ],
    )


@pytest.mark.asyncio
async def test_array_item_projection_preserves_record_alignment() -> None:
    router = SchemaRouter()
    tool = _tool()
    key = router.add_tool(tool)

    async def invoker(_endpoint: str, _arguments: dict) -> dict:
        return {
            "data": [
                {"band_gap": 1200.0, "density": 2.4},
                {"band_gap": 500.0, "density": 3.1},
            ]
        }

    router.executor.bind(
        key,
        invoker,
        expected_fingerprint=tool.fingerprint,
    )
    endpoint = tool.endpoint("read")
    call = ToolCall(
        tool=key,
        endpoint=endpoint.name,
        fields=["data[].band_gap", "data[].density"],
        schema_fingerprint=endpoint.fingerprint,
        tool_fingerprint=tool.fingerprint,
    )
    plan = ExecutionPlan(
        query="band gaps and densities",
        registry_version=router.registry.version,
        calls=[call],
    )

    result = (await router.execute(plan))[0]

    assert result.data == {
        "data": [
            {"band_gap": 1.2, "density": 2.4},
            {"band_gap": 0.5, "density": 3.1},
        ]
    }
    assert result.field_contracts["data[].band_gap"].source_unit == "meV"
    assert result.field_contracts["data[].band_gap"].unit == "eV"


@pytest.mark.asyncio
async def test_array_item_projection_keeps_missing_child_in_same_record_slot() -> None:
    router = SchemaRouter()
    tool = _tool()
    key = router.add_tool(tool)

    async def invoker(_endpoint: str, _arguments: dict) -> dict:
        return {
            "data": [
                {"band_gap": 1200.0, "density": 2.4},
                {"density": 3.1},
                {"band_gap": 700.0, "density": 4.2},
            ]
        }

    router.executor.bind(
        key,
        invoker,
        expected_fingerprint=tool.fingerprint,
    )
    endpoint = tool.endpoint("read")
    call = ToolCall(
        tool=key,
        endpoint=endpoint.name,
        fields=["data[].band_gap", "data[].density"],
        schema_fingerprint=endpoint.fingerprint,
        tool_fingerprint=tool.fingerprint,
    )
    plan = ExecutionPlan(
        query="aligned records",
        registry_version=router.registry.version,
        calls=[call],
    )

    result = (await router.execute(plan))[0]

    assert result.data["data"][0] == {"band_gap": 1.2, "density": 2.4}
    assert result.data["data"][1] == {"density": 3.1}
    assert result.data["data"][2]["density"] == 4.2
    assert result.data["data"][2]["band_gap"] == pytest.approx(0.7)


@pytest.mark.asyncio
async def test_parent_and_array_child_can_be_selected_together_without_collision() -> None:
    router = SchemaRouter()
    tool = _tool()
    key = router.add_tool(tool)

    raw = {
        "data": [
            {"band_gap": 1200.0, "density": 2.4},
            {"band_gap": 500.0, "density": 3.1},
        ]
    }

    async def invoker(_endpoint: str, _arguments: dict) -> dict:
        return raw

    router.executor.bind(
        key,
        invoker,
        expected_fingerprint=tool.fingerprint,
    )
    endpoint = tool.endpoint("read")
    call = ToolCall(
        tool=key,
        endpoint=endpoint.name,
        fields=["data", "data[].band_gap"],
        schema_fingerprint=endpoint.fingerprint,
        tool_fingerprint=tool.fingerprint,
    )
    plan = ExecutionPlan(
        query="full data and band gap",
        registry_version=router.registry.version,
        calls=[call],
    )

    result = (await router.execute(plan))[0]

    assert result.data == {
        "data": [
            {"band_gap": 1.2, "density": 2.4},
            {"band_gap": 0.5, "density": 3.1},
        ]
    }


def test_array_field_value_schema_is_leaf_schema() -> None:
    endpoint = _tool().endpoint("read")

    assert canonical_field_value_schema(
        endpoint,
        "data[].band_gap",
    )["type"] == "number"


def test_array_wildcard_cannot_be_root_or_terminal_segment() -> None:
    with pytest.raises(ValueError, match="must not begin"):
        FieldSpec(
            name="bad",
            path=["*", "value"],
            json_schema={"type": "number"},
        )

    with pytest.raises(ValueError, match="must not end"):
        FieldSpec(
            name="bad",
            path=["data", "*"],
            json_schema={"type": "array"},
        )
