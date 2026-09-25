from __future__ import annotations

import pytest

from schemarouter import (
    CallableDecisionBackend,
    DecisionPolicy,
    EndpointSpec,
    FieldSpec,
    InMemoryRegistry,
    PlanRequest,
    RegistryExecutor,
    SchemaPlanner,
    ToolCall,
    ToolSpec,
    compare_endpoint_specs,
)
from schemarouter.dashboard import render_dashboard
from schemarouter.inspection import inspect_registry, inspect_tool_spec


def _qualified_tool(
    name: str,
    *,
    provider: str,
    qualifiers: dict[str, str],
) -> ToolSpec:
    return ToolSpec(
        name=name,
        provider=provider,
        endpoints=[
            EndpointSpec(
                name="read",
                read_only=True,
                output_fields=[
                    FieldSpec(
                        name="elastic_modulus",
                        semantic_id="elastic_modulus",
                        aliases=["elastic modulus", "탄성계수"],
                        json_schema={"type": "number"},
                        unit="GPa",
                        qualifiers=qualifiers,
                    )
                ],
            )
        ],
    )


def test_field_qualifiers_are_optional_and_exact() -> None:
    field = FieldSpec(
        name="abstract",
        semantic_id="document_text",
        json_schema={"type": "string"},
    )

    assert field.qualifiers == {}

    qualified = FieldSpec(
        name="elastic_modulus",
        semantic_id="elastic_modulus",
        json_schema={"type": "number"},
        unit="GPa",
        qualifiers={
            "temperature": "300 K",
            "phase": "alpha",
        },
    )

    assert qualified.qualifiers == {
        "temperature": "300 K",
        "phase": "alpha",
    }


@pytest.mark.parametrize(
    ("qualifiers", "message"),
    [
        ({"": "300 K"}, "qualifier keys"),
        ({" temperature": "300 K"}, "qualifier keys"),
        ({"temperature": ""}, "qualifier values"),
        ({"temperature": "300 K "}, "qualifier values"),
    ],
)
def test_field_qualifiers_reject_empty_or_padded_tags(
    qualifiers: dict[str, str],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        FieldSpec(
            name="elastic_modulus",
            qualifiers=qualifiers,
        )


def test_field_qualifiers_participate_in_fingerprint_canonically() -> None:
    first = EndpointSpec(
        name="read",
        output_fields=[
            FieldSpec(
                name="elastic_modulus",
                qualifiers={"temperature": "300 K", "phase": "alpha"},
            )
        ],
    )
    reordered = EndpointSpec(
        name="read",
        output_fields=[
            FieldSpec(
                name="elastic_modulus",
                qualifiers={"phase": "alpha", "temperature": "300 K"},
            )
        ],
    )
    changed = EndpointSpec(
        name="read",
        output_fields=[
            FieldSpec(
                name="elastic_modulus",
                qualifiers={"temperature": "500 K", "phase": "alpha"},
            )
        ],
    )

    assert first.fingerprint == reordered.fingerprint
    assert first.fingerprint != changed.fingerprint


def test_same_scientific_qualifiers_allow_cross_provider_fallback() -> None:
    registry = InMemoryRegistry()
    registry.register(
        _qualified_tool(
            "provider_a",
            provider="a",
            qualifiers={
                "temperature": "300 K",
                "phase": "alpha",
            },
        )
    )
    registry.register(
        _qualified_tool(
            "provider_b",
            provider="b",
            qualifiers={
                "phase": "alpha",
                "temperature": "300 K",
            },
        )
    )

    plan = SchemaPlanner(registry).plan(
        PlanRequest(
            query="탄성계수",
            preferred_tools=["provider_a"],
            fallback_scope="cross_provider",
        )
    )

    route = plan.fallback_route(0)
    assert route is not None
    assert [call.tool for call in route.alternatives] == ["provider_b"]


@pytest.mark.parametrize(
    "alternative_qualifiers",
    [
        {"temperature": "500 K", "phase": "alpha"},
        {"temperature": "300 K", "phase": "beta"},
        {"temperature": "300 K"},
        {},
    ],
)
def test_different_or_missing_scientific_qualifiers_block_fallback(
    alternative_qualifiers: dict[str, str],
) -> None:
    registry = InMemoryRegistry()
    registry.register(
        _qualified_tool(
            "provider_a",
            provider="a",
            qualifiers={
                "temperature": "300 K",
                "phase": "alpha",
            },
        )
    )
    registry.register(
        _qualified_tool(
            "provider_b",
            provider="b",
            qualifiers=alternative_qualifiers,
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


def test_unitless_text_fields_can_carry_optional_qualifiers() -> None:
    field = FieldSpec(
        name="abstract",
        semantic_id="document_text",
        json_schema={"type": "string"},
        qualifiers={"language": "en"},
    )

    assert field.unit is None
    assert field.qualifiers == {"language": "en"}


@pytest.mark.asyncio
async def test_tool_result_preserves_only_selected_field_qualifiers() -> None:
    endpoint = EndpointSpec(
        name="read",
        read_only=True,
        output_fields=[
            FieldSpec(
                name="elastic_modulus",
                semantic_id="elastic_modulus",
                json_schema={"type": "number"},
                unit="GPa",
                qualifiers={
                    "temperature": "300 K",
                    "phase": "alpha",
                },
            ),
            FieldSpec(
                name="density",
                semantic_id="density",
                json_schema={"type": "number"},
                unit="g/cm3",
                qualifiers={"temperature": "300 K"},
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
    assert result.field_contracts["elastic_modulus"].qualifiers == {
        "temperature": "300 K",
        "phase": "alpha",
    }


def test_inspection_and_dashboard_expose_field_qualifiers() -> None:
    tool = _qualified_tool(
        "provider_a",
        provider="a",
        qualifiers={
            "temperature": "300 K",
            "orientation": "[100]",
        },
    )

    inspection = inspect_tool_spec(tool)
    field = inspection.endpoints[0].fields[0]

    assert field.qualifiers == {
        "temperature": "300 K",
        "orientation": "[100]",
    }

    registry = InMemoryRegistry()
    registry.register(tool)
    html = render_dashboard(inspect_registry(registry))
    assert "temperature=300 K" in html
    assert "orientation=[100]" in html


def test_schema_diff_marks_qualifier_drift_breaking() -> None:
    old = EndpointSpec(
        name="read",
        read_only=True,
        output_fields=[
            FieldSpec(
                name="elastic_modulus",
                semantic_id="elastic_modulus",
                qualifiers={"temperature": "300 K"},
            )
        ],
    )
    new = old.model_copy(deep=True)
    new.output_fields[0].qualifiers = {"temperature": "500 K"}

    report = compare_endpoint_specs(old, new)

    assert report.compatibility == "breaking"
    assert any(
        change.kind == "qualifiers_changed"
        and change.path.endswith(".qualifiers")
        for change in report.changes
    )



def test_query_qualifier_prefers_matching_endpoint() -> None:
    registry = InMemoryRegistry()
    registry.register(
        _qualified_tool(
            "provider_300k",
            provider="a",
            qualifiers={"temperature": "300 K"},
        )
    )
    registry.register(
        _qualified_tool(
            "provider_500k",
            provider="b",
            qualifiers={"temperature": "500 K"},
        )
    )

    plan = SchemaPlanner(registry).plan(
        PlanRequest(query="elastic modulus at 500 K")
    )

    assert [call.tool for call in plan.calls] == ["provider_500k"]
    assert plan.calls[0].explanation is not None
    assert any(
        component.kind == "field_qualifier"
        and component.matched == "elastic_modulus:temperature=500 K"
        for component in plan.calls[0].explanation.score_components
    )


def test_numeric_qualifier_does_not_match_inside_larger_number() -> None:
    registry = InMemoryRegistry()
    registry.register(
        _qualified_tool(
            "a_provider_300k",
            provider="a",
            qualifiers={"temperature": "300 K"},
        )
    )
    registry.register(
        _qualified_tool(
            "z_provider_1300k",
            provider="b",
            qualifiers={"temperature": "1300 K"},
        )
    )

    plan = SchemaPlanner(registry).plan(
        PlanRequest(query="elastic modulus at 1300 K")
    )

    assert [call.tool for call in plan.calls] == ["z_provider_1300k"]
    assert plan.calls[0].explanation is not None
    qualifier_components = [
        component
        for component in plan.calls[0].explanation.score_components
        if component.kind == "field_qualifier"
    ]
    assert [component.matched for component in qualifier_components] == [
        "elastic_modulus:temperature=1300 K"
    ]


def test_short_ascii_qualifier_does_not_create_accidental_route_bias() -> None:
    registry = InMemoryRegistry()
    registry.register(
        _qualified_tool(
            "provider_k",
            provider="a",
            qualifiers={"state": "K"},
        )
    )
    registry.register(
        _qualified_tool(
            "provider_other",
            provider="b",
            qualifiers={"state": "Q"},
        )
    )

    plan = SchemaPlanner(registry).plan(
        PlanRequest(query="bulk elastic modulus")
    )

    assert plan.calls
    assert all(
        component.kind != "field_qualifier"
        for component in (
            plan.calls[0].explanation.score_components
            if plan.calls[0].explanation
            else []
        )
    )


def test_field_decision_options_include_trusted_qualifiers() -> None:
    captured = {}

    def decide(request):
        captured["request"] = request
        return {"selections": [{"option_id": "field:0", "score": 1.0}]}

    registry = InMemoryRegistry()
    registry.register(
        _qualified_tool(
            "provider_a",
            provider="a",
            qualifiers={
                "temperature": "300 K",
                "phase": "alpha",
            },
        )
    )
    planner = SchemaPlanner(
        registry,
        decision_backend=CallableDecisionBackend(decide),
        decision_policy=DecisionPolicy(enabled=True, field_selection=True),
    )

    plan = planner.plan(PlanRequest(query="elastic modulus at 300 K"))

    assert plan.calls
    request = captured["request"]
    assert request.context["surface"] == "field_selection"
    assert "qualifiers: phase=alpha, temperature=300 K" in request.options[0].description
