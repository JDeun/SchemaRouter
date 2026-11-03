"""Public per-need conditions are proved on one current scoped field and route."""

from __future__ import annotations

from dataclasses import replace

import pytest

from schemarouter import (
    AuthorizationPolicy,
    CapabilityFieldContract,
    DataScopeRule,
    EndpointSpec,
    FieldSpec,
    NativeConceptCatalog,
    NativeDeclaredConcept,
    PaperIntentDeclaration,
    PaperIntentRegistry,
    ParameterSpec,
    PrincipalContext,
    SchemaRouter,
    ToolSpec,
)

ACTOR = PrincipalContext(subject="scoped-needs", roles=("reader",))
INTENTS = PaperIntentRegistry(
    intents=(
        PaperIntentDeclaration(
            intent_id="information.lookup",
            required_concept_ids=(),
        ),
    )
)


def source(*, required=True, parameters=None, qualifiers=None, collision=False, second=False):
    router = SchemaRouter(authorization_policy=AuthorizationPolicy(default_effect="allow"))
    owners = []
    roots = set()
    for name in ("facility", "remote") if second else ("facility",):
        field = FieldSpec(
            name="reading",
            semantic_id=f"{name}.reading",
            json_schema={"type": "number"},
            unit="Cel",
            qualifiers=qualifiers or {},
            path=("packet", "reading"),
            result_path=("answer", "reading"),
        )
        fields = [field]
        if collision:
            fields.append(
                FieldSpec(
                    name="literal",
                    semantic_id="other.value",
                    json_schema={"type": "number"},
                    path=("packet.reading",),
                    result_path=("other",),
                )
            )
        params = (
            parameters
            if parameters is not None
            else [
                ParameterSpec(
                    name="facility_code",
                    aliases=["site_tag"],
                    semantic_id="facility.code",
                    required=required,
                    json_schema={"type": "string"},
                )
            ]
        )
        if any(parameter.required for parameter in params):
            roots.add(f"{name}.read")
        router.add_tool(
            ToolSpec(
                name=name,
                source_type="measurement",
                license="reviewed",
                endpoints=[
                    EndpointSpec(
                        name="read",
                        read_only=True,
                        output_fields=fields,
                        parameters=params,
                        input_schema={
                            "type": "object",
                            "properties": {p.name: p.json_schema for p in params},
                            "required": [p.name for p in params if p.required],
                        },
                    )
                ],
            )
        )
        owners.append(
            NativeDeclaredConcept(
                concept_id=f"{name}.reading",
                aliases=(f"{name} reading",),
                source_type="measurement",
                license="reviewed",
                required_fields=(CapabilityFieldContract.from_field(field),),
            )
        )
    session = router.prepare_field_routing(
        catalog=NativeConceptCatalog(concepts=tuple(owners)), approved_host_roots=frozenset(roots)
    )
    return router, session


async def query(session, conditions, *, host=None, hints=None, needs=None, actor=ACTOR):
    raw = {
        "intent_id": "information.lookup",
        "needs": needs
        or [
            {"concept": "facility reading", "qualifiers": conditions},
        ],
        "parameter_hints": hints or {},
    }
    return await session.acompile_query(
        "Map the explicitly supplied measurement requirements",
        principal=actor,
        model=lambda _: raw,
        intent_registry=INTENTS,
        model_visible_intent_ids=("information.lookup",),
        host_source_arguments=host,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("required", (True, False))
@pytest.mark.parametrize("key", ("facility_code", "site_tag", "facility.code"))
async def test_declared_per_need_input_is_pending_without_binding_or_changing_required(
    key, required
):
    router, session = source(required=required)
    plan = await query(session, {key: "PLANT-X"})
    assert plan.status == "requires_arguments" and plan.coverage.complete
    assert plan.calls[0].call.arguments == {}
    assert plan.calls[0].call.missing_required_arguments == (["facility_code"] if required else [])
    assert plan.calls[0].parameters_meta[0].required is required
    assert plan.understanding_hints["needs"][0]["qualifiers"] == {key: "PLANT-X"}
    assert router.registry.get("facility").endpoint("read").parameters[0].required is required


@pytest.mark.asyncio
@pytest.mark.parametrize("actual,complete", (("PLANT-X", True), ("OTHER", False)))
async def test_per_need_input_checks_the_host_value_on_the_same_route(actual, complete):
    _, session = source()
    plan = await query(
        session, {"site_tag": "PLANT-X"}, host={"facility.read": {"facility_code": actual}}
    )
    assert plan.coverage.complete is complete
    assert plan.status == ("ready" if complete else "no_proven_hit")
    assert all(call.call.arguments == {"facility_code": actual} for call in plan.calls)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "conditions",
    (
        {"source_path": "packet.reading", "result_path": "answer.reading"},
        {"source_path": "/packet/reading", "result_path": "/answer/reading"},
    ),
)
async def test_canonical_structural_conditions_use_current_source_and_result_paths(conditions):
    _, session = source(parameters=[])
    plan = await query(session, conditions)
    assert plan.status == "ready" and plan.coverage.complete
    assert plan.calls[0].fields_meta[0].source_path == ("packet", "reading")
    assert plan.calls[0].fields_meta[0].result_path == ("answer", "reading")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "conditions",
    (
        {"unknown": "PLANT-X"},
        {"source_field": "packet.reading"},
        {"source_path": "/wrong/reading"},
        {"result_path": "packet.reading"},
        {"role": "forecast"},
    ),
)
async def test_unknown_or_wrong_conditions_are_preserved_and_never_covered(conditions):
    _, session = source(parameters=[])
    plan = await query(session, conditions)
    assert not plan.coverage.complete
    assert plan.coverage.uncovered[0].qualifiers == [
        f"{k}={v}" for k, v in sorted(conditions.items())
    ]


@pytest.mark.asyncio
async def test_dotted_path_collision_requires_an_exact_pointer():
    _, session = source(parameters=[], collision=True)
    dotted = await query(session, {"source_path": "packet.reading"})
    pointed = await query(session, {"source_path": "/packet/reading"})
    assert not dotted.coverage.complete
    assert pointed.coverage.complete and pointed.status == "ready"


@pytest.mark.asyncio
async def test_one_condition_cannot_be_both_output_metadata_and_an_input_proposal():
    _, session = source(required=False, qualifiers={"site_tag": "PLANT-X"})
    plan = await query(session, {"site_tag": "PLANT-X"})
    assert not plan.coverage.complete and plan.status == "no_proven_hit"


@pytest.mark.asyncio
async def test_duplicate_input_aliases_are_ambiguous_and_numeric_input_is_not_coerced():
    for params in (
        [
            ParameterSpec(name=name, aliases=["site_tag"], json_schema={"type": "string"})
            for name in ("first", "second")
        ],
        [
            ParameterSpec(
                name="facility_code", aliases=["site_tag"], json_schema={"type": "integer"}
            )
        ],
    ):
        _, session = source(parameters=params)
        plan = await query(session, {"site_tag": "12"})
        assert not plan.coverage.complete


@pytest.mark.asyncio
async def test_per_need_inputs_do_not_broadcast_between_routes_or_replace_global_hints():
    _, session = source(second=True)
    needs = [
        {"concept": f"{name} reading", "qualifiers": {"site_tag": value}}
        for name, value in (("facility", "A"), ("remote", "B"))
    ]
    plan = await query(session, {}, needs=needs)
    assert plan.coverage.complete and plan.status == "requires_arguments"
    assert len(plan.calls) == 2 and all(call.call.arguments == {} for call in plan.calls)
    global_hint = await query(session, {}, needs=needs, hints={"site_tag": "A"})
    assert not global_hint.coverage.complete
    assert any(
        "proof=ambiguous_source_input" in item.qualifiers for item in global_hint.coverage.uncovered
    )


@pytest.mark.asyncio
async def test_conflicting_conditions_cannot_share_one_unbound_source_input():
    _, session = source(required=False)
    plan = await query(
        session,
        {},
        needs=[
            {"concept": "facility reading", "qualifiers": {"site_tag": "A"}},
            {"concept": "facility reading", "qualifiers": {"site_tag": "B"}},
        ],
    )
    assert not plan.coverage.complete
    assert len(plan.coverage.uncovered) >= 2


@pytest.mark.asyncio
async def test_redacted_input_schema_is_not_a_private_membership_oracle():
    from pydantic import TypeAdapter

    param = ParameterSpec(
        name="facility_code",
        required=False,
        json_schema={"type": "string", "enum": ["PRIVATE_ALLOWED"]},
    )
    router, session = source(parameters=[param])
    tool = router.registry.get("facility")
    tool.endpoints[0].output_fields.append(FieldSpec(name="hidden", json_schema={"type": "string"}))
    router.add_tool(tool, replace=True)
    router.authorization_policy = replace(
        router.authorization_policy,
        data_rules=(
            DataScopeRule(
                operation="facility.read", roles_any=("reader",), hidden_fields=("hidden",)
            ),
        ),
    )
    session = router.prepare_field_routing(catalog=session._require_catalog())
    plans = [
        await query(session, {"facility_code": value}) for value in ("PRIVATE_ALLOWED", "OTHER")
    ]
    assert all(not plan.coverage.complete for plan in plans)
    evidence = [
        [
            item.qualifiers
            for item in plan.coverage.uncovered
            if "query_input_condition=true" in item.qualifiers
        ]
        for plan in plans
    ]
    assert evidence[0] == evidence[1]
    assert "PRIVATE_ALLOWED" not in TypeAdapter(type(plans[1])).dump_json(plans[1]).decode()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path,pointer",
    [
        (("packet.reading",), "/packet.reading"),
        (("packet/reading", "~literal"), "/packet~1reading/~0literal"),
    ],
)
async def test_literal_native_segments_and_pointer_escapes_preserve_path_identity(path, pointer):
    router, session = source(parameters=[])
    tool = router.registry.get("facility")
    tool.endpoints[0].output_fields[0].path = path
    router.add_tool(tool, replace=True)
    session = router.prepare_field_routing(catalog=session._require_catalog())
    exact = await query(session, {"source_path": pointer})
    assert exact.coverage.complete
    guessed = await query(session, {"source_path": ".".join(path)})
    assert guessed.coverage.complete is not any("." in segment for segment in path)
    malformed = await query(session, {"source_path": "/packet~2reading"})
    assert not malformed.coverage.complete


@pytest.mark.asyncio
async def test_input_output_role_unit_and_source_all_hold_on_the_same_selected_field():
    from schemarouter import UnitNormalizationSpec

    router, session = source(qualifiers={"role": "measured"})
    tool = router.registry.get("facility")
    field = tool.endpoints[0].output_fields[0]
    field.unit = "K"
    field.unit_normalization = UnitNormalizationSpec(
        dimension="temperature",
        canonical_unit="Cel",
        scale=1,
        offset=-273.15,
    )
    router.add_tool(tool, replace=True)
    session = router.prepare_field_routing(
        catalog=session._require_catalog(), approved_host_roots=frozenset({"facility.read"})
    )
    need = {
        "concept": "facility reading",
        "unit": "Cel",
        "source_type": "measurement",
        "qualifiers": {"site_tag": "A", "role": "measured", "source_path": "/packet/reading"},
    }
    good = await query(session, {}, needs=[need])
    assert good.coverage.complete and good.status == "requires_arguments"
    assert good.calls[0].fields_meta[0].source_unit == "K"
    for changed in (
        {**need, "unit": "K"},
        {**need, "source_type": "other"},
        {**need, "qualifiers": {**need["qualifiers"], "role": "predicted"}},
        {**need, "qualifiers": {**need["qualifiers"], "result_path": "/not/answer"}},
    ):
        denied = await query(session, {}, needs=[changed])
        assert not denied.coverage.complete


@pytest.mark.asyncio
async def test_per_need_and_global_proposals_cannot_conflict_on_one_optional_parameter():
    _, session = source(required=False)
    plan = await query(session, {"site_tag": "A"}, hints={"facility_code": "B"})
    assert not plan.coverage.complete and plan.status == "no_proven_hit"
    assert any(
        "proof=conflicting_query_input" in item.qualifiers and "need_index=0" in item.qualifiers
        for item in plan.coverage.uncovered
    )
    assert plan.calls[0].call.arguments == {}


@pytest.mark.asyncio
async def test_per_need_input_evidence_is_explicit_and_keeps_original_requirement():
    _, session = source(required=False)
    plan = await query(session, {"site_tag": "A"})
    positive, evidence = plan.coverage.covered
    assert positive.semantic_id == "facility reading" and positive.qualifiers == ["site_tag=A"]
    assert evidence.semantic_id == "site_tag"
    assert set(evidence.qualifiers) == {
        "query_input_condition=true",
        "need_index=0",
        "proof=pending_host_input",
        "route=facility.read",
        "parameter=facility_code",
    }


@pytest.mark.asyncio
async def test_hidden_parameter_and_redacted_alias_or_path_are_not_restored():
    for conditions in ({"site_tag": "A"}, {"source_path": "/packet/reading"}, {"hidden": "A"}):
        router, session = source(required=False)
        tool = router.registry.get("facility")
        endpoint = tool.endpoints[0]
        endpoint.parameters.append(ParameterSpec(name="hidden", json_schema={"type": "string"}))
        endpoint.input_schema["properties"]["hidden"] = {"type": "string"}
        endpoint.output_fields.append(FieldSpec(name="hidden", json_schema={"type": "string"}))
        router.add_tool(tool, replace=True)
        router.authorization_policy = replace(
            router.authorization_policy,
            data_rules=(
                DataScopeRule(
                    operation="facility.read", roles_any=("reader",), hidden_fields=("hidden",)
                ),
            ),
        )
        session = router.prepare_field_routing(catalog=session._require_catalog())
        plan = await query(session, conditions)
        assert not plan.coverage.complete
        assert not any(
            "proof=pending_host_input" in item.qualifiers for item in plan.coverage.covered
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("mutation", ("actor", "policy", "registry", "availability"))
async def test_need_proof_rechecks_actor_policy_registry_and_health_after_compile(
    monkeypatch, mutation
):
    from schemarouter.errors import PolicyViolationError

    router, session = source()
    actor = ACTOR.model_copy(deep=True)
    compiled = False
    original = type(session).compile_understood

    def mark_compiled(self, *args, **kwargs):
        nonlocal compiled
        result = original(self, *args, **kwargs)
        compiled = True
        return result

    def available(tool, endpoint):
        if compiled:
            if mutation == "actor":
                actor.roles = ("PRIVATE_CHANGED",)
            elif mutation == "policy":
                router.authorization_policy = AuthorizationPolicy(default_effect="deny")
            elif mutation == "registry":
                changed = router.registry.get("facility")
                changed.description = "PRIVATE_CHANGED"
                router.add_tool(changed, replace=True)
            else:
                return False
        return True

    monkeypatch.setattr(type(session), "compile_understood", mark_compiled)
    router.planner.availability_predicate = available
    with pytest.raises(PolicyViolationError) as caught:
        await query(session, {"site_tag": "A"}, actor=actor)
    assert "PRIVATE_CHANGED" not in str(caught.value)


@pytest.mark.asyncio
async def test_callback_copy_mutation_cannot_create_a_declared_input_alias():
    from schemarouter.errors import PolicyViolationError

    router, session = source(required=False)

    def available(tool, endpoint):
        endpoint.parameters[0].aliases.append("invented_alias")
        return True

    router.planner.availability_predicate = available
    with pytest.raises(PolicyViolationError):
        await query(session, {"invented_alias": "A"})
    assert router.registry.get("facility").endpoint("read").parameters[0].aliases == ["site_tag"]


@pytest.mark.asyncio
async def test_shared_alias_role_remains_a_meaning_discriminator_with_an_input_condition():
    router, session = source(second=True, required=False)
    owners = []
    for name, role in (("facility", "author"), ("remote", "reviewer")):
        tool = router.registry.get(name)
        field = tool.endpoints[0].output_fields[0]
        field.qualifiers = {"role": role}
        router.add_tool(tool, replace=True)
        owners.append(
            NativeDeclaredConcept(
                concept_id=f"{name}.reading",
                aliases=("reading",),
                required_fields=(CapabilityFieldContract.from_field(field),),
                source_type="measurement",
                license="reviewed",
            )
        )
    session = router.prepare_field_routing(catalog=NativeConceptCatalog(concepts=tuple(owners)))
    plan = await query(
        session,
        {},
        needs=[
            {
                "concept": "reading",
                "qualifiers": {"role": "author", "site_tag": "A"},
            }
        ],
    )
    assert plan.coverage.complete and plan.status == "requires_arguments"
    assert [call.route_id for call in plan.calls] == ["facility.read"]


@pytest.mark.asyncio
async def test_conditions_from_two_output_fields_cannot_be_combined_into_one_need():
    router, session = source(required=False)
    tool = router.registry.get("facility")
    first = tool.endpoints[0].output_fields[0]
    first.qualifiers = {"role": "measured", "phase": "liquid"}
    second = FieldSpec(
        name="other",
        semantic_id="facility.other",
        json_schema={"type": "number"},
        unit="Cel",
        qualifiers={"role": "predicted", "phase": "gas"},
    )
    tool.endpoints[0].output_fields.append(second)
    router.add_tool(tool, replace=True)
    owner = NativeDeclaredConcept(
        concept_id="facility.reading",
        aliases=("facility reading",),
        required_fields=tuple(
            CapabilityFieldContract(
                semantic_id=field.semantic_id, json_schema={"type": "number"}, unit="Cel"
            )
            for field in (first, second)
        ),
        source_type="measurement",
        license="reviewed",
    )
    session = router.prepare_field_routing(catalog=NativeConceptCatalog(concepts=(owner,)))
    plan = await query(session, {"role": "measured", "phase": "gas", "site_tag": "A"})
    assert not plan.coverage.complete
    assert plan.coverage.uncovered[0].qualifiers == ["phase=gas", "role=measured", "site_tag=A"]


@pytest.mark.asyncio
async def test_named_source_contributes_a_proved_need_with_pending_input_conditions():
    _, session = source(required=False)
    plan = await session.acompile_query(
        "Get facility reading from facility for site_tag A",
        principal=ACTOR,
        model=lambda _: {
            "intent_id": "information.lookup",
            "needs": [
                {
                    "concept": "facility reading",
                    "qualifiers": {"site_tag": "A"},
                }
            ],
            "named_tools": ["facility"],
        },
        intent_registry=INTENTS,
        model_visible_intent_ids=("information.lookup",),
    )
    assert plan.coverage.complete and plan.status == "requires_arguments"
    assert any(
        item.semantic_id == "facility" and item.qualifiers == ["named_tool=true"]
        for item in plan.coverage.covered
    )


@pytest.mark.asyncio
async def test_rejected_alternative_input_does_not_invalidate_one_complete_field_witness():
    router, session = source(required=False, second=True)
    other = router.registry.get("remote")
    other.endpoints[0].output_fields[0].semantic_id = "facility.reading"
    other.endpoints[0].parameters[0].json_schema = {"type": "integer"}
    other.endpoints[0].input_schema["properties"]["facility_code"] = {"type": "integer"}
    router.add_tool(other, replace=True)
    owner = session._require_catalog().concepts[0]
    session = router.prepare_field_routing(catalog=NativeConceptCatalog(concepts=(owner,)))
    plan = await query(session, {"site_tag": "A"})
    assert plan.coverage.complete and plan.status == "requires_arguments"
    assert len(plan.calls) == 2
    evidence = [
        item for item in plan.coverage.covered if "query_input_condition=true" in item.qualifiers
    ]
    assert len(evidence) == 1 and "route=facility.read" in evidence[0].qualifiers


@pytest.mark.asyncio
async def test_public_path_proof_rejects_scope_change_between_observations(monkeypatch):
    from schemarouter.errors import PolicyViolationError

    router, session = source(parameters=[])
    compiled = False
    observations = 0
    compile_original = type(session).compile_understood
    scope_original = router._data_scope_endpoint_view

    def compiled_plan(self, *args, **kwargs):
        nonlocal compiled
        plan = compile_original(self, *args, **kwargs)
        compiled = True
        return plan

    def scoped(principal, tool, endpoint):
        nonlocal observations
        view = scope_original(principal, tool, endpoint).model_copy(deep=True)
        if compiled:
            observations += 1
            if observations >= 3:
                view.output_fields[0].path = ("PRIVATE_CHANGED_PATH",)
        return view

    monkeypatch.setattr(type(session), "compile_understood", compiled_plan)
    monkeypatch.setattr(router, "_data_scope_endpoint_view", scoped)
    with pytest.raises(PolicyViolationError) as caught:
        await query(session, {"source_path": "/packet/reading"})
    assert "PRIVATE_CHANGED_PATH" not in str(caught.value)
