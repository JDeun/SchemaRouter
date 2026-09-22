import pytest

from schemarouter import (
    CallableDecisionBackend,
    DecisionPolicy,
    EndpointSpec,
    FieldSpec,
    InMemoryRegistry,
    ParameterSpec,
    PlanningError,
    PlanRequest,
    SchemaPlanner,
    ToolSpec,
)


def registry() -> InMemoryRegistry:
    reg = InMemoryRegistry()
    reg.register(
        ToolSpec(
            name="materials",
            endpoints=[
                EndpointSpec(
                    name="search",
                    description="Search material properties",
                    parameters=[ParameterSpec(name="formula", required=True)],
                    output_fields=[
                        FieldSpec(name="material_id", identifier=True),
                        FieldSpec(name="band_gap", aliases=["band gap"], unit="eV"),
                        FieldSpec(
                            name="formation_energy_per_atom",
                            aliases=["formation energy"],
                            unit="eV/atom",
                        ),
                        FieldSpec(name="density", unit="g/cm3"),
                    ],
                )
            ],
            source_type="calculated",
            license="CC BY 4.0",
        )
    )
    return reg


def test_planner_projects_matched_fields_and_identifier() -> None:
    reg = registry()
    plan = SchemaPlanner(reg).plan(
        PlanRequest(
            query="LiFePO4 band gap and formation energy",
            arguments={"formula": "LiFePO4", "made_up": 1},
        )
    )

    assert plan.executable
    call = plan.calls[0]
    assert call.tool == "materials"
    assert call.fields == ["material_id", "band_gap", "formation_energy_per_atom"]
    assert call.arguments == {"formula": "LiFePO4"}
    assert call.evidence.license is True
    assert call.evidence.provenance is True
    assert call.evidence.units is True
    assert "made_up" in plan.warnings[0]


def test_planner_favors_recall_when_field_intent_is_ambiguous() -> None:
    reg = registry()
    plan = SchemaPlanner(reg).plan(
        PlanRequest(query="tell me about this material", arguments={"formula": "Si"})
    )
    call = plan.calls[0]
    assert call.fields == [
        "material_id",
        "band_gap",
        "formation_energy_per_atom",
        "density",
    ]


def test_missing_required_argument_is_explicit() -> None:
    reg = registry()
    plan = SchemaPlanner(reg).plan("band gap")
    assert plan.calls[0].missing_required_arguments == ["formula"]
    assert plan.executable is False


def test_decision_backend_is_off_by_default() -> None:
    reg = registry()
    backend = CallableDecisionBackend(
        lambda _: {"selections": [{"option_id": "candidate:999"}]}
    )
    plan = SchemaPlanner(reg, decision_backend=backend).plan(
        PlanRequest(query="band gap", arguments={"formula": "Si"})
    )
    assert plan.calls[0].endpoint == "search"


def test_enabled_decision_policy_requires_backend() -> None:
    reg = registry()
    with pytest.raises(PlanningError, match="no decision backend"):
        SchemaPlanner(
            reg,
            decision_policy=DecisionPolicy(enabled=True, endpoint_selection=True),
        )


def test_decision_backend_can_select_from_bounded_candidates() -> None:
    reg = registry()
    reg.register(
        ToolSpec(
            name="secondary",
            endpoints=[
                EndpointSpec(
                    name="lookup",
                    description="band gap lookup",
                    output_fields=[FieldSpec(name="band_gap")],
                )
            ],
        )
    )
    backend = CallableDecisionBackend(
        lambda request: {
            "selections": [
                {
                    "option_id": next(
                        option.id
                        for option in request.options
                        if option.label == "secondary.lookup"
                    ),
                    "score": 0.9,
                }
            ]
        }
    )
    plan = SchemaPlanner(
        reg,
        decision_backend=backend,
        decision_policy=DecisionPolicy(enabled=True, endpoint_selection=True),
    ).plan("band gap")
    assert len(plan.calls) == 1
    assert plan.calls[0].tool == "secondary"


def test_invalid_decision_falls_back_to_deterministic_by_default() -> None:
    reg = registry()
    backend = CallableDecisionBackend(
        lambda _: {"selections": [{"option_id": "candidate:evil"}]}
    )
    plan = SchemaPlanner(
        reg,
        decision_backend=backend,
        decision_policy=DecisionPolicy(enabled=True, endpoint_selection=True),
    ).plan(PlanRequest(query="band gap", arguments={"formula": "Si"}))
    assert plan.calls[0].tool == "materials"
    assert any("decision backend fallback" in warning for warning in plan.warnings)


def test_invalid_decision_can_fail_closed_without_fallback() -> None:
    reg = registry()
    backend = CallableDecisionBackend(
        lambda _: {"selections": [{"option_id": "candidate:evil"}]}
    )
    planner = SchemaPlanner(
        reg,
        decision_backend=backend,
        decision_policy=DecisionPolicy(
            enabled=True,
            endpoint_selection=True,
            fallback="error",
        ),
    )
    with pytest.raises(PlanningError, match="unknown option"):
        planner.plan("band gap")


def test_evidence_sufficiency_decision_surface_remains_reserved() -> None:
    reg = registry()
    backend = CallableDecisionBackend(
        lambda _: {"selections": [{"option_id": "candidate:0"}]}
    )
    with pytest.raises(PlanningError, match="reserved"):
        SchemaPlanner(
            reg,
            decision_backend=backend,
            decision_policy=DecisionPolicy(
                enabled=True,
                evidence_sufficiency=True,
            ),
        )


def test_field_decision_selects_only_declared_fields_and_preserves_identifier() -> None:
    reg = registry()

    def choose_density(request):
        assert request.context["surface"] == "field_selection"
        assert request.context["tool"] == "materials"
        assert request.context["endpoint"] == "search"
        assert [option.label for option in request.options] == [
            "band_gap",
            "formation_energy_per_atom",
            "density",
        ]
        density = next(option for option in request.options if option.label == "density")
        return {"selections": [{"option_id": density.id, "score": 0.9}]}

    plan = SchemaPlanner(
        reg,
        decision_backend=CallableDecisionBackend(choose_density),
        decision_policy=DecisionPolicy(enabled=True, field_selection=True),
    ).plan(
        PlanRequest(
            query="tell me about this material",
            arguments={"formula": "Si"},
        )
    )

    assert plan.calls[0].fields == ["material_id", "density"]
    assert plan.calls[0].evidence.units is True


def test_field_decision_bound_does_not_exceed_deterministic_answer_width() -> None:
    reg = registry()

    def inspect_request(request):
        assert request.max_selections == 2
        selected = [
            option.id
            for option in request.options
            if option.label in {"band_gap", "formation_energy_per_atom"}
        ]
        return {"selections": [{"option_id": option_id} for option_id in selected]}

    plan = SchemaPlanner(
        reg,
        decision_backend=CallableDecisionBackend(inspect_request),
        decision_policy=DecisionPolicy(enabled=True, field_selection=True),
    ).plan(
        PlanRequest(
            query="band gap and formation energy",
            arguments={"formula": "Si"},
        )
    )

    assert plan.calls[0].fields == [
        "material_id",
        "band_gap",
        "formation_energy_per_atom",
    ]


def test_invalid_field_decision_falls_back_to_deterministic_projection() -> None:
    reg = registry()
    backend = CallableDecisionBackend(
        lambda _: {"selections": [{"option_id": "field:999"}]}
    )

    plan = SchemaPlanner(
        reg,
        decision_backend=backend,
        decision_policy=DecisionPolicy(enabled=True, field_selection=True),
    ).plan(
        PlanRequest(
            query="band gap",
            arguments={"formula": "Si"},
        )
    )

    assert plan.calls[0].fields == ["material_id", "band_gap"]
    assert any("field decision fallback" in warning for warning in plan.warnings)


def test_field_decision_abstention_falls_back_to_deterministic_projection() -> None:
    reg = registry()

    plan = SchemaPlanner(
        reg,
        decision_backend=CallableDecisionBackend(lambda _: {"abstained": True}),
        decision_policy=DecisionPolicy(enabled=True, field_selection=True),
    ).plan(
        PlanRequest(
            query="band gap",
            arguments={"formula": "Si"},
        )
    )

    assert plan.calls[0].fields == ["material_id", "band_gap"]
    assert any(
        "field decision backend abstained" in warning
        for warning in plan.warnings
    )


def test_invalid_field_decision_can_fail_closed_without_fallback() -> None:
    reg = registry()
    planner = SchemaPlanner(
        reg,
        decision_backend=CallableDecisionBackend(
            lambda _: {"selections": [{"option_id": "field:999"}]}
        ),
        decision_policy=DecisionPolicy(
            enabled=True,
            field_selection=True,
            fallback="error",
        ),
    )

    with pytest.raises(PlanningError, match="unknown option"):
        planner.plan(
            PlanRequest(
                query="band gap",
                arguments={"formula": "Si"},
            )
        )


@pytest.mark.asyncio
async def test_async_field_decision_uses_async_backend() -> None:
    reg = registry()

    async def choose_formation_energy(request):
        option = next(
            option
            for option in request.options
            if option.label == "formation_energy_per_atom"
        )
        return {"selections": [{"option_id": option.id, "score": 0.8}]}

    plan = await SchemaPlanner(
        reg,
        decision_backend=CallableDecisionBackend(choose_formation_energy),
        decision_policy=DecisionPolicy(enabled=True, field_selection=True),
    ).aplan(
        PlanRequest(
            query="tell me about this material",
            arguments={"formula": "Si"},
        )
    )

    assert plan.calls[0].fields == [
        "material_id",
        "formation_energy_per_atom",
    ]


def test_decision_abstention_falls_back_to_deterministic() -> None:
    reg = registry()
    backend = CallableDecisionBackend(
        lambda _: {"abstained": True},
    )
    plan = SchemaPlanner(
        reg,
        decision_backend=backend,
        decision_policy=DecisionPolicy(enabled=True, endpoint_selection=True),
    ).plan(PlanRequest(query="band gap", arguments={"formula": "Si"}))

    assert plan.calls[0].tool == "materials"
    assert any("decision backend abstained" in warning for warning in plan.warnings)


def test_decision_provider_error_falls_back_to_deterministic() -> None:
    reg = registry()

    def failing_backend(_: object) -> dict[str, object]:
        raise RuntimeError("provider unavailable")

    plan = SchemaPlanner(
        reg,
        decision_backend=CallableDecisionBackend(failing_backend),
        decision_policy=DecisionPolicy(enabled=True, endpoint_selection=True),
    ).plan(PlanRequest(query="band gap", arguments={"formula": "Si"}))

    assert plan.calls[0].tool == "materials"
    assert any("decision backend fallback: RuntimeError" in warning for warning in plan.warnings)

