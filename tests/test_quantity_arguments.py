import math

import pytest

from schemarouter import (
    EndpointSpec,
    FieldSpec,
    InMemoryRegistry,
    ParameterSpec,
    PlanRequest,
    QuantityArgument,
    RegistryExecutor,
    SchemaPlanner,
    ToolSpec,
    UnitNormalizationSpec,
)


def _size_tool(
    name: str,
    *,
    provider: str,
    parameter: ParameterSpec,
) -> ToolSpec:
    return ToolSpec(
        name=name,
        provider=provider,
        access_mode="openapi",
        endpoints=[
            EndpointSpec(
                name="search",
                description="Search particle size data",
                read_only=True,
                parameters=[parameter],
                output_fields=[
                    FieldSpec(
                        name="particle_size",
                        semantic_id="particle_size",
                        aliases=["particle size", "입자 크기"],
                        json_schema={"type": "number"},
                    )
                ],
            )
        ],
    )


def test_quantity_argument_rejects_non_numeric_or_non_finite_values() -> None:
    with pytest.raises(ValueError, match="numeric scalar or numeric array"):
        QuantityArgument(value="100", unit="nm")
    with pytest.raises(ValueError, match="numeric scalar or numeric array"):
        QuantityArgument(value=True, unit="nm")
    with pytest.raises(ValueError, match="finite"):
        QuantityArgument(value=float("inf"), unit="nm")


@pytest.mark.parametrize("unit", ["", " nm", "nm "])
def test_quantity_argument_requires_exact_non_empty_unit(unit: str) -> None:
    with pytest.raises(ValueError):
        QuantityArgument(value=100.0, unit=unit)


def test_parameter_unit_contract_requires_numeric_schema() -> None:
    with pytest.raises(ValueError, match="numeric scalar or numeric-array"):
        ParameterSpec(
            name="label",
            json_schema={"type": "string"},
            unit="nm",
        )

    with pytest.raises(ValueError, match="declared numeric json_schema"):
        ParameterSpec(
            name="max_size",
            unit="m",
            unit_normalization=UnitNormalizationSpec(
                dimension="length",
                canonical_unit="nm",
                scale=1e9,
            ),
        )


def test_planner_compiles_same_quantity_into_provider_native_units() -> None:
    registry = InMemoryRegistry()
    meters = _size_tool(
        "meters_api",
        provider="provider_a",
        parameter=ParameterSpec(
            name="max_size",
            json_schema={"type": "number"},
            unit="m",
            unit_normalization=UnitNormalizationSpec(
                dimension="length",
                canonical_unit="nm",
                scale=1e9,
            ),
        ),
    )
    nanometers = _size_tool(
        "nanometers_api",
        provider="provider_b",
        parameter=ParameterSpec(
            name="max_size",
            json_schema={"type": "number"},
            unit="nm",
        ),
    )
    registry.register(meters)
    registry.register(nanometers)

    plan = SchemaPlanner(registry).plan(
        PlanRequest(
            query="입자 크기",
            preferred_tools=["meters_api"],
            arguments={
                "max_size": QuantityArgument(value=100.0, unit="nm"),
            },
            fallback_scope="cross_provider",
            max_fallbacks=2,
        )
    )

    assert plan.calls[0].tool == "meters_api"
    assert plan.calls[0].arguments["max_size"] == pytest.approx(1e-7)

    route = plan.fallback_route(0)
    assert route is not None
    assert route.alternatives[0].tool == "nanometers_api"
    assert route.alternatives[0].arguments["max_size"] == pytest.approx(100.0)


def test_quantity_dict_from_analyzer_is_compiled_like_quantity_argument() -> None:
    registry = InMemoryRegistry()
    registry.register(
        _size_tool(
            "meters_api",
            provider="provider_a",
            parameter=ParameterSpec(
                name="max_size",
                json_schema={"type": "number"},
                unit="m",
                unit_normalization=UnitNormalizationSpec(
                    dimension="length",
                    canonical_unit="nm",
                    scale=1e9,
                ),
            ),
        )
    )

    plan = SchemaPlanner(registry).plan(
        PlanRequest(
            query="particle size",
            arguments={
                "max_size": {"value": 250.0, "unit": "nm"},
            },
        )
    )

    assert plan.calls[0].arguments["max_size"] == pytest.approx(2.5e-7)


def test_incompatible_quantity_unit_prunes_route_and_uses_compatible_provider() -> None:
    registry = InMemoryRegistry()
    registry.register(
        _size_tool(
            "energy_api",
            provider="wrong_provider",
            parameter=ParameterSpec(
                name="max_size",
                json_schema={"type": "number"},
                unit="eV",
            ),
        )
    )
    registry.register(
        _size_tool(
            "nanometers_api",
            provider="provider_b",
            parameter=ParameterSpec(
                name="max_size",
                json_schema={"type": "number"},
                unit="nm",
            ),
        )
    )

    plan = SchemaPlanner(registry).plan(
        PlanRequest(
            query="particle size",
            preferred_tools=["energy_api"],
            arguments={
                "max_size": QuantityArgument(value=100.0, unit="nm"),
            },
        )
    )

    assert plan.calls[0].tool == "nanometers_api"
    assert plan.calls[0].arguments["max_size"] == 100.0
    assert any("incompatible argument" in warning for warning in plan.warnings)


def test_plain_numeric_argument_remains_provider_native_for_backward_compatibility() -> None:
    registry = InMemoryRegistry()
    registry.register(
        _size_tool(
            "meters_api",
            provider="provider_a",
            parameter=ParameterSpec(
                name="max_size",
                json_schema={"type": "number"},
                unit="m",
                unit_normalization=UnitNormalizationSpec(
                    dimension="length",
                    canonical_unit="nm",
                    scale=1e9,
                ),
            ),
        )
    )

    plan = SchemaPlanner(registry).plan(
        PlanRequest(
            query="particle size",
            arguments={"max_size": 100.0},
        )
    )

    assert plan.calls[0].arguments["max_size"] == 100.0


def test_affine_canonical_input_is_inverted_to_provider_unit() -> None:
    registry = InMemoryRegistry()
    tool = ToolSpec(
        name="temperature_api",
        endpoints=[
            EndpointSpec(
                name="search",
                description="Search temperature data",
                read_only=True,
                parameters=[
                    ParameterSpec(
                        name="min_temperature",
                        json_schema={"type": "number"},
                        unit="degC",
                        unit_normalization=UnitNormalizationSpec(
                            dimension="temperature",
                            canonical_unit="K",
                            scale=1.0,
                            offset=273.15,
                        ),
                    )
                ],
                output_fields=[
                    FieldSpec(
                        name="temperature",
                        semantic_id="temperature",
                        aliases=["temperature"],
                        json_schema={"type": "number"},
                    )
                ],
            )
        ],
    )
    registry.register(tool)

    plan = SchemaPlanner(registry).plan(
        PlanRequest(
            query="temperature",
            arguments={
                "min_temperature": QuantityArgument(
                    value=298.15,
                    unit="K",
                )
            },
        )
    )

    assert plan.calls[0].arguments["min_temperature"] == pytest.approx(25.0)


@pytest.mark.asyncio
async def test_executor_receives_only_provider_native_numeric_argument() -> None:
    registry = InMemoryRegistry()
    tool = _size_tool(
        "meters_api",
        provider="provider_a",
        parameter=ParameterSpec(
            name="max_size",
            json_schema={"type": "number"},
            unit="m",
            unit_normalization=UnitNormalizationSpec(
                dimension="length",
                canonical_unit="nm",
                scale=1e9,
            ),
        ),
    )
    registry.register(tool)

    plan = SchemaPlanner(registry).plan(
        PlanRequest(
            query="particle size",
            arguments={
                "max_size": QuantityArgument(value=100.0, unit="nm"),
            },
        )
    )

    seen = {}

    def invoke(endpoint_name, arguments):
        seen.update(arguments)
        return {"particle_size": 90.0}

    executor = RegistryExecutor(registry)
    executor.bind("meters_api", invoke)
    result = (await executor.execute(plan))[0]

    assert seen == {"max_size": pytest.approx(1e-7)}
    assert isinstance(seen["max_size"], float)
    assert result.data == {"particle_size": 90.0}


def test_quantity_array_conversion_is_elementwise_and_finite() -> None:
    registry = InMemoryRegistry()
    tool = ToolSpec(
        name="window_api",
        endpoints=[
            EndpointSpec(
                name="search",
                description="Search wavelength window",
                read_only=True,
                parameters=[
                    ParameterSpec(
                        name="window",
                        json_schema={
                            "type": "array",
                            "items": {"type": "number"},
                        },
                        unit="m",
                        unit_normalization=UnitNormalizationSpec(
                            dimension="length",
                            canonical_unit="nm",
                            scale=1e9,
                        ),
                    )
                ],
                output_fields=[FieldSpec(name="value")],
            )
        ],
    )
    registry.register(tool)

    plan = SchemaPlanner(registry).plan(
        PlanRequest(
            query="window",
            arguments={
                "window": QuantityArgument(
                    value=[400.0, 700.0],
                    unit="nm",
                )
            },
        )
    )

    assert plan.calls[0].arguments["window"] == pytest.approx([4e-7, 7e-7])
