import pytest

from schemarouter import (
    EndpointSpec,
    EvidenceRequirements,
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
    with pytest.raises(ValueError, match="numeric scalar or numeric-array"):
        FieldSpec(
            name="paper_title",
            json_schema={"type": "string"},
            unit="GPa",
        )


@pytest.mark.parametrize(
    ("scale", "offset"),
    [
        (0.0, 0.0),
        (-1.0, 0.0),
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

    assert result.data["wavelengths"] == pytest.approx([4e-7, 5e-7])
    contract = result.field_contracts["wavelengths"]
    assert contract.json_schema == {
        "type": "array",
        "items": {"type": "number"},
    }
    assert contract.source_unit == "nm"
    assert contract.unit == "m"
    assert contract.dimension == "length"



def test_endpoint_schema_rejects_unit_on_non_numeric_raw_field() -> None:
    with pytest.raises(ValueError, match="numeric scalar or numeric-array"):
        EndpointSpec(
            name="read",
            read_only=True,
            output_fields=[
                FieldSpec(
                    name="title",
                    unit="GPa",
                )
            ],
            output_schema={
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                },
            },
        )


def test_fallback_keeps_scientific_unit_symbols_case_and_punctuation_sensitive() -> None:
    registry = InMemoryRegistry()
    registry.register(
        _quantity_tool(
            "meters_per_second",
            FieldSpec(
                name="speed",
                semantic_id="speed",
                aliases=["speed"],
                json_schema={"type": "number"},
                unit="m/s",
            ),
            provider="provider_a",
        )
    )
    registry.register(
        _quantity_tool(
            "milliseconds",
            FieldSpec(
                name="speed_value",
                semantic_id="speed",
                aliases=["speed"],
                json_schema={"type": "number"},
                unit="ms",
            ),
            provider="provider_b",
        )
    )

    plan = SchemaPlanner(registry).plan(
        PlanRequest(
            query="speed",
            preferred_tools=["meters_per_second"],
            fallback_scope="cross_provider",
        )
    )

    assert plan.fallback_route(0) is None


def test_fallback_allows_integer_candidate_for_number_requirement_not_reverse() -> None:
    def field(name: str, json_type: str) -> FieldSpec:
        return FieldSpec(
            name=name,
            semantic_id="sample_count",
            aliases=["sample count"],
            json_schema={"type": json_type},
        )

    registry = InMemoryRegistry()
    registry.register(
        _quantity_tool(
            "number_primary",
            field("count", "number"),
            provider="provider_a",
        )
    )
    registry.register(
        _quantity_tool(
            "integer_candidate",
            field("count_integer", "integer"),
            provider="provider_b",
        )
    )
    plan = SchemaPlanner(registry).plan(
        PlanRequest(
            query="sample count",
            preferred_tools=["number_primary"],
            fallback_scope="cross_provider",
        )
    )
    assert plan.fallback_route(0) is not None

    reverse_registry = InMemoryRegistry()
    reverse_registry.register(
        _quantity_tool(
            "integer_primary",
            field("count_integer", "integer"),
            provider="provider_a",
        )
    )
    reverse_registry.register(
        _quantity_tool(
            "number_candidate",
            field("count", "number"),
            provider="provider_b",
        )
    )
    reverse_plan = SchemaPlanner(reverse_registry).plan(
        PlanRequest(
            query="sample count",
            preferred_tools=["integer_primary"],
            fallback_scope="cross_provider",
        )
    )
    assert reverse_plan.fallback_route(0) is None


@pytest.mark.asyncio
async def test_unit_normalization_overflow_fails_closed() -> None:
    field = FieldSpec(
        name="value",
        semantic_id="huge_value",
        json_schema={"type": "number"},
        unit="GPa",
        unit_normalization=UnitNormalizationSpec(
            dimension="pressure",
            canonical_unit="Pa",
            scale=1e9,
        ),
    )
    endpoint = EndpointSpec(
        name="read",
        read_only=True,
        output_fields=[field],
    )
    tool = ToolSpec(name="huge", endpoints=[endpoint])
    registry = InMemoryRegistry()
    registry.register(tool)
    call = ToolCall(
        tool="huge",
        endpoint="read",
        fields=["value"],
        schema_fingerprint=endpoint.fingerprint,
        tool_fingerprint=tool.fingerprint,
    )

    executor = RegistryExecutor(registry)
    executor.bind(
        "huge",
        lambda endpoint_name, arguments: {"value": 1e308},
    )

    with pytest.raises(SchemaValidationError, match="non-finite|overflow"):
        await executor.execute_call(call)



@pytest.mark.asyncio
async def test_nullable_numeric_unit_value_remains_null() -> None:
    field = FieldSpec(
        name="elastic_modulus",
        semantic_id="elastic_modulus",
        json_schema={"type": ["number", "null"]},
        unit="GPa",
        unit_normalization=UnitNormalizationSpec(
            dimension="pressure",
            canonical_unit="Pa",
            scale=1e9,
        ),
    )
    endpoint = EndpointSpec(
        name="read",
        read_only=True,
        output_fields=[field],
    )
    tool = ToolSpec(name="nullable_materials", endpoints=[endpoint])
    registry = InMemoryRegistry()
    registry.register(tool)
    call = ToolCall(
        tool="nullable_materials",
        endpoint="read",
        fields=["elastic_modulus"],
        schema_fingerprint=endpoint.fingerprint,
        tool_fingerprint=tool.fingerprint,
    )
    executor = RegistryExecutor(registry)
    executor.bind(
        "nullable_materials",
        lambda endpoint_name, arguments: {"elastic_modulus": None},
    )

    result = await executor.execute_call(call)

    assert result.data == {"elastic_modulus": None}
    assert result.field_contracts["elastic_modulus"].unit == "Pa"



@pytest.mark.parametrize("unit", ["", " GPa", "GPa "])
def test_field_unit_rejects_empty_or_surrounding_whitespace(unit: str) -> None:
    with pytest.raises(ValueError):
        FieldSpec(
            name="elastic_modulus",
            json_schema={"type": "number"},
            unit=unit,
        )


@pytest.mark.parametrize(
    ("dimension", "canonical_unit"),
    [
        (" pressure", "Pa"),
        ("pressure ", "Pa"),
        ("pressure", " Pa"),
        ("pressure", "Pa "),
    ],
)
def test_unit_normalization_rejects_surrounding_whitespace(
    dimension: str,
    canonical_unit: str,
) -> None:
    with pytest.raises(ValueError):
        UnitNormalizationSpec(
            dimension=dimension,
            canonical_unit=canonical_unit,
        )


def test_same_source_and_canonical_unit_requires_identity_transform() -> None:
    with pytest.raises(ValueError, match="must be identity"):
        FieldSpec(
            name="pressure",
            json_schema={"type": "number"},
            unit="Pa",
            unit_normalization=UnitNormalizationSpec(
                dimension="pressure",
                canonical_unit="Pa",
                scale=2.0,
            ),
        )


def test_unit_normalization_requires_declared_numeric_schema() -> None:
    field = FieldSpec(
        name="elastic_modulus",
        unit="GPa",
        unit_normalization=UnitNormalizationSpec(
            dimension="pressure",
            canonical_unit="Pa",
            scale=1e9,
        ),
    )

    with pytest.raises(ValueError, match="requires a declared numeric field schema"):
        EndpointSpec(
            name="read",
            read_only=True,
            output_fields=[field],
        )


def test_field_schema_rejects_incompatible_raw_endpoint_type() -> None:
    with pytest.raises(ValueError, match="incompatible with the raw output schema"):
        EndpointSpec(
            name="read",
            read_only=True,
            output_fields=[
                FieldSpec(
                    name="elastic_modulus",
                    json_schema={"type": "number"},
                )
            ],
            output_schema={
                "type": "object",
                "properties": {
                    "elastic_modulus": {"type": "string"},
                },
            },
        )


def test_field_number_contract_accepts_integer_raw_endpoint_type() -> None:
    endpoint = EndpointSpec(
        name="read",
        read_only=True,
        output_fields=[
            FieldSpec(
                name="sample_count",
                json_schema={"type": "number"},
            )
        ],
        output_schema={
            "type": "object",
            "properties": {
                "sample_count": {"type": "integer"},
            },
        },
    )

    assert endpoint.output_fields[0].json_schema == {"type": "number"}


def test_unit_bearing_fallback_requires_explicit_datatype_contracts() -> None:
    registry = InMemoryRegistry()
    registry.register(
        _quantity_tool(
            "provider_a",
            FieldSpec(
                name="elastic_modulus",
                semantic_id="elastic_modulus",
                aliases=["elastic modulus", "탄성계수"],
                unit="GPa",
            ),
            provider="provider_a",
        )
    )
    registry.register(
        _quantity_tool(
            "provider_b",
            FieldSpec(
                name="youngs_modulus",
                semantic_id="elastic_modulus",
                aliases=["elastic modulus", "탄성계수"],
                unit="GPa",
            ),
            provider="provider_b",
        )
    )

    plan = SchemaPlanner(registry).plan(
        PlanRequest(
            query="탄성계수",
            preferred_tools=["provider_a"],
            fallback_scope="cross_provider",
        )
    )

    assert plan.fallback_route(0) is None


def test_fallback_compares_post_normalization_datatype() -> None:
    registry = InMemoryRegistry()
    registry.register(
        _quantity_tool(
            "integer_gpa",
            _quantity_field(
                "elastic_modulus",
                semantic_id="elastic_modulus",
                unit="GPa",
                dimension="pressure",
                canonical_unit="Pa",
                scale=1e9,
                json_type="integer",
            ),
            provider="provider_a",
        )
    )
    registry.register(
        _quantity_tool(
            "number_pa",
            _quantity_field(
                "youngs_modulus",
                semantic_id="elastic_modulus",
                unit="Pa",
                dimension="pressure",
                canonical_unit="Pa",
                scale=1.0,
                json_type="number",
            ),
            provider="provider_b",
        )
    )

    plan = SchemaPlanner(registry).plan(
        PlanRequest(
            query="탄성계수",
            preferred_tools=["integer_gpa"],
            fallback_scope="cross_provider",
        )
    )

    route = plan.fallback_route(0)
    assert route is not None
    assert [call.tool for call in route.alternatives] == ["number_pa"]


def test_fallback_rejects_contradictory_transform_for_same_source_unit() -> None:
    registry = InMemoryRegistry()
    registry.register(
        _quantity_tool(
            "provider_a",
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
            "provider_b",
            _quantity_field(
                "youngs_modulus",
                semantic_id="elastic_modulus",
                unit="GPa",
                dimension="pressure",
                canonical_unit="Pa",
                scale=1e8,
            ),
            provider="provider_b",
        )
    )

    plan = SchemaPlanner(registry).plan(
        PlanRequest(
            query="탄성계수",
            preferred_tools=["provider_a"],
            fallback_scope="cross_provider",
        )
    )

    assert plan.fallback_route(0) is None


@pytest.mark.asyncio
async def test_field_schema_is_enforced_when_endpoint_raw_schema_is_loose() -> None:
    endpoint = EndpointSpec(
        name="read",
        read_only=True,
        output_fields=[
            FieldSpec(
                name="elastic_modulus",
                json_schema={"type": "number"},
            )
        ],
        output_schema={
            "type": "object",
            "properties": {
                "elastic_modulus": {},
            },
        },
    )
    tool = ToolSpec(name="loose_provider", endpoints=[endpoint])
    registry = InMemoryRegistry()
    registry.register(tool)
    call = ToolCall(
        tool="loose_provider",
        endpoint="read",
        fields=["elastic_modulus"],
        schema_fingerprint=endpoint.fingerprint,
        tool_fingerprint=tool.fingerprint,
    )
    executor = RegistryExecutor(registry)
    executor.bind(
        "loose_provider",
        lambda endpoint_name, arguments: {"elastic_modulus": "130"},
    )

    with pytest.raises(SchemaValidationError, match="elastic_modulus"):
        await executor.execute_call(call)


@pytest.mark.asyncio
async def test_affine_offset_unit_normalization() -> None:
    field = FieldSpec(
        name="temperature",
        semantic_id="temperature",
        json_schema={"type": "number"},
        unit="degC",
        unit_normalization=UnitNormalizationSpec(
            dimension="temperature",
            canonical_unit="K",
            scale=1.0,
            offset=273.15,
        ),
    )
    endpoint = EndpointSpec(
        name="read",
        read_only=True,
        output_fields=[field],
    )
    tool = ToolSpec(name="temperature_provider", endpoints=[endpoint])
    registry = InMemoryRegistry()
    registry.register(tool)
    call = ToolCall(
        tool="temperature_provider",
        endpoint="read",
        fields=["temperature"],
        schema_fingerprint=endpoint.fingerprint,
        tool_fingerprint=tool.fingerprint,
    )
    executor = RegistryExecutor(registry)
    executor.bind(
        "temperature_provider",
        lambda endpoint_name, arguments: {"temperature": 25.0},
    )

    result = await executor.execute_call(call)

    assert result.data["temperature"] == pytest.approx(298.15)
    assert result.field_contracts["temperature"].source_unit == "degC"
    assert result.field_contracts["temperature"].unit == "K"



@pytest.mark.asyncio
async def test_provider_source_path_is_canonicalized_before_unit_normalization() -> None:
    field = FieldSpec(
        name="elastic_modulus",
        semantic_id="elastic_modulus",
        json_schema={"type": "number"},
        path=["elasticity", "_provider_bulk_modulus"],
        result_path=["elastic_modulus"],
        unit="GPa",
        unit_normalization=UnitNormalizationSpec(
            dimension="pressure",
            canonical_unit="Pa",
            scale=1e9,
        ),
    )
    endpoint = EndpointSpec(
        name="read",
        read_only=True,
        output_fields=[field],
        output_schema={
            "type": "object",
            "properties": {
                "elasticity": {
                    "type": "object",
                    "properties": {
                        "_provider_bulk_modulus": {"type": "number"},
                    },
                    "required": ["_provider_bulk_modulus"],
                }
            },
            "required": ["elasticity"],
        },
    )
    tool = ToolSpec(name="provider_specific", endpoints=[endpoint])
    registry = InMemoryRegistry()
    registry.register(tool)
    call = ToolCall(
        tool="provider_specific",
        endpoint="read",
        fields=["elastic_modulus"],
        schema_fingerprint=endpoint.fingerprint,
        tool_fingerprint=tool.fingerprint,
    )

    executor = RegistryExecutor(registry)
    executor.bind(
        "provider_specific",
        lambda endpoint_name, arguments: {
            "elasticity": {
                "_provider_bulk_modulus": 130.0,
            }
        },
    )

    result = await executor.execute_call(call)

    assert result.data == {"elastic_modulus": 130_000_000_000.0}
    contract = result.field_contracts["elastic_modulus"]
    assert contract.semantic_id == "elastic_modulus"
    assert contract.json_schema == {"type": "number"}
    assert contract.source_unit == "GPa"
    assert contract.unit == "Pa"
    assert contract.dimension == "pressure"



def test_text_field_accepts_explicit_string_type_without_unit() -> None:
    field = FieldSpec(
        name="abstract",
        semantic_id="document_text",
        json_schema={"type": "string"},
        aliases=["paper abstract", "논문 초록"],
    )

    assert field.unit is None
    assert field.unit_normalization is None
    assert field.json_schema == {"type": "string"}


def test_untyped_text_like_field_can_remain_unitless() -> None:
    field = FieldSpec(
        name="web_snippet",
        semantic_id="document_text",
        aliases=["snippet", "검색 결과"],
    )

    assert field.unit is None
    assert field.json_schema == {}


def test_unitless_text_fields_can_fallback_across_providers() -> None:
    registry = InMemoryRegistry()
    registry.register(
        ToolSpec(
            name="arxiv",
            provider="arxiv",
            access_mode="api",
            endpoints=[
                EndpointSpec(
                    name="search",
                    read_only=True,
                    output_fields=[
                        FieldSpec(
                            name="abstract",
                            semantic_id="document_text",
                            json_schema={"type": "string"},
                            aliases=["abstract", "논문 초록"],
                        )
                    ],
                )
            ],
        )
    )
    registry.register(
        ToolSpec(
            name="web",
            provider="web",
            access_mode="search",
            endpoints=[
                EndpointSpec(
                    name="search",
                    read_only=True,
                    output_fields=[
                        FieldSpec(
                            name="snippet",
                            semantic_id="document_text",
                            json_schema={"type": "string"},
                            aliases=["abstract", "논문 초록"],
                        )
                    ],
                )
            ],
        )
    )

    plan = SchemaPlanner(registry).plan(
        PlanRequest(
            query="논문 초록",
            preferred_tools=["arxiv"],
            fallback_scope="cross_provider",
        )
    )

    assert plan.calls[0].tool == "arxiv"
    route = plan.fallback_route(0)
    assert route is not None
    assert [call.tool for call in route.alternatives] == ["web"]


@pytest.mark.asyncio
async def test_unitless_text_tool_result_has_no_unit_contract() -> None:
    field = FieldSpec(
        name="abstract",
        semantic_id="document_text",
        json_schema={"type": "string"},
    )
    endpoint = EndpointSpec(
        name="read",
        read_only=True,
        output_fields=[field],
    )
    tool = ToolSpec(name="arxiv", endpoints=[endpoint])
    registry = InMemoryRegistry()
    registry.register(tool)
    executor = RegistryExecutor(registry)
    executor.bind(
        "arxiv",
        lambda endpoint_name, arguments: {
            "abstract": "A concise scientific abstract."
        },
    )
    call = ToolCall(
        tool="arxiv",
        endpoint="read",
        fields=["abstract"],
        schema_fingerprint=endpoint.fingerprint,
        tool_fingerprint=tool.fingerprint,
    )

    result = await executor.execute_call(call)

    contract = result.field_contracts["abstract"]
    assert result.data == {"abstract": "A concise scientific abstract."}
    assert contract.json_schema == {"type": "string"}
    assert contract.source_unit is None
    assert contract.unit is None
    assert contract.dimension is None


def test_unitless_text_field_cannot_substitute_unit_bearing_quantity() -> None:
    registry = InMemoryRegistry()
    registry.register(
        ToolSpec(
            name="numeric_provider",
            provider="provider_a",
            endpoints=[
                EndpointSpec(
                    name="read",
                    read_only=True,
                    output_fields=[
                        FieldSpec(
                            name="elastic_modulus",
                            semantic_id="elastic_modulus",
                            json_schema={"type": "number"},
                            unit="GPa",
                        )
                    ],
                )
            ],
        )
    )
    registry.register(
        ToolSpec(
            name="text_provider",
            provider="provider_b",
            endpoints=[
                EndpointSpec(
                    name="read",
                    read_only=True,
                    output_fields=[
                        FieldSpec(
                            name="elastic_modulus_text",
                            semantic_id="elastic_modulus",
                            json_schema={"type": "string"},
                            aliases=["탄성계수"],
                        )
                    ],
                )
            ],
        )
    )

    plan = SchemaPlanner(registry).plan(
        PlanRequest(
            query="탄성계수",
            preferred_tools=["numeric_provider"],
            fallback_scope="cross_provider",
        )
    )

    assert plan.calls[0].tool == "numeric_provider"
    assert plan.fallback_route(0) is None



def test_unitless_text_is_valid_when_units_are_not_requested() -> None:
    registry = InMemoryRegistry()
    registry.register(
        ToolSpec(
            name="arxiv",
            endpoints=[
                EndpointSpec(
                    name="search",
                    read_only=True,
                    output_fields=[
                        FieldSpec(
                            name="abstract",
                            semantic_id="document_text",
                            json_schema={"type": "string"},
                            aliases=["논문 초록"],
                        )
                    ],
                )
            ],
        )
    )

    plan = SchemaPlanner(registry).plan(
        PlanRequest(query="논문 초록")
    )

    assert plan.calls
    assert plan.calls[0].fields == ["abstract"]


def test_unitless_text_is_rejected_only_when_units_are_explicitly_required() -> None:
    registry = InMemoryRegistry()
    registry.register(
        ToolSpec(
            name="arxiv",
            endpoints=[
                EndpointSpec(
                    name="search",
                    read_only=True,
                    output_fields=[
                        FieldSpec(
                            name="abstract",
                            semantic_id="document_text",
                            json_schema={"type": "string"},
                            aliases=["논문 초록"],
                        )
                    ],
                )
            ],
        )
    )

    plan = SchemaPlanner(registry).plan(
        PlanRequest(
            query="논문 초록",
            evidence=EvidenceRequirements(units=True),
        )
    )

    assert plan.calls == []



@pytest.mark.asyncio
async def test_result_field_contracts_include_only_selected_fields() -> None:
    endpoint = EndpointSpec(
        name="read",
        read_only=True,
        output_fields=[
            FieldSpec(
                name="elastic_modulus",
                semantic_id="elastic_modulus",
                json_schema={"type": "number"},
                unit="GPa",
            ),
            FieldSpec(
                name="density",
                semantic_id="density",
                json_schema={"type": "number"},
                unit="g/cm3",
            ),
        ],
    )
    tool = ToolSpec(name="materials", endpoints=[endpoint])
    registry = InMemoryRegistry()
    registry.register(tool)
    executor = RegistryExecutor(registry)
    executor.bind(
        "materials",
        lambda endpoint_name, arguments: {
            "elastic_modulus": 130.0,
            "density": 2.33,
        },
    )
    call = ToolCall(
        tool="materials",
        endpoint="read",
        fields=["elastic_modulus"],
        schema_fingerprint=endpoint.fingerprint,
        tool_fingerprint=tool.fingerprint,
    )

    result = await executor.execute_call(call)

    assert result.data == {"elastic_modulus": 130.0}
    assert set(result.field_contracts) == {"elastic_modulus"}
    assert result.field_contracts["elastic_modulus"].unit == "GPa"
