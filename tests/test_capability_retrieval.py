from __future__ import annotations

import pytest

from schemarouter import (
    EndpointSpec,
    FieldSpec,
    InMemoryRegistry,
    ParameterSpec,
    PlanRequest,
    PlanningError,
    QueryIntent,
    SchemaRouter,
    ToolSpec,
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

    field = first.output_fields[0]
    assert field.semantic_id == "material.youngs_modulus"
    assert field.json_schema == {"type": "number"}
    assert field.unit == "GPa"
    assert field.unit_normalization is not None
    assert field.unit_normalization.dimension == "elastic_modulus"
    assert field.unit_normalization.canonical_unit == "GPa"
    assert field.qualifiers == {"temperature": "300 K"}


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
