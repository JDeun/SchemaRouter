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
    ServerProjectionSpec,
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


def test_multi_call_planner_prefers_complementary_semantic_field_coverage() -> None:
    reg = InMemoryRegistry()
    for name, access_mode in (
        ("a_materials_openapi", "openapi"),
        ("b_materials_optimade", "optimade"),
    ):
        reg.register(
            ToolSpec(
                name=name,
                provider="materials_project",
                access_mode=access_mode,
                endpoints=[
                    EndpointSpec(
                        name="search",
                        read_only=True,
                        output_fields=[
                            FieldSpec(name="material_id", identifier=True),
                            FieldSpec(
                                name="band_gap",
                                semantic_id="band_gap",
                                aliases=["band gap"],
                                json_schema={"type": "number"},
                                unit="eV",
                            ),
                        ],
                    )
                ],
            )
        )
    reg.register(
        ToolSpec(
            name="z_arxiv",
            provider="arxiv",
            access_mode="api",
            endpoints=[
                EndpointSpec(
                    name="search",
                    read_only=True,
                    output_fields=[
                        FieldSpec(name="paper_id", identifier=True),
                        FieldSpec(
                            name="abstract",
                            semantic_id="document_abstract",
                            aliases=["paper abstract"],
                            json_schema={"type": "string"},
                        ),
                    ],
                )
            ],
        )
    )

    plan = SchemaPlanner(reg).plan(
        PlanRequest(
            query="band gap and paper abstract",
            max_calls=2,
        )
    )

    assert [call.tool for call in plan.calls] == [
        "a_materials_openapi",
        "z_arxiv",
    ]
    assert plan.calls[0].fields == ["material_id", "band_gap"]
    assert plan.calls[1].fields == ["paper_id", "abstract"]


def test_multi_call_field_coverage_respects_explicit_qualifiers() -> None:
    reg = InMemoryRegistry()
    for name, temperature in (
        ("a_elastic_300k", "300 K"),
        ("b_elastic_500k", "500 K"),
    ):
        reg.register(
            ToolSpec(
                name=name,
                provider="materials_project",
                access_mode="api",
                endpoints=[
                    EndpointSpec(
                        name="read",
                        read_only=True,
                        output_fields=[
                            FieldSpec(
                                name="elastic_modulus",
                                semantic_id="elastic_modulus",
                                aliases=["elastic modulus"],
                                json_schema={"type": "number"},
                                unit="GPa",
                                qualifiers={"temperature": temperature},
                            )
                        ],
                    )
                ],
            )
        )
    reg.register(
        ToolSpec(
            name="z_arxiv",
            provider="arxiv",
            access_mode="api",
            endpoints=[
                EndpointSpec(
                    name="search",
                    read_only=True,
                    output_fields=[
                        FieldSpec(
                            name="abstract",
                            semantic_id="document_abstract",
                            aliases=["paper abstract"],
                            json_schema={"type": "string"},
                        )
                    ],
                )
            ],
        )
    )

    plan = SchemaPlanner(reg).plan(
        PlanRequest(
            query="elastic modulus at 300 K and paper abstract",
            max_calls=2,
        )
    )

    assert [call.tool for call in plan.calls] == [
        "a_elastic_300k",
        "z_arxiv",
    ]


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


def test_evidence_sufficiency_surface_no_longer_blocks_planner_construction() -> None:
    reg = registry()
    planner = SchemaPlanner(
        reg,
        decision_backend=CallableDecisionBackend(
            lambda _: {"selections": [{"option_id": "evidence:sufficient"}]}
        ),
        decision_policy=DecisionPolicy(
            enabled=True,
            evidence_sufficiency=True,
        ),
    )

    plan = planner.plan("band gap")

    assert plan.calls


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




def test_decision_backend_does_not_expand_empty_lexical_recall_by_default() -> None:
    reg = registry()
    called = False

    def choose(_: object) -> dict[str, object]:
        nonlocal called
        called = True
        return {"selections": [{"option_id": "candidate:0"}]}

    plan = SchemaPlanner(
        reg,
        decision_backend=CallableDecisionBackend(choose),
        decision_policy=DecisionPolicy(
            enabled=True,
            endpoint_selection=True,
        ),
    ).plan("재료의 전자 구조를 알려줘")

    assert plan.calls == []
    assert called is False
    assert plan.warnings == ["no schema candidate matched the request"]


def test_decision_backend_can_expand_empty_lexical_recall_when_opted_in() -> None:
    reg = registry()

    def choose(request):
        assert [option.label for option in request.options] == ["materials.search"]
        assert request.options[0].metadata["schema_score"] == 0.0
        return {"selections": [{"option_id": request.options[0].id, "score": 0.9}]}

    plan = SchemaPlanner(
        reg,
        decision_backend=CallableDecisionBackend(choose),
        decision_policy=DecisionPolicy(
            enabled=True,
            endpoint_selection=True,
            recall_on_empty=True,
        ),
    ).plan("재료의 전자 구조를 알려줘")

    assert plan.calls[0].tool == "materials"
    assert plan.calls[0].endpoint == "search"
    assert any("expanded an empty lexical candidate set" in item for item in plan.warnings)


def test_empty_recall_abstention_fails_closed_without_arbitrary_deterministic_route() -> None:
    reg = registry()
    plan = SchemaPlanner(
        reg,
        decision_backend=CallableDecisionBackend(lambda _: {"abstained": True}),
        decision_policy=DecisionPolicy(
            enabled=True,
            endpoint_selection=True,
            recall_on_empty=True,
        ),
    ).plan("완전히 어휘가 다른 요청")

    assert plan.calls == []
    assert any(
        "abstained after empty lexical recall" in item
        for item in plan.warnings
    )


def test_empty_recall_provider_error_fails_closed_without_arbitrary_route() -> None:
    reg = registry()

    def fail(_: object) -> dict[str, object]:
        raise RuntimeError("offline")

    plan = SchemaPlanner(
        reg,
        decision_backend=CallableDecisionBackend(fail),
        decision_policy=DecisionPolicy(
            enabled=True,
            endpoint_selection=True,
            recall_on_empty=True,
        ),
    ).plan("완전히 어휘가 다른 요청")

    assert plan.calls == []
    assert any(
        "fallback after empty lexical recall: RuntimeError" in item
        for item in plan.warnings
    )


@pytest.mark.asyncio
async def test_async_decision_backend_can_expand_empty_lexical_recall() -> None:
    reg = registry()

    async def choose(request):
        return {"selections": [{"option_id": request.options[0].id}]}

    plan = await SchemaPlanner(
        reg,
        decision_backend=CallableDecisionBackend(choose),
        decision_policy=DecisionPolicy(
            enabled=True,
            endpoint_selection=True,
            recall_on_empty=True,
        ),
    ).aplan("재료의 전자 구조를 알려줘")

    assert plan.calls[0].tool == "materials"
    assert any("expanded an empty lexical candidate set" in item for item in plan.warnings)



def test_candidate_abstention_can_suppress_existing_lexical_route() -> None:
    reg = registry()
    plan = SchemaPlanner(
        reg,
        decision_backend=CallableDecisionBackend(lambda _: {"abstained": True}),
        decision_policy=DecisionPolicy(
            enabled=True,
            endpoint_selection=True,
            candidate_abstention="no_route",
        ),
    ).plan("band gap")

    assert plan.calls == []
    assert any("suppressed candidate route" in item for item in plan.warnings)


def test_candidate_no_route_abstention_does_not_change_provider_error_fallback() -> None:
    reg = registry()

    def fail(_: object) -> dict[str, object]:
        raise RuntimeError("offline")

    plan = SchemaPlanner(
        reg,
        decision_backend=CallableDecisionBackend(fail),
        decision_policy=DecisionPolicy(
            enabled=True,
            endpoint_selection=True,
            candidate_abstention="no_route",
            fallback="deterministic",
        ),
    ).plan("band gap")

    assert plan.calls[0].tool == "materials"
    assert any("decision backend fallback: RuntimeError" in item for item in plan.warnings)


@pytest.mark.asyncio
async def test_async_candidate_abstention_can_suppress_route() -> None:
    reg = registry()

    async def abstain(_: object) -> dict[str, object]:
        return {"abstained": True}

    plan = await SchemaPlanner(
        reg,
        decision_backend=CallableDecisionBackend(abstain),
        decision_policy=DecisionPolicy(
            enabled=True,
            endpoint_selection=True,
            candidate_abstention="no_route",
        ),
    ).aplan("band gap")

    assert plan.calls == []
    assert any("suppressed candidate route" in item for item in plan.warnings)



def test_inherited_candidate_abstention_preserves_fallback_error_behavior() -> None:
    reg = registry()
    planner = SchemaPlanner(
        reg,
        decision_backend=CallableDecisionBackend(lambda _: {"abstained": True}),
        decision_policy=DecisionPolicy(
            enabled=True,
            endpoint_selection=True,
            fallback="error",
        ),
    )

    with pytest.raises(PlanningError, match="decision backend abstained"):
        planner.plan("band gap")


def test_plan_explanation_records_deterministic_score_and_field_reasons() -> None:
    reg = registry()
    plan = SchemaPlanner(reg).plan(
        PlanRequest(
            query="LiFePO4 band gap",
            arguments={"formula": "LiFePO4", "unknown": 1},
        )
    )

    explanation = plan.calls[0].explanation
    assert explanation is not None
    assert explanation.candidate_selection == "deterministic"
    assert explanation.ignored_arguments == ["unknown"]
    assert any(
        component.kind == "field_lexical"
        and component.matched == "band_gap"
        and component.value == 3.0
        for component in explanation.score_components
    )
    reasons = {item.field: item.reason for item in explanation.field_selection}
    assert reasons["material_id"] == "identifier"
    assert reasons["band_gap"] == "field_lexical"


def test_plan_explanation_marks_recall_fallback_projection() -> None:
    reg = registry()
    plan = SchemaPlanner(reg).plan(
        PlanRequest(query="tell me about this material", arguments={"formula": "Si"})
    )

    explanation = plan.calls[0].explanation
    assert explanation is not None
    reasons = {item.field: item.reason for item in explanation.field_selection}
    assert reasons["material_id"] == "identifier"
    assert reasons["band_gap"] == "recall_fallback"
    assert reasons["formation_energy_per_atom"] == "recall_fallback"
    assert reasons["density"] == "recall_fallback"


def test_plan_explanation_marks_decision_backend_candidate_selection() -> None:
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

    def choose_secondary(request):
        option = next(
            option
            for option in request.options
            if option.label == "secondary.lookup"
        )
        return {"selections": [{"option_id": option.id}]}

    plan = SchemaPlanner(
        reg,
        decision_backend=CallableDecisionBackend(choose_secondary),
        decision_policy=DecisionPolicy(enabled=True, endpoint_selection=True),
    ).plan("band gap")

    explanation = plan.calls[0].explanation
    assert explanation is not None
    assert explanation.candidate_selection == "decision_backend"


def test_plan_explanation_marks_decision_backend_field_selection() -> None:
    reg = registry()

    def choose_density(request):
        density = next(option for option in request.options if option.label == "density")
        return {"selections": [{"option_id": density.id}]}

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

    explanation = plan.calls[0].explanation
    assert explanation is not None
    reasons = {item.field: item.reason for item in explanation.field_selection}
    assert reasons["material_id"] == "identifier"
    assert reasons["density"] == "decision_backend"



def _provider_tool(
    name: str,
    *,
    provider: str,
    access_mode: str,
    field_name: str = "band_gap",
    aliases: list[str] | None = None,
    read_only: bool = True,
) -> ToolSpec:
    return ToolSpec(
        name=name,
        provider=provider,
        access_mode=access_mode,
        endpoints=[
            EndpointSpec(
                name="search",
                description="Search materials band gap properties",
                read_only=read_only,
                parameters=[ParameterSpec(name="formula", required=True)],
                output_fields=[
                    FieldSpec(name="material_id", identifier=True),
                    FieldSpec(
                        name=field_name,
                        aliases=list(aliases or []),
                        json_schema={"type": "number"},
                        unit="eV",
                    ),
                ],
            )
        ],
    )


def test_planner_precompiles_same_provider_access_fallbacks() -> None:
    reg = InMemoryRegistry()
    api = _provider_tool(
        "mp_api",
        provider="materials_project",
        access_mode="openapi",
        aliases=["band gap"],
    )
    optimade = _provider_tool(
        "mp_optimade",
        provider="materials_project",
        access_mode="optimade",
        field_name="_mp_band_gap",
        aliases=["band gap", "band_gap"],
    )
    reg.register(api)
    reg.register(optimade)

    plan = SchemaPlanner(reg).plan(
        PlanRequest(
            query="Si band gap",
            preferred_tools=["mp_api"],
            arguments={"formula": "Si"},
            fallback_scope="same_provider",
            max_fallbacks=2,
        )
    )

    assert plan.calls[0].tool == "mp_api"
    route = plan.fallback_route(0)
    assert route is not None
    assert [call.tool for call in route.alternatives] == ["mp_optimade"]
    assert route.alternatives[0].fields == ["material_id", "_mp_band_gap"]
    assert route.alternatives[0].arguments == {"formula": "Si"}


def test_cross_provider_fallback_orders_same_provider_before_other_provider() -> None:
    reg = InMemoryRegistry()
    reg.register(
        _provider_tool(
            "mp_api",
            provider="materials_project",
            access_mode="openapi",
            aliases=["band gap"],
        )
    )
    reg.register(
        _provider_tool(
            "mp_optimade",
            provider="materials_project",
            access_mode="optimade",
            field_name="_mp_band_gap",
            aliases=["band gap", "band_gap"],
        )
    )
    reg.register(
        _provider_tool(
            "oqmd_api",
            provider="oqmd",
            access_mode="openapi",
            aliases=["band gap"],
        )
    )

    plan = SchemaPlanner(reg).plan(
        PlanRequest(
            query="Si band gap",
            preferred_tools=["mp_api"],
            arguments={"formula": "Si"},
            fallback_scope="cross_provider",
            max_fallbacks=2,
        )
    )

    route = plan.fallback_route(0)
    assert route is not None
    assert [call.tool for call in route.alternatives] == [
        "mp_optimade",
        "oqmd_api",
    ]


def test_fallback_does_not_cross_semantically_incompatible_fields() -> None:
    reg = InMemoryRegistry()
    reg.register(
        _provider_tool(
            "mp_api",
            provider="materials_project",
            access_mode="openapi",
            aliases=["band gap"],
        )
    )
    reg.register(
        _provider_tool(
            "mp_wrong_surface",
            provider="materials_project",
            access_mode="legacy",
            field_name="density",
            aliases=["mass density"],
        ).model_copy(
            update={
                "description": "Band gap provider transport with incompatible output field",
            },
            deep=True,
        )
    )

    plan = SchemaPlanner(reg).plan(
        PlanRequest(
            query="Si band gap",
            preferred_tools=["mp_api"],
            arguments={"formula": "Si"},
            fallback_scope="same_provider",
        )
    )

    assert plan.fallback_route(0) is None


def test_planner_never_builds_automatic_mutation_fallbacks() -> None:
    reg = InMemoryRegistry()
    reg.register(
        _provider_tool(
            "primary_write",
            provider="provider_a",
            access_mode="openapi",
            aliases=["band gap"],
            read_only=False,
        )
    )
    reg.register(
        _provider_tool(
            "secondary_write",
            provider="provider_a",
            access_mode="python",
            aliases=["band gap"],
            read_only=False,
        )
    )

    plan = SchemaPlanner(reg).plan(
        PlanRequest(
            query="write band gap",
            preferred_tools=["primary_write"],
            arguments={"formula": "Si"},
            fallback_scope="same_provider",
        )
    )

    assert plan.calls[0].tool == "primary_write"
    assert plan.fallback_routes == []



def test_provider_fallback_requires_explicit_primary_provider_identity() -> None:
    reg = InMemoryRegistry()
    reg.register(
        ToolSpec(
            name="untagged_primary",
            endpoints=[
                EndpointSpec(
                    name="search",
                    read_only=True,
                    output_fields=[FieldSpec(name="band_gap", aliases=["band gap"])],
                )
            ],
        )
    )
    reg.register(
        _provider_tool(
            "tagged_alternative",
            provider="provider_b",
            access_mode="openapi",
            aliases=["band gap"],
        )
    )

    plan = SchemaPlanner(reg).plan(
        PlanRequest(
            query="band gap",
            preferred_tools=["untagged_primary"],
            fallback_scope="cross_provider",
        )
    )

    assert plan.calls[0].tool == "untagged_primary"
    assert plan.fallback_routes == []



def _semantic_provider_tool(
    name: str,
    *,
    provider: str,
    access_mode: str,
    field_name: str,
    semantic_id: str,
    unit: str | None,
) -> ToolSpec:
    return ToolSpec(
        name=name,
        provider=provider,
        access_mode=access_mode,
        endpoints=[
            EndpointSpec(
                name="search",
                read_only=True,
                output_fields=[
                    FieldSpec(name="material_id", identifier=True),
                    FieldSpec(
                        name=field_name,
                        semantic_id=semantic_id,
                        json_schema={"type": "number"} if unit is not None else {},
                        unit=unit,
                    ),
                ],
            )
        ],
    )


def test_semantic_id_bridges_provider_specific_field_names() -> None:
    reg = InMemoryRegistry()
    reg.register(
        _semantic_provider_tool(
            "provider_a",
            provider="a",
            access_mode="openapi",
            field_name="elasticity_value",
            semantic_id="elastic_modulus",
            unit="GPa",
        )
    )
    reg.register(
        _semantic_provider_tool(
            "provider_b",
            provider="b",
            access_mode="optimade",
            field_name="_b_emod",
            semantic_id="elastic_modulus",
            unit="GPa",
        )
    )

    plan = SchemaPlanner(reg).plan(
        PlanRequest(
            query="elastic modulus",
            preferred_tools=["provider_a"],
            fallback_scope="cross_provider",
        )
    )

    assert plan.calls[0].fields == ["material_id", "elasticity_value"]
    route = plan.fallback_route(0)
    assert route is not None
    assert route.alternatives[0].tool == "provider_b"
    assert route.alternatives[0].fields == ["material_id", "_b_emod"]


def test_fallback_rejects_semantically_matching_field_with_incompatible_unit() -> None:
    reg = InMemoryRegistry()
    reg.register(
        _semantic_provider_tool(
            "provider_a",
            provider="a",
            access_mode="openapi",
            field_name="elasticity_value",
            semantic_id="elastic_modulus",
            unit="GPa",
        )
    )
    reg.register(
        _semantic_provider_tool(
            "provider_b",
            provider="b",
            access_mode="optimade",
            field_name="_b_emod",
            semantic_id="elastic_modulus",
            unit="Pa",
        )
    )

    plan = SchemaPlanner(reg).plan(
        PlanRequest(
            query="elastic modulus",
            preferred_tools=["provider_a"],
            fallback_scope="cross_provider",
        )
    )

    assert plan.fallback_routes == []


def test_semantic_id_takes_precedence_over_lexical_alias_overlap() -> None:
    primary = ToolSpec(
        name="primary",
        provider="a",
        access_mode="openapi",
        endpoints=[
            EndpointSpec(
                name="search",
                read_only=True,
                output_fields=[
                    FieldSpec(
                        name="modulus",
                        semantic_id="elastic_modulus",
                        aliases=["modulus"],
                        unit="GPa",
                    )
                ],
            )
        ],
    )
    misleading = ToolSpec(
        name="misleading",
        provider="b",
        access_mode="openapi",
        endpoints=[
            EndpointSpec(
                name="search",
                read_only=True,
                output_fields=[
                    FieldSpec(
                        name="modulus",
                        semantic_id="bulk_modulus",
                        aliases=["modulus", "elastic modulus"],
                        unit="GPa",
                    )
                ],
            )
        ],
    )
    reg = InMemoryRegistry()
    reg.register(primary)
    reg.register(misleading)

    plan = SchemaPlanner(reg).plan(
        PlanRequest(
            query="elastic modulus",
            preferred_tools=["primary"],
            fallback_scope="cross_provider",
        )
    )

    assert plan.fallback_routes == []



def test_fallback_does_not_treat_substring_overlap_as_semantic_equivalence() -> None:
    primary = ToolSpec(
        name="primary",
        provider="a",
        access_mode="openapi",
        endpoints=[
            EndpointSpec(
                name="search",
                description="material modulus lookup",
                read_only=True,
                output_fields=[
                    FieldSpec(
                        name="elastic_modulus",
                        aliases=["elastic modulus"],
                    )
                ],
            )
        ],
    )
    misleading = ToolSpec(
        name="misleading",
        provider="b",
        access_mode="openapi",
        endpoints=[
            EndpointSpec(
                name="search",
                description="material modulus lookup",
                read_only=True,
                output_fields=[
                    FieldSpec(
                        name="bulk_modulus",
                        aliases=["modulus"],
                    )
                ],
            )
        ],
    )
    reg = InMemoryRegistry()
    reg.register(primary)
    reg.register(misleading)

    plan = SchemaPlanner(reg).plan(
        PlanRequest(
            query="elastic modulus",
            preferred_tools=["primary"],
            fallback_scope="cross_provider",
        )
    )

    assert plan.calls[0].tool == "primary"
    assert plan.fallback_routes == []


def test_ambiguous_recall_first_plan_requires_full_fallback_field_coverage() -> None:
    primary = ToolSpec(
        name="primary",
        provider="a",
        access_mode="openapi",
        endpoints=[
            EndpointSpec(
                name="search",
                description="material overview",
                read_only=True,
                output_fields=[
                    FieldSpec(name="elastic_modulus", aliases=["elastic modulus"]),
                    FieldSpec(name="density", aliases=["density"]),
                ],
            )
        ],
    )
    incomplete = ToolSpec(
        name="incomplete",
        provider="b",
        access_mode="openapi",
        endpoints=[
            EndpointSpec(
                name="search",
                description="material overview",
                read_only=True,
                output_fields=[
                    FieldSpec(name="elastic_modulus", aliases=["elastic modulus"]),
                ],
            )
        ],
    )
    reg = InMemoryRegistry()
    reg.register(primary)
    reg.register(incomplete)

    plan = SchemaPlanner(reg).plan(
        PlanRequest(
            query="material overview",
            preferred_tools=["primary"],
            fallback_scope="cross_provider",
        )
    )

    assert plan.calls[0].fields == ["elastic_modulus", "density"]
    assert plan.fallback_routes == []



def test_equal_relevance_prefers_explicit_server_projection() -> None:
    reg = InMemoryRegistry()
    reg.register(
        ToolSpec(
            name="a_plain",
            endpoints=[
                EndpointSpec(
                    name="search",
                    read_only=True,
                    output_fields=[
                        FieldSpec(
                            name="elastic_modulus",
                            aliases=["elastic modulus"],
                        )
                    ],
                )
            ],
        )
    )
    reg.register(
        ToolSpec(
            name="z_projecting",
            endpoints=[
                EndpointSpec(
                    name="search",
                    read_only=True,
                    output_fields=[
                        FieldSpec(
                            name="elastic_modulus",
                            aliases=["elastic modulus"],
                        )
                    ],
                    server_projection=ServerProjectionSpec(parameter="fields"),
                )
            ],
        )
    )

    plan = SchemaPlanner(reg).plan("elastic modulus")

    assert plan.calls[0].tool == "z_projecting"



def test_parameter_alias_maps_same_value_without_semantic_transformation() -> None:
    registry = InMemoryRegistry()
    registry.register(
        ToolSpec(
            name="provider_b",
            endpoints=[
                EndpointSpec(
                    name="search",
                    read_only=True,
                    parameters=[
                        ParameterSpec(
                            name="chemical_formula",
                            aliases=["formula"],
                            required=True,
                        )
                    ],
                    output_fields=[
                        FieldSpec(
                            name="elastic_modulus",
                            semantic_id="elastic_modulus",
                            aliases=["elastic modulus"],
                            json_schema={"type": "number"},
                        )
                    ],
                )
            ],
        )
    )

    marker = {"formula": "Si"}
    plan = SchemaPlanner(registry).plan(
        PlanRequest(
            query="elastic modulus",
            arguments=marker,
        )
    )

    assert plan.executable
    assert plan.calls[0].arguments == {"chemical_formula": "Si"}
    assert marker == {"formula": "Si"}
    assert any(
        component.kind == "argument_alias_match"
        and component.matched == "formula->chemical_formula"
        for component in plan.calls[0].explanation.score_components
    )


def test_exact_parameter_name_wins_over_competing_alias() -> None:
    registry = InMemoryRegistry()
    registry.register(
        ToolSpec(
            name="provider",
            endpoints=[
                EndpointSpec(
                    name="search",
                    read_only=True,
                    parameters=[
                        ParameterSpec(name="formula", required=True),
                        ParameterSpec(
                            name="chemical_formula",
                            aliases=["formula"],
                            required=False,
                        ),
                    ],
                    output_fields=[FieldSpec(name="value")],
                )
            ],
        )
    )

    plan = SchemaPlanner(registry).plan(
        PlanRequest(
            query="value",
            arguments={"formula": "Si"},
        )
    )

    assert plan.calls[0].arguments == {"formula": "Si"}
    assert "chemical_formula" not in plan.calls[0].arguments


def test_ambiguous_parameter_alias_never_guesses_a_target() -> None:
    registry = InMemoryRegistry()
    registry.register(
        ToolSpec(
            name="provider",
            endpoints=[
                EndpointSpec(
                    name="search",
                    read_only=True,
                    parameters=[
                        ParameterSpec(
                            name="formula",
                            aliases=["material"],
                            required=True,
                        ),
                        ParameterSpec(
                            name="material_id",
                            aliases=["material"],
                            required=True,
                        ),
                    ],
                    output_fields=[FieldSpec(name="value")],
                )
            ],
        )
    )

    plan = SchemaPlanner(registry).plan(
        PlanRequest(
            query="value",
            arguments={"material": "Si"},
        )
    )

    assert plan.calls[0].arguments == {}
    assert sorted(plan.calls[0].missing_required_arguments) == [
        "formula",
        "material_id",
    ]
    assert plan.executable is False
    assert any(
        "ambiguous parameter aliases: material" in warning
        for warning in plan.warnings
    )


def test_multiple_supplied_aliases_for_one_parameter_are_not_guessed() -> None:
    registry = InMemoryRegistry()
    registry.register(
        ToolSpec(
            name="provider",
            endpoints=[
                EndpointSpec(
                    name="search",
                    read_only=True,
                    parameters=[
                        ParameterSpec(
                            name="chemical_formula",
                            aliases=["formula", "composition"],
                            required=True,
                        )
                    ],
                    output_fields=[FieldSpec(name="value")],
                )
            ],
        )
    )

    plan = SchemaPlanner(registry).plan(
        PlanRequest(
            query="value",
            arguments={
                "formula": "Si",
                "composition": "Ge",
            },
        )
    )

    assert plan.calls[0].arguments == {}
    assert plan.calls[0].missing_required_arguments == ["chemical_formula"]
    assert any(
        "ambiguous parameter aliases: composition, formula" in warning
        for warning in plan.warnings
    )


def test_fallback_compiles_provider_specific_parameter_aliases_independently() -> None:
    registry = InMemoryRegistry()
    registry.register(
        ToolSpec(
            name="provider_a",
            provider="a",
            access_mode="openapi",
            endpoints=[
                EndpointSpec(
                    name="search",
                    read_only=True,
                    parameters=[
                        ParameterSpec(name="formula", required=True)
                    ],
                    output_fields=[
                        FieldSpec(
                            name="elastic_modulus",
                            semantic_id="elastic_modulus",
                            json_schema={"type": "number"},
                        )
                    ],
                )
            ],
        )
    )
    registry.register(
        ToolSpec(
            name="provider_b",
            provider="b",
            access_mode="optimade",
            endpoints=[
                EndpointSpec(
                    name="search",
                    read_only=True,
                    parameters=[
                        ParameterSpec(
                            name="chemical_formula",
                            aliases=["formula"],
                            required=True,
                        )
                    ],
                    output_fields=[
                        FieldSpec(
                            name="elasticity",
                            semantic_id="elastic_modulus",
                            json_schema={"type": "number"},
                        )
                    ],
                )
            ],
        )
    )

    plan = SchemaPlanner(registry).plan(
        PlanRequest(
            query="elastic modulus",
            preferred_tools=["provider_a"],
            arguments={"formula": "Si"},
            fallback_scope="cross_provider",
        )
    )

    assert plan.calls[0].arguments == {"formula": "Si"}
    route = plan.fallback_route(0)
    assert route is not None
    assert route.alternatives[0].tool == "provider_b"
    assert route.alternatives[0].arguments == {"chemical_formula": "Si"}


def test_candidate_index_discovers_endpoint_from_parameter_alias() -> None:
    registry = InMemoryRegistry()
    registry.register(
        ToolSpec(
            name="provider",
            endpoints=[
                EndpointSpec(
                    name="lookup",
                    read_only=True,
                    parameters=[
                        ParameterSpec(
                            name="chemical_formula",
                            aliases=["formula"],
                            required=True,
                        )
                    ],
                    output_fields=[FieldSpec(name="value")],
                )
            ],
        )
    )

    plan = SchemaPlanner(registry).plan(
        PlanRequest(
            query="unrelated words",
            arguments={"formula": "Si"},
        )
    )

    assert plan.calls
    assert plan.calls[0].tool == "provider"
    assert plan.calls[0].arguments == {"chemical_formula": "Si"}
