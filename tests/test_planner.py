from schemarouter import (
    EndpointSpec,
    FieldSpec,
    InMemoryRegistry,
    ParameterSpec,
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
