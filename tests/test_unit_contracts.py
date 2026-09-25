import pytest

from schemarouter import (
    EndpointSpec,
    FieldSpec,
    InMemoryRegistry,
    PlanRequest,
    RegistryExecutor,
    SchemaPlanner,
    SchemaValidationError,
    ToolCall,
    ToolSpec,
    UnitNormalizationSpec,
)


def _quantity_field(
    name: str,
    *,
    semantic_id: str,
    unit: str,
    dimension: str,
    canonical_unit: str,
    scale: float,
    json_type: str = "number",
) -> FieldSpec:
    return FieldSpec(
        name=name,
        semantic_id=semantic_id,
        aliases=["elastic modulus", "탄성계수"],
        json_schema={"type": json_type},
        unit=unit,
        unit_normalization=UnitNormalizationSpec(
            dimension=dimension,
            canonical_unit=canonical_unit,
            scale=scale,
        ),
    )


def _quantity_tool(
    name: str,
    field: FieldSpec,
    *,
    provider: str,
) -> ToolSpec:
    return ToolSpec(
        name=name,
        provider=provider,
        access_mode="openapi",
        endpoints=[
            EndpointSpec(
                name="read",
                description="Read elastic modulus",
                read_only=True,
                output_fields=[field],
            )
        ],
    )


def test_field_unit_requires_numeric_explicit_schema_type() -> None:
    with pytest.raises(ValueError, match="numeric json_schema type"):
        FieldSpec(
            name="paper_title",
            json_schema={"type": "string"},
            unit="GPa",
        )


@pytest.mark.parametrize(
    ("scale", "offset"),
    [
        (0.0, 0.0),
        (float("inf"), 0.0),
        (1.0, float("nan")),
    ],
)
def test_unit_normalization_rejects_non_finite_or_zero_conversion(
    scale: float,
    offset: float,
) -> None:
    with pytest.raises(ValueError):
        UnitNormalizationSpec(
            dimension="pressure",
            canonical_unit="Pa",
            scale=scale,
            offset=offset,
        )


def test_fallback_accepts_same_semantic_numeric_field_with_convertible_units() -> None:
    registry = InMemoryRegistry()
    registry.register(
        _quantity_tool(
            "provider_gpa",
            _quantity_field(
                "elastic_modulus",
                semantic_id="elastic_modulus",
                unit="GPa",
                dimension="pressure",
                canonical_unit="Pa",
                scale=1e9,
            ),
            provider="provider_a",
        )
    )
    registry.register(
        _quantity_tool(
            "provider_pa",
            _quantity_field(
                "youngs_modulus",
                semantic_id="elastic_modulus",
                unit="Pa",
                dimension="pressure",
                canonical_unit="Pa",
                scale=1.0,
            ),
            provider="provider_b",
        )
    )

    plan = SchemaPlanner(registry).plan(
        PlanRequest(
            query="탄성계수",
            preferred_tools=["provider_gpa"],
            fallback_scope="cross_provider",
        )
    )

    assert plan.calls[0].tool == "provider_gpa"
    route = plan.fallback_route(0)
    assert route is not None
    assert [call.tool for call in route.alternatives] == ["provider_pa"]


def test_fallback_rejects_same_semantic_field_with_incompatible_datatype() -> None:
    registry = InMemoryRegistry()
    registry.register(
        _quantity_tool(
            "numeric_provider",
            FieldSpec(
                name="elastic_modulus",
                semantic_id="elastic_modulus",
                aliases=["elastic modulus", "탄성계수"],
                json_schema={"type": "number"},
            ),
            provider="provider_a",
        )
    )
    registry.register(
        _quantity_tool(
            "string_provider",
            FieldSpec(
                name="elastic_modulus_text",
                semantic_id="elastic_modulus",
                aliases=["elastic modulus", "탄성계수"],
                json_schema={"type": "string"},
            ),
            provider="provider_b",
        )
    )

    plan = SchemaPlanner(registry).plan(
        PlanRequest(
            query="탄성계수",
            preferred_tools=["numeric_provider"],
            fallback_scope="cross_provider",
        )
    )

    assert plan.fallback_route(0) is None


def test_fallback_rejects_same_semantic_field_with_incompatible_dimension() -> None:
    registry = InMemoryRegistry()
    registry.register(
        _quantity_tool(
            "pressure_provider",
            _quantity_field(
                "elastic_modulus",
                semantic_id="elastic_modulus",
                unit="GPa",
                dimension="pressure",
                canonical_unit="Pa",
                scale=1e9,
            ),
            provider="provider_a",
        )
    )
    registry.register(
        _quantity_tool(
            "length_provider",
            _quantity_field(
                "elastic_modulus",
                semantic_id="elastic_modulus",
                unit="nm",
                dimension="length",
                canonical_unit="m",
                scale=1e-9,
            ),
            provider="provider_b",
        )
    )

    plan = SchemaPlanner(registry).plan(
        PlanRequest(
            query="탄성계수",
            preferred_tools=["pressure_provider"],
            fallback_scope="cross_provider",
        )
    )

    assert plan.fallback_route(0) is None


@pytest.mark.asyncio
async def test_executor_normalizes_unit_after_raw_validation_and_emits_contract() -> None:
    field = _quantity_field(
        "elastic_modulus",
        semantic_id="elastic_modulus",
        unit="GPa",
        dimension="pressure",
        canonical_unit="Pa",
        scale=1e9,
    )
    endpoint = EndpointSpec(
        name="read",
        read_only=True,
        output_fields=[field],
        output_schema={
            "type": "object",
            "properties": {
                "elastic_modulus": {"type": "number"},
            },
            "required": ["elastic_modulus"],
        },
    )
    tool = ToolSpec(name="materials", endpoints=[endpoint])
    registry = InMemoryRegistry()
    registry.register(tool)

    call = ToolCall(
        tool="materials",
        endpoint="read",
        fields=["elastic_modulus"],
        schema_fingerprint=endpoint.fingerprint,
        tool_fingerprint=tool.fingerprint,
    )
    executor = RegistryExecutor(registry)
    executor.bind(
        "materials",
        lambda endpoint_name, arguments: {"elastic_modulus": 130.0},
    )

    result = await executor.execute_call(call)

    assert result.data == {"elastic_modulus": 130_000_000_000.0}
    contract = result.field_contracts["elastic_modulus"]
    assert contract.semantic_id == "elastic_modulus"
    assert contract.json_schema == {"type": "number"}
    assert contract.source_unit == "GPa"
    assert contract.unit == "Pa"
    assert contract.dimension == "pressure"


@pytest.mark.asyncio
async def test_raw_type_failure_happens_before_unit_normalization() -> None:
    field = _quantity_field(
        "elastic_modulus",
        semantic_id="elastic_modulus",
        unit="GPa",
        dimension="pressure",
        canonical_unit="Pa",
        scale=1e9,
    )
    endpoint = EndpointSpec(
        name="read",
        read_only=True,
        output_fields=[field],
        output_schema={
            "type": "object",
            "properties": {
                "elastic_modulus": {"type": "number"},
            },
            "required": ["elastic_modulus"],
        },
    )
    tool = ToolSpec(name="materials", endpoints=[endpoint])
    registry = InMemoryRegistry()
    registry.register(tool)

    call = ToolCall(
        tool="materials",
        endpoint="read",
        fields=["elastic_modulus"],
        schema_fingerprint=endpoint.fingerprint,
        tool_fingerprint=tool.fingerprint,
    )
    executor = RegistryExecutor(registry)
    executor.bind(
        "materials",
        lambda endpoint_name, arguments: {"elastic_modulus": "130"},
    )

    with pytest.raises(SchemaValidationError):
        await executor.execute_call(call)



@pytest.mark.asyncio
async def test_executor_normalizes_numeric_array_units() -> None:
    field = FieldSpec(
        name="wavelengths",
        semantic_id="wavelength",
        json_schema={
            "type": "array",
            "items": {"type": "number"},
        },
        unit="nm",
        unit_normalization=UnitNormalizationSpec(
            dimension="length",
            canonical_unit="m",
            scale=1e-9,
        ),
    )
    endpoint = EndpointSpec(
        name="read",
        read_only=True,
        output_fields=[field],
    )
    tool = ToolSpec(name="spectra", endpoints=[endpoint])
    registry = InMemoryRegistry()
    registry.register(tool)
    call = ToolCall(
        tool="spectra",
        endpoint="read",
        fields=["wavelengths"],
        schema_fingerprint=endpoint.fingerprint,
        tool_fingerprint=tool.fingerprint,
    )

    executor = RegistryExecutor(registry)
    executor.bind(
        "spectra",
        lambda endpoint_name, arguments: {"wavelengths": [400.0, 500.0]},
    )

    result = await executor.execute_call(call)

    assert result.data == {
        "wavelengths": [pytest.approx(4e-7), pytest.approx(5e-7)]
    }
    contract = result.field_contracts["wavelengths"]
    assert contract.json_schema == {
        "type": "array",
        "items": {"type": "number"},
    }
    assert contract.source_unit == "nm"
    assert contract.unit == "m"
    assert contract.dimension == "length"
