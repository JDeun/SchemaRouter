from __future__ import annotations

import pytest

from schemarouter import (
    CallableDecisionBackend,
    CapabilityFieldContract,
    EndpointSpec,
    FieldSpec,
    InMemoryRegistry,
    ObservedStateField,
    ParameterSpec,
    PlanningError,
    PlanRequest,
    QueryIntent,
    SchemaRouter,
    ToolSpec,
    TypedExecutionState,
    UnitNormalizationSpec,
)


def make_retrieval_router() -> SchemaRouter:
    router = SchemaRouter(registry=InMemoryRegistry())
    router.add_tool(
        ToolSpec(
            name="materials",
            description="Materials property service",
            provider="materials_project",
            access_mode="openapi",
            source_type="calculated",
            license="CC BY 4.0",
            endpoints=[
                EndpointSpec(
                    name="current",
                    description="Get current Young's modulus",
                    read_only=True,
                    parameters=[
                        ParameterSpec(
                            name="material_id",
                            required=True,
                            json_schema={"type": "string"},
                        )
                    ],
                    output_fields=[
                        FieldSpec(
                            name="youngs_modulus",
                            semantic_id="material.youngs_modulus",
                            description="Young's modulus",
                            aliases=["elastic modulus"],
                            json_schema={"type": "number"},
                            unit="GPa",
                            unit_normalization=UnitNormalizationSpec(
                                dimension="elastic_modulus",
                                canonical_unit="GPa",
                            ),
                            qualifiers={"temperature": "300 K"},
                        )
                    ],
                ),
                EndpointSpec(
                    name="history",
                    description="Get historical Young's modulus values",
                    read_only=True,
                    parameters=[
                        ParameterSpec(
                            name="material_id",
                            required=True,
                            json_schema={"type": "string"},
                        )
                    ],
                    output_fields=[
                        FieldSpec(
                            name="youngs_modulus",
                            semantic_id="material.youngs_modulus",
                            json_schema={
                                "type": "array",
                                "items": {"type": "number"},
                            },
                            unit="GPa",
                        )
                    ],
                ),
            ],
        )
    )
    router.add_tool(
        ToolSpec(
            name="papers",
            description="Scientific paper service",
            provider="arxiv",
            access_mode="api",
            endpoints=[
                EndpointSpec(
                    name="search",
                    description="Search scientific papers",
                    read_only=True,
                    parameters=[
                        ParameterSpec(
                            name="query",
                            required=True,
                            json_schema={"type": "string"},
                        )
                    ],
                    output_fields=[
                        FieldSpec(
                            name="abstract",
                            semantic_id="document.abstract",
                            json_schema={"type": "string"},
                        )
                    ],
                )
            ],
        )
    )
    return router


def test_retrieve_returns_typed_ranked_registered_candidates() -> None:
    router = make_retrieval_router()

    result = router.retrieve(
        PlanRequest(
            query="current Young's modulus for MAT-7",
            arguments={"material_id": "MAT-7"},
        ),
        k=2,
    )

    assert result.query == "current Young's modulus for MAT-7"
    assert result.requested_k == 2
    assert result.total_ranked == 3
    assert result.executable_only is False
    assert len(result.candidates) == 2

    first = result.candidates[0]
    assert first.rank == 1
    assert first.route_id == "materials.current"
    assert first.tool == "materials"
    assert first.endpoint == "current"
    assert first.provider == "materials_project"
    assert first.access_mode == "openapi"
    assert first.source_type == "calculated"
    assert first.license == "CC BY 4.0"
    assert first.read_only is True
    assert first.destructive is None
    assert first.tool_fingerprint == router.registry.get("materials").fingerprint
    assert first.endpoint_fingerprint == router.registry.endpoint(
        "materials",
        "current",
    ).fingerprint
    assert first.input_schema == {
        "type": "object",
        "properties": {"material_id": {"type": "string"}},
        "additionalProperties": False,
        "required": ["material_id"],
    }
    assert first.output_schema == {
        "type": "object",
        "properties": {"youngs_modulus": {"type": "number"}},
    }

    field = first.output_fields[0]
    assert field.semantic_id == "material.youngs_modulus"
    assert field.json_schema == {"type": "number"}
    assert field.unit == "GPa"
    assert field.unit_normalization is not None
    assert field.unit_normalization.dimension == "elastic_modulus"
    assert field.unit_normalization.canonical_unit == "GPa"
    assert field.qualifiers == {"temperature": "300 K"}


def test_retrieve_preserves_explicit_complex_endpoint_schemas() -> None:
    router = SchemaRouter()
    input_schema = {
        "type": "object",
        "properties": {
            "mode": {"type": "string", "enum": ["fast", "safe"]},
            "payload": {
                "oneOf": [
                    {"type": "string"},
                    {"type": "object", "additionalProperties": False},
                ]
            },
        },
        "required": ["mode", "payload"],
        "additionalProperties": False,
    }
    output_schema = {
        "oneOf": [
            {
                "type": "object",
                "properties": {"status": {"const": "ok"}},
                "required": ["status"],
                "additionalProperties": False,
            },
            {"type": "null"},
        ]
    }
    router.add_tool(
        ToolSpec(
            name="complex",
            endpoints=[
                EndpointSpec(
                    name="run",
                    description="Run complex operation",
                    read_only=True,
                    parameters=[
                        ParameterSpec(
                            name="mode",
                            required=True,
                            json_schema={"type": "string", "enum": ["fast", "safe"]},
                        ),
                        ParameterSpec(
                            name="payload",
                            required=True,
                            json_schema={
                                "oneOf": [
                                    {"type": "string"},
                                    {"type": "object", "additionalProperties": False},
                                ]
                            },
                        ),
                    ],
                    input_schema=input_schema,
                    output_schema=output_schema,
                )
            ],
        )
    )

    candidate = router.retrieve("run complex operation", k=1).candidates[0]

    assert candidate.input_schema == input_schema
    assert candidate.output_schema == output_schema


def test_retrieve_tie_order_is_deterministic_and_registered_only() -> None:
    router = SchemaRouter()
    for name in ("b_tool", "a_tool"):
        router.add_tool(
            ToolSpec(
                name=name,
                description="same service",
                endpoints=[
                    EndpointSpec(
                        name="read",
                        description="same capability",
                        read_only=True,
                        output_fields=[FieldSpec(name="value")],
                    )
                ],
            )
        )

    first = router.retrieve("completely unrelated query", k=10)
    second = router.retrieve("completely unrelated query", k=10)

    assert [item.route_id for item in first.candidates] == [
        "a_tool.read",
        "b_tool.read",
    ]
    assert [
        (item.route_id, item.score)
        for item in first.candidates
    ] == [
        (item.route_id, item.score)
        for item in second.candidates
    ]
    assert first.total_ranked == 2


@pytest.mark.parametrize("invalid_k", [0, -1, True, False])
def test_retrieve_rejects_invalid_k(invalid_k) -> None:
    router = make_retrieval_router()
    with pytest.raises(ValueError, match="k must be an integer >= 1"):
        router.retrieve("modulus", k=invalid_k)


def test_retrieve_executable_filters_unbound_routes_without_executing() -> None:
    router = make_retrieval_router()
    plain = router.retrieve("current Young's modulus", k=5)
    assert {item.route_id for item in plain.candidates} == {
        "materials.current",
        "materials.history",
        "papers.search",
    }

    executable_before = router.retrieve_executable(
        "current Young's modulus",
        k=5,
    )
    assert executable_before.executable_only is True
    assert executable_before.candidates == []

    invoked = 0

    def invoker(endpoint: str, arguments: dict) -> dict:
        nonlocal invoked
        invoked += 1
        return {"youngs_modulus": 125.0}

    router.executor.bind("materials", invoker)

    executable_after = router.retrieve_executable(
        "current Young's modulus",
        k=5,
    )
    assert {
        item.route_id
        for item in executable_after.candidates
    } == {
        "materials.current",
        "materials.history",
    }
    assert invoked == 0


def test_retrieve_respects_bounded_unavailability() -> None:
    router = make_retrieval_router()
    assert "materials.current" in {
        item.route_id
        for item in router.retrieve("current Young's modulus", k=5).candidates
    }

    router.mark_access_unavailable("materials", "current", cooldown_seconds=60)

    result = router.retrieve("current Young's modulus", k=5)
    assert "materials.current" not in {
        item.route_id
        for item in result.candidates
    }


class AsyncAnalyzer:
    async def analyze(self, request: PlanRequest, registry) -> QueryIntent:
        del registry
        return QueryIntent(
            concepts=[*request.concepts, "youngs", "modulus"],
            preferred_tools=request.preferred_tools,
            arguments=request.arguments,
            evidence=request.evidence,
            field_evidence=request.field_evidence,
        )


@pytest.mark.asyncio
async def test_aretrieve_supports_async_analyzer() -> None:
    router = make_retrieval_router()
    router.planner.analyzer = AsyncAnalyzer()

    with pytest.raises(PlanningError, match="use await planner.aretrieve"):
        router.retrieve("Young's modulus", k=1)

    result = await router.aretrieve("Young's modulus", k=1)
    assert len(result.candidates) == 1
    assert result.candidates[0].route_id.startswith("materials.")


@pytest.mark.asyncio
async def test_aretrieve_executable_supports_async_analyzer() -> None:
    router = make_retrieval_router()
    router.planner.analyzer = AsyncAnalyzer()
    router.executor.bind(
        "materials",
        lambda endpoint, arguments: {"youngs_modulus": 125.0},
    )

    result = await router.aretrieve_executable("Young's modulus", k=5)
    assert result.executable_only is True
    assert {
        item.route_id
        for item in result.candidates
    } == {
        "materials.current",
        "materials.history",
    }


def test_configured_router_exposes_same_retrieval_surface() -> None:
    router = make_retrieval_router()
    configured = router.with_config({})

    direct = router.retrieve("Young's modulus", k=2)
    configured_result = configured.retrieve("Young's modulus", k=2)

    assert configured_result == direct


def test_planner_additional_availability_does_not_imply_executable() -> None:
    router = make_retrieval_router()

    result = router.planner.retrieve_with_additional_availability(
        "Young's modulus",
        lambda tool, endpoint: endpoint.name == "current",
        k=5,
    )

    assert result.executable_only is False
    assert [item.route_id for item in result.candidates] == [
        "materials.current"
    ]


def test_retrieval_result_is_detached_from_registry_state() -> None:
    router = make_retrieval_router()
    result = router.retrieve("current Young's modulus", k=1)
    candidate = result.candidates[0]

    original_endpoint = router.registry.endpoint(
        candidate.tool,
        candidate.endpoint,
    )
    original_field_name = original_endpoint.output_fields[0].name
    original_parameter_name = original_endpoint.parameters[0].name

    candidate.output_fields[0].name = "mutated-field"
    candidate.parameters[0].name = "mutated-parameter"
    candidate.input_schema["properties"]["material_id"]["type"] = "integer"
    candidate.output_schema["properties"]["youngs_modulus"]["type"] = "string"
    candidate.matched_fields.append("mutated-match")

    endpoint_after = router.registry.endpoint(
        candidate.tool,
        candidate.endpoint,
    )
    assert endpoint_after.output_fields[0].name == original_field_name
    assert endpoint_after.parameters[0].name == original_parameter_name

    fresh = router.retrieve("current Young's modulus", k=1)
    assert fresh.candidates[0].output_fields[0].name == original_field_name
    assert fresh.candidates[0].parameters[0].name == original_parameter_name
    assert fresh.candidates[0].input_schema["properties"]["material_id"]["type"] == "string"
    assert fresh.candidates[0].output_schema["properties"]["youngs_modulus"]["type"] == "number"
    assert "mutated-match" not in fresh.candidates[0].matched_fields


def test_retrieve_does_not_invoke_planning_candidate_recall_backend() -> None:
    router = make_retrieval_router()
    called = False

    def planning_recall_backend(_request):
        nonlocal called
        called = True
        raise AssertionError("public retrieve must stay deterministic")

    router.planner.candidate_recall_backend = CallableDecisionBackend(
        planning_recall_backend
    )

    result = router.retrieve("current Young's modulus", k=2)

    assert len(result.candidates) == 2
    assert called is False


def test_retrieve_routes_matches_full_retrieval_ranking() -> None:
    router = make_retrieval_router()

    routes = router.retrieve_routes("current Young's modulus", k=3)
    full = router.retrieve("current Young's modulus", k=3)

    assert routes.query == full.query
    assert routes.registry_version == full.registry_version
    assert routes.requested_k == full.requested_k
    assert routes.total_ranked == full.total_ranked
    assert [
        (
            item.rank,
            item.route_id,
            item.score,
            item.matched_fields,
            [component.model_dump() for component in item.score_components],
            item.selection_source,
            item.read_only,
            item.destructive,
            item.provider,
            item.access_mode,
            item.tool_fingerprint,
            item.endpoint_fingerprint,
        )
        for item in routes.candidates
    ] == [
        (
            item.rank,
            item.route_id,
            item.score,
            item.matched_fields,
            [component.model_dump() for component in item.score_components],
            item.selection_source,
            item.read_only,
            item.destructive,
            item.provider,
            item.access_mode,
            item.tool_fingerprint,
            item.endpoint_fingerprint,
        )
        for item in full.candidates
    ]


@pytest.mark.asyncio
async def test_aretrieve_routes_supports_async_analyzer() -> None:
    router = make_retrieval_router()
    router.planner.analyzer = AsyncAnalyzer()

    with pytest.raises(PlanningError, match="use await planner.aretrieve_routes"):
        router.retrieve_routes("Young's modulus", k=1)

    result = await router.aretrieve_routes("Young's modulus", k=1)
    assert len(result.candidates) == 1
    assert result.candidates[0].route_id.startswith("materials.")


def test_configured_router_exposes_route_retrieval_surface() -> None:
    router = make_retrieval_router()
    configured = router.with_config({})

    direct = router.retrieve_routes("Young's modulus", k=2)
    configured_result = configured.retrieve_routes("Young's modulus", k=2)

    assert configured_result == direct


def test_semantic_namespace_token_does_not_count_as_field_evidence() -> None:
    router = SchemaRouter()
    router.add_tool(
        ToolSpec(
            name="material_service",
            description="material property service",
            endpoints=[
                EndpointSpec(
                    name="lookup",
                    description="look up material properties",
                    read_only=True,
                    output_fields=[
                        FieldSpec(
                            name="youngs_modulus",
                            semantic_id="material.youngs_modulus",
                            aliases=["elastic modulus"],
                        )
                    ],
                )
            ],
        )
    )

    unsupported = router.retrieve_routes(
        PlanRequest(
            query="material unsupported_property",
            concepts=["unsupported_property"],
        ),
        k=1,
    )

    assert unsupported.candidates[0].route_id == "material_service.lookup"
    assert unsupported.candidates[0].matched_fields == []
    assert all(
        component.kind not in {"field_exact", "field_lexical", "field_substring"}
        for component in unsupported.candidates[0].score_components
    )


def test_retrieve_accepts_optional_typed_execution_state() -> None:
    router = make_retrieval_router()
    state = TypedExecutionState(
        observed_fields=[
            ObservedStateField(
                contract=CapabilityFieldContract(
                    semantic_id="resource.material_id",
                    json_schema={"type": "string"},
                ),
                stable_identifier="MAT-7",
            )
        ]
    )

    result = router.retrieve(
        "Young's modulus",
        k=3,
        execution_state=state,
        state_requirements={
            "materials.current": [CapabilityFieldContract(
                semantic_id="resource.material_id",
                json_schema={"type": "string"},
            )],
            "materials.history": [CapabilityFieldContract(
                semantic_id="missing.future.state",
                json_schema={"type": "string"},
            )],
        },
    )

    route_ids = [item.candidate.route_id for item in result.candidates]
    assert "materials.current" in route_ids
    assert "materials.history" not in route_ids


def test_retrieve_without_execution_state_preserves_stateless_contract() -> None:
    router = make_retrieval_router()

    result = router.retrieve("Young's modulus", k=2)

    assert result.executable_only is False
    assert all(hasattr(candidate, "route_id") for candidate in result.candidates)
