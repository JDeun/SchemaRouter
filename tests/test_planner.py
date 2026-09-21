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


@pytest.mark.parametrize("surface", ["field_selection", "evidence_sufficiency"])
def test_reserved_decision_surfaces_fail_closed(surface: str) -> None:
    reg = registry()
    backend = CallableDecisionBackend(
        lambda _: {"selections": [{"option_id": "candidate:0"}]}
    )
    with pytest.raises(PlanningError, match="reserved"):
        SchemaPlanner(
            reg,
            decision_backend=backend,
            decision_policy=DecisionPolicy(enabled=True, **{surface: True}),
        )
