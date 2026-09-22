import pytest

from schemarouter import (
    CallableDecisionBackend,
    DecisionPolicy,
    EndpointSpec,
    EvidenceRequirements,
    FieldSpec,
    InMemoryRegistry,
    PlanningError,
    PlanRequest,
    SchemaPlanner,
    ToolSpec,
)


def registry(
    *,
    tool_source_type: str | None = "calculated",
    tool_license: str | None = "CC BY 4.0",
    band_gap_unit: str | None = "eV",
) -> InMemoryRegistry:
    reg = InMemoryRegistry()
    reg.register(
        ToolSpec(
            name="materials",
            description="Materials property database",
            source_type=tool_source_type,
            license=tool_license,
            endpoints=[
                EndpointSpec(
                    name="search",
                    description="Search material properties including band gap",
                    output_fields=[
                        FieldSpec(
                            name="material_id",
                            identifier=True,
                            aliases=["id"],
                        ),
                        FieldSpec(
                            name="band_gap",
                            aliases=["band gap"],
                            unit=band_gap_unit,
                            source_type=tool_source_type,
                            license=tool_license,
                        ),
                    ],
                    read_only=True,
                )
            ],
        )
    )
    return reg


def evidence_request() -> PlanRequest:
    return PlanRequest(
        query="band gap",
        evidence=EvidenceRequirements(
            provenance=True,
            license=True,
            units=True,
            source_type="calculated",
        ),
    )


def test_evidence_surface_is_independently_enabled() -> None:
    policy = DecisionPolicy(enabled=True, evidence_sufficiency=True)

    assert policy.evidence_sufficiency_enabled is True
    assert policy.candidate_selection_enabled is False
    assert policy.field_selection_enabled is False
    assert policy.reserved_surfaces_enabled is False


def test_evidence_backend_receives_only_bounded_binary_decision_after_local_check() -> None:
    seen = {}

    def decide(request):
        seen["request"] = request
        return {
            "selections": [
                {
                    "option_id": "evidence:sufficient",
                    "score": 0.9,
                }
            ]
        }

    plan = SchemaPlanner(
        registry(),
        decision_backend=CallableDecisionBackend(decide),
        decision_policy=DecisionPolicy(
            enabled=True,
            evidence_sufficiency=True,
        ),
    ).plan(evidence_request())

    assert len(plan.calls) == 1
    request = seen["request"]
    assert request.max_selections == 1
    assert [option.id for option in request.options] == [
        "evidence:sufficient",
        "evidence:insufficient",
    ]
    assert request.context["surface"] == "evidence_sufficiency"
    assert request.context["requested"] == {
        "provenance": True,
        "license": True,
        "units": True,
        "source_type": "calculated",
    }
    assert request.context["available"] == {
        "provenance": True,
        "license": True,
        "units": True,
        "source_type": True,
    }


def test_evidence_backend_can_only_veto_locally_sufficient_call() -> None:
    plan = SchemaPlanner(
        registry(),
        decision_backend=CallableDecisionBackend(
            lambda _: {
                "selections": [{"option_id": "evidence:insufficient"}],
            }
        ),
        decision_policy=DecisionPolicy(
            enabled=True,
            evidence_sufficiency=True,
        ),
    ).plan(evidence_request())

    assert plan.calls == []
    assert any(
        "evidence decision marked evidence insufficient" in warning
        for warning in plan.warnings
    )


def test_local_evidence_failure_never_calls_provider_or_gets_upgraded() -> None:
    called = False

    def must_not_run(_):
        nonlocal called
        called = True
        return {
            "selections": [{"option_id": "evidence:sufficient"}],
        }

    plan = SchemaPlanner(
        registry(tool_license=None),
        decision_backend=CallableDecisionBackend(must_not_run),
        decision_policy=DecisionPolicy(
            enabled=True,
            evidence_sufficiency=True,
        ),
    ).plan(evidence_request())

    assert called is False
    assert plan.calls == []
    assert any("local evidence insufficient: license" in warning for warning in plan.warnings)


def test_missing_units_fail_local_evidence_check() -> None:
    plan = SchemaPlanner(
        registry(band_gap_unit=None),
        decision_backend=CallableDecisionBackend(
            lambda _: {
                "selections": [{"option_id": "evidence:sufficient"}],
            }
        ),
        decision_policy=DecisionPolicy(
            enabled=True,
            evidence_sufficiency=True,
        ),
    ).plan(evidence_request())

    assert plan.calls == []
    assert any("local evidence insufficient: units" in warning for warning in plan.warnings)


def test_source_type_mismatch_cannot_be_upgraded_by_provider() -> None:
    called = False

    def must_not_run(_):
        nonlocal called
        called = True
        return {
            "selections": [{"option_id": "evidence:sufficient"}],
        }

    plan = SchemaPlanner(
        registry(tool_source_type="experimental"),
        decision_backend=CallableDecisionBackend(must_not_run),
        decision_policy=DecisionPolicy(
            enabled=True,
            evidence_sufficiency=True,
        ),
    ).plan(evidence_request())

    assert called is False
    assert plan.calls == []
    assert any(
        "source_type=calculated" in warning
        for warning in plan.warnings
    )


def test_local_evidence_failure_can_fail_closed_with_error_policy() -> None:
    planner = SchemaPlanner(
        registry(tool_license=None),
        decision_backend=CallableDecisionBackend(
            lambda _: {
                "selections": [{"option_id": "evidence:sufficient"}],
            }
        ),
        decision_policy=DecisionPolicy(
            enabled=True,
            evidence_sufficiency=True,
            fallback="error",
        ),
    )

    with pytest.raises(PlanningError, match="local evidence insufficient: license"):
        planner.plan(evidence_request())


def test_evidence_backend_abstention_falls_back_to_local_assessment() -> None:
    plan = SchemaPlanner(
        registry(),
        decision_backend=CallableDecisionBackend(
            lambda _: {"abstained": True},
        ),
        decision_policy=DecisionPolicy(
            enabled=True,
            evidence_sufficiency=True,
        ),
    ).plan(evidence_request())

    assert len(plan.calls) == 1
    assert any(
        "evidence decision backend abstained" in warning
        for warning in plan.warnings
    )


def test_invalid_evidence_decision_falls_back_to_local_assessment() -> None:
    plan = SchemaPlanner(
        registry(),
        decision_backend=CallableDecisionBackend(
            lambda _: {
                "selections": [{"option_id": "evidence:unknown"}],
            }
        ),
        decision_policy=DecisionPolicy(
            enabled=True,
            evidence_sufficiency=True,
        ),
    ).plan(evidence_request())

    assert len(plan.calls) == 1
    assert any(
        "evidence decision fallback" in warning
        for warning in plan.warnings
    )


def test_invalid_evidence_decision_can_fail_closed() -> None:
    planner = SchemaPlanner(
        registry(),
        decision_backend=CallableDecisionBackend(
            lambda _: {
                "selections": [{"option_id": "evidence:unknown"}],
            }
        ),
        decision_policy=DecisionPolicy(
            enabled=True,
            evidence_sufficiency=True,
            fallback="error",
        ),
    )

    with pytest.raises(PlanningError, match="unknown option"):
        planner.plan(evidence_request())


def test_evidence_surface_is_noop_when_request_has_no_evidence_requirements() -> None:
    called = False

    def must_not_run(_):
        nonlocal called
        called = True
        return {
            "selections": [{"option_id": "evidence:insufficient"}],
        }

    plan = SchemaPlanner(
        registry(),
        decision_backend=CallableDecisionBackend(must_not_run),
        decision_policy=DecisionPolicy(
            enabled=True,
            evidence_sufficiency=True,
        ),
    ).plan(PlanRequest(query="band gap"))

    assert called is False
    assert len(plan.calls) == 1


@pytest.mark.asyncio
async def test_async_evidence_sufficiency_uses_async_backend() -> None:
    async def decide(request):
        assert request.context["surface"] == "evidence_sufficiency"
        return {
            "selections": [{"option_id": "evidence:sufficient"}],
        }

    plan = await SchemaPlanner(
        registry(),
        decision_backend=CallableDecisionBackend(decide),
        decision_policy=DecisionPolicy(
            enabled=True,
            evidence_sufficiency=True,
        ),
    ).aplan(evidence_request())

    assert len(plan.calls) == 1
    assert plan.calls[0].evidence.provenance is True
    assert plan.calls[0].evidence.license is True
    assert plan.calls[0].evidence.units is True
    assert plan.calls[0].evidence.source_type == "calculated"
