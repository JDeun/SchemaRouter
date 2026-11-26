"""Source-bound query conditions, not model accuracy or provider-task evidence."""
from __future__ import annotations

from copy import deepcopy

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
    PaperNativeRankPolicy,
    ParameterSpec,
    PrincipalContext,
    ToolSpec,
)
from scripts.research_legacy_router import legacy_router

ACTOR = PrincipalContext(subject="query-condition", roles=("reader",))
CATALOG = NativeConceptCatalog(concepts=(NativeDeclaredConcept(
    concept_id="weather.temperature", aliases=("air temperature",),
    source_type="weather", license="reviewed",
    required_fields=(CapabilityFieldContract(semantic_id="weather.temperature",
        json_schema={"type": "number"}),),
),))
INTENTS = PaperIntentRegistry(intents=(PaperIntentDeclaration(
    intent_id="information.lookup", required_concept_ids=(),
),))


def source(*, parameters=(), restricted=False, identifier=False):
    router = legacy_router(
        authorization_policy=AuthorizationPolicy(default_effect="allow",
        data_rules=(DataScopeRule(operation="weather.read", roles_any=("reader",),
            hidden_fields=("private",)),) if restricted else ()))
    fields = [FieldSpec(name="temperature", semantic_id="weather.temperature",
        json_schema={"type": "number"})]
    if identifier:
        fields.append(FieldSpec(name="city", semantic_id="weather.city", identifier=True,
            json_schema={"type": "string"}))
    if restricted:
        fields.append(FieldSpec(name="private", json_schema={"type": "string"}))
    router.add_tool(ToolSpec(name="weather", source_type="weather", license="reviewed",
        endpoints=[EndpointSpec(name="read", read_only=True, output_fields=fields,
            parameters=list(parameters), input_schema={
                "type": "object",
                "properties": {p.name: deepcopy(p.json_schema) for p in parameters},
                "required": [p.name for p in parameters if p.required],
            } if parameters else {},
        )]))
    session = router.prepare_field_routing(catalog=CATALOG,
        approved_host_roots=frozenset({"weather.read"}) if parameters else frozenset())
    return router, session


async def query(session, hints, *, host=None, model=None):
    raw = {"intent_id": "information.lookup", "needs": [{"concept": "air temperature"}],
           "parameter_hints": hints}
    return await session.acompile_query("Get air temperature in Seoul", principal=ACTOR,
        model=model or (lambda _: raw), intent_registry=INTENTS,
        model_visible_intent_ids=("information.lookup",),
        host_source_arguments={"weather.read": host} if host is not None else None)


def city(*, aliases=(), semantic_id=None, name="city", kind="string"):
    return ParameterSpec(name=name, aliases=list(aliases), semantic_id=semantic_id,
        required=True, json_schema={"type": kind})


@pytest.mark.asyncio
async def test_scalar_hint_without_declared_source_input_or_filter_is_unproven():
    _, session = source()
    plan = await query(session, {"city": "Seoul"})
    assert plan.status == "no_proven_hit" and not plan.coverage.complete
    assert plan.calls[0].call.arguments == {}
    condition, = [item for item in plan.coverage.uncovered
                  if "query_input_condition=true" in item.qualifiers]
    assert condition.semantic_id == "city"
    assert "proof=unproven_source_relation" in condition.qualifiers


@pytest.mark.parametrize("key,param", [
    ("city", city()),
    ("place", city(aliases=("place",))),
    ("weather.city", city(semantic_id="weather.city")),
    ("city", city(name="filter__city", aliases=("city",))),
])
@pytest.mark.asyncio
async def test_only_matching_host_source_input_proves_condition(key, param):
    _, session = source(parameters=(param,))
    plan = await query(session, {key: "Seoul"}, host={param.name: "Seoul"})
    assert plan.status == "ready" and plan.coverage.complete
    assert plan.calls[0].call.arguments == {param.name: "Seoul"}
    assert any("proof=matching_host_input" in item.qualifiers for item in plan.coverage.covered)


@pytest.mark.asyncio
async def test_hint_does_not_fill_missing_source_input_and_missing_diagnosis_survives():
    _, session = source(parameters=(city(),))
    plan = await query(session, {"city": "Seoul"})
    assert plan.status == "requires_arguments" and plan.coverage.complete
    assert plan.calls[0].call.arguments == {}
    assert plan.calls[0].call.missing_required_arguments == ["city"]
    assert any("proof=pending_host_input" in item.qualifiers for item in plan.coverage.covered)


@pytest.mark.asyncio
async def test_conflicting_host_input_is_not_query_complete_or_exposed_in_coverage():
    _, session = source(parameters=(city(),))
    plan = await query(session, {"city": "Seoul"}, host={"city": "PRIVATE_HOST_BERLIN"})
    assert plan.status == "no_proven_hit" and not plan.coverage.complete
    assert plan.calls[0].call.arguments == {"city": "PRIVATE_HOST_BERLIN"}
    assert "PRIVATE_HOST_BERLIN" not in plan.coverage.model_dump_json()
    assert any("proof=conflicting_host_input" in item.qualifiers
               for item in plan.coverage.uncovered)


@pytest.mark.parametrize("hint,actual,kind,complete", [
    (True, 1, "integer", False), (1, True, "boolean", False),
    (1, 1.0, "number", True), (1, 1, "integer", True),
    (9007199254740993, 9007199254740992.0, "number", False),
])
@pytest.mark.asyncio
async def test_exact_json_scalar_equality_never_coerces_bool_or_large_integer(hint, actual, kind,
                                                                           complete):
    _, session = source(parameters=(city(kind=kind),))
    plan = await query(session, {"city": hint}, host={"city": actual})
    assert plan.coverage.complete is complete
    assert plan.status == ("ready" if complete else "no_proven_hit")


@pytest.mark.asyncio
async def test_two_declared_alias_targets_are_ambiguous_even_with_matching_host_values():
    _, session = source(parameters=(city(aliases=("place",)),
                                   city(name="region", aliases=("place",))))
    plan = await query(session, {"place": "Seoul"}, host={"city": "Seoul", "region": "Seoul"})
    assert plan.status == "no_proven_hit" and not plan.coverage.complete
    assert any("proof=ambiguous_source_input" in item.qualifiers
               for item in plan.coverage.uncovered)


@pytest.mark.parametrize("key", ("place", "weather.city"))
@pytest.mark.asyncio
async def test_scoped_redacted_alias_and_semantic_id_never_recovered_from_raw_source(key):
    _, session = source(parameters=(city(aliases=("place",), semantic_id="weather.city"),),
                        restricted=True)
    plan = await query(session, {key: "Seoul"}, host={"city": "Seoul"})
    assert plan.status == "no_proven_hit" and not plan.coverage.complete
    assert any("proof=unproven_source_relation" in item.qualifiers
               for item in plan.coverage.uncovered)


@pytest.mark.asyncio
async def test_selected_identifier_alone_does_not_invent_output_filter_relation():
    _, session = source(identifier=True)
    plan = await query(session, {"city": "Seoul"})
    assert plan.status == "no_proven_hit" and not plan.coverage.complete
    assert plan.calls[0].call.fields == ["temperature", "city"]


@pytest.mark.parametrize("mutation", ("actor", "policy", "source"))
@pytest.mark.asyncio
async def test_condition_source_revalidation_refuses_callback_mutation(mutation):
    from schemarouter.errors import PolicyViolationError
    from schemarouter.paper_query_conditions import _apply_query_input_conditions

    router, session = source(parameters=(city(),))
    plan = await query(session, {}, host={"city": "PRIVATE_HOST_VALUE"})
    actor = ACTOR.model_copy(deep=True)
    mutated = False

    def available(tool, endpoint):
        nonlocal mutated
        if not mutated:
            mutated = True
            if mutation == "actor":
                actor.roles = ("changed",)
            elif mutation == "policy":
                router.authorization_policy = AuthorizationPolicy(default_effect="deny")
            else:
                revised = router.registry.get("weather")
                revised.description = "changed"
                router.registry.register(revised, replace=True)
        return True

    router.planner.availability_predicate = available
    with pytest.raises(PolicyViolationError) as caught:
        _apply_query_input_conditions(router, plan, principal=actor,
            parameter_hints={"city": "Seoul"})
    assert "PRIVATE_HOST_VALUE" not in str(caught.value)
    assert "PRIVATE_HOST_VALUE" not in repr(caught.value)


@pytest.mark.asyncio
async def test_callback_disposable_schema_mutation_cannot_create_a_source_alias():
    from schemarouter.paper_query_conditions import _apply_query_input_conditions

    router, session = source(parameters=(city(),))
    plan = await query(session, {}, host={"city": "Seoul"})

    def available(tool, endpoint):
        endpoint.parameters[0].aliases.append("place")
        tool.endpoint("read").parameters[0].aliases.append("place")
        return True

    router.planner.availability_predicate = available
    checked = _apply_query_input_conditions(router, plan, principal=ACTOR,
        parameter_hints={"place": "Seoul"})
    assert checked.status == "no_proven_hit" and not checked.coverage.complete
    assert router.registry.get("weather").endpoint("read").parameters[0].aliases == []


@pytest.mark.asyncio
async def test_scope_cannot_rewrite_its_retained_input_to_hide_alias_withdrawal(monkeypatch):
    from schemarouter.errors import PolicyViolationError
    from schemarouter.paper_query_conditions import _apply_query_input_conditions

    router, session = source(parameters=(city(aliases=("place",)),))
    plan = await query(session, {}, host={"city": "Seoul"})
    original = router._data_scope_endpoint_view
    observations = 0
    retained = []

    def changing_scope(principal, tool, endpoint):
        nonlocal observations
        observations += 1
        view = original(principal, tool, endpoint).model_copy(deep=True)
        if observations >= 3:
            for previous in retained:
                previous.parameters[0].aliases.clear()
            view.parameters[0].aliases.clear()
        retained.append(view)
        return view

    monkeypatch.setattr(router, "_data_scope_endpoint_view", changing_scope)
    with pytest.raises(PolicyViolationError, match="source eligibility changed"):
        _apply_query_input_conditions(router, plan, principal=ACTOR,
            parameter_hints={"place": "Seoul"})


@pytest.mark.asyncio
async def test_global_hint_cannot_broadcast_to_two_same_semantic_source_inputs():
    router, _ = source(parameters=(city(semantic_id="weather.city"),))
    router.add_tool(ToolSpec(name="humidity", source_type="weather", license="reviewed",
        endpoints=[EndpointSpec(name="read", read_only=True,
            parameters=[city(semantic_id="weather.city")], input_schema={
                "type": "object", "properties": {"city": {"type": "string"}}, "required": ["city"],
            }, output_fields=[FieldSpec(name="humidity", semantic_id="weather.humidity",
                json_schema={"type": "number"})],
        )]))
    catalog = NativeConceptCatalog(concepts=(*CATALOG.concepts, NativeDeclaredConcept(
        concept_id="weather.humidity", aliases=("air humidity",), source_type="weather",
        license="reviewed", required_fields=(CapabilityFieldContract(
            semantic_id="weather.humidity", json_schema={"type": "number"},
        ),),
    )))
    session = router.prepare_field_routing(catalog=catalog,
        approved_host_roots=frozenset({"weather.read", "humidity.read"}))
    plan = await session.acompile_query("Get air temperature and air humidity in Seoul",
        principal=ACTOR, model=lambda _: {"intent_id": "information.lookup", "needs": [
            {"concept": "air temperature"}, {"concept": "air humidity"},
        ], "parameter_hints": {"weather.city": "Seoul"}}, intent_registry=INTENTS,
        model_visible_intent_ids=("information.lookup",), host_source_arguments={
            "weather.read": {"city": "Seoul"}, "humidity.read": {"city": "Seoul"},
        })
    assert len(plan.calls) == 2 and plan.status == "no_proven_hit" and not plan.coverage.complete
    assert any("proof=ambiguous_source_input" in item.qualifiers
               for item in plan.coverage.uncovered)


@pytest.mark.asyncio
async def test_unproven_condition_preserves_g5_requires_observation_diagnosis():
    from test_native_concept_graph_vertical_slice import _catalog, _joined_router

    router = _joined_router()
    session = router.prepare_field_routing(catalog=_catalog())
    plan = await session.acompile_query("Get case status from cases in Seoul", principal=ACTOR,
        model=lambda _: {"intent_id": "information.lookup", "needs": [{"concept": "case status"}],
            "named_tools": ["cases"], "parameter_hints": {"city": "Seoul"}},
        intent_registry=INTENTS, model_visible_intent_ids=("information.lookup",))
    assert plan.status == "requires_observation" and plan.bindings
    assert not plan.coverage.complete
    assert plan.calls[-1].call.missing_required_arguments == ["contact_id", "region_id"]


@pytest.mark.parametrize("name,aliases,hint_key", [
    ("city", (), "city"), ("filter__city", ("city",), "city"),
])
@pytest.mark.asyncio
async def test_optional_query_input_mapping_waits_without_forging_source_required_metadata(
    name, aliases, hint_key,
):
    router, _ = source()
    tool = router.registry.get("weather")
    parameter = city(name=name, aliases=aliases)
    parameter.required = False
    endpoint = tool.endpoint("read")
    endpoint.parameters = [parameter]
    endpoint.input_schema = {"type": "object", "properties": {name: {"type": "string"}}}
    router.registry.register(tool, replace=True)
    session = router.prepare_field_routing(catalog=CATALOG)
    plan = await session.acompile_query("Get air temperature from weather in Seoul",
        principal=ACTOR, model=lambda _: {"intent_id": "information.lookup", "needs": [
            {"concept": "air temperature"},
        ], "named_tools": ["weather"], "parameter_hints": {hint_key: "Seoul"}},
        intent_registry=INTENTS, model_visible_intent_ids=("information.lookup",))
    assert plan.status == "requires_arguments" and plan.coverage.complete
    assert plan.calls[0].call.arguments == {}
    assert plan.calls[0].call.missing_required_arguments == []
    assert plan.calls[0].parameters_meta[0].required is False
    condition, = [item for item in plan.coverage.covered
                  if "proof=pending_host_input" in item.qualifiers]
    assert {"route=weather.read", f"parameter={name}"} <= set(condition.qualifiers)
    assert router.registry.get("weather").endpoint("read").parameters[0].required is False


@pytest.mark.parametrize("proposed,valid", [("Seoul", True), ("other", False)])
@pytest.mark.asyncio
async def test_unbound_hint_fit_uses_current_public_scalar_contract(proposed, valid):
    parameter = city()
    parameter.json_schema["enum"] = ["Seoul"]
    _, session = source(parameters=(parameter,))
    plan = await query(session, {"city": proposed})
    assert plan.status == "requires_arguments"
    assert plan.coverage.complete is valid
    assert plan.calls[0].call.arguments == {}
    assert plan.calls[0].call.missing_required_arguments == ["city"]


@pytest.mark.asyncio
async def test_scoped_private_enum_hints_have_uniform_unproven_disposition():
    parameter = city()
    parameter.json_schema["enum"] = ["PRIVATE_ALLOWED_CITY"]
    _, session = source(parameters=(parameter,), restricted=True)
    dispositions = []
    for proposed in ("PRIVATE_ALLOWED_CITY", "PRIVATE_OTHER_CITY", "arbitrary"):
        plan = await query(session, {"city": proposed})
        conditions = [item for item in plan.coverage.uncovered
                      if "query_input_condition=true" in item.qualifiers]
        dispositions.append((plan.status, plan.coverage.complete,
                             [item.model_dump() for item in conditions]))
        assert plan.calls[0].call.arguments == {}
        assert "PRIVATE_ALLOWED_CITY" not in plan.coverage.model_dump_json()
        assert "PRIVATE_OTHER_CITY" not in plan.coverage.model_dump_json()
    assert dispositions[0] == dispositions[1] == dispositions[2]
    assert "proof=unproven_scoped_input_fit" in dispositions[0][2][0]["qualifiers"]


@pytest.mark.asyncio
async def test_matching_bound_host_call_reuses_existing_proof_without_raw_schema_disclosure():
    parameter = city()
    parameter.json_schema["enum"] = ["PRIVATE_ALLOWED_CITY"]
    _, session = source(parameters=(parameter,), restricted=True)
    plan = await query(session, {"city": "PRIVATE_ALLOWED_CITY"},
        host={"city": "PRIVATE_ALLOWED_CITY"})
    assert plan.status == "ready" and plan.coverage.complete
    assert "PRIVATE_ALLOWED_CITY" not in plan.coverage.model_dump_json()
    assert any("proof=matching_host_input" in item.qualifiers for item in plan.coverage.covered)


@pytest.mark.asyncio
async def test_hidden_required_parameter_fails_closed_before_condition_inference():
    from schemarouter.errors import PolicyViolationError

    _, session = source(parameters=(city(name="private", semantic_id="weather.city"),),
                        restricted=True)
    with pytest.raises(PolicyViolationError, match="source eligibility changed") as caught:
        await query(session, {"weather.city": "Seoul"})
    assert "private" not in str(caught.value)


@pytest.mark.asyncio
async def test_unsupported_hint_preserves_another_required_input_diagnosis():
    _, session = source(parameters=(city(),))
    plan = await query(session, {"entity": "Alice"})
    assert plan.status == "requires_arguments" and not plan.coverage.complete
    assert plan.calls[0].call.missing_required_arguments == ["city"]
    assert plan.calls[0].call.arguments == {}



# Direct comparison input semantics are separately host-approved, not a
# relaxation of the legacy unique-target/G5 contract tested above.
SHARED_SID = "weather.city"
SHARED_INTENT = "weather.compare"
SHARED_ROUTES = ("north.read", "south.read")


def _shared_fixture(*, approved=True, wrong_semantic=False, missing=False,
                    ambiguous=False, hidden=False, invalid_value=False,
                    owner_targets=False, header=False, alias_collision=False):
    router = legacy_router(authorization_policy=AuthorizationPolicy(
        default_effect="allow",
        data_rules=(DataScopeRule(operation="south.read", hidden_fields=("private",)),)
        if hidden else (),
    ))
    for tool, parameter in (("north", "city"), ("south", "location")):
        params = [ParameterSpec(
            name=parameter,
            semantic_id=("weather.other" if tool == "south" and wrong_semantic else SHARED_SID),
            aliases=["place"],
            json_schema=(
                {"type": "string", "enum": ["Busan"]}
                if tool == "south" and invalid_value else
                {"anyOf": [{"type": "string"}, {"type": "array", "items": {"type": "string"}}]}
            ),
            location="header" if tool == "south" and header else "query",
        )]
        if tool == "south" and missing:
            params = []
        if tool == "south" and ambiguous:
            params.append(ParameterSpec(
                name="region", semantic_id=SHARED_SID, json_schema={"type": "string"},
            ))
        if tool == "south" and alias_collision:
            params.append(ParameterSpec(
                name="place", semantic_id="weather.other", json_schema={"type": "string"},
            ))
        router.add_tool(ToolSpec(
            name=tool, source_type="weather", license="reviewed",
            endpoints=[EndpointSpec(
                name="read", read_only=True, parameters=params,
                output_fields=[
                    FieldSpec(name="temperature", semantic_id="weather.temperature",
                              json_schema={"type": "number"}),
                    FieldSpec(name="private", json_schema={"type": "string"}),
                ],
                input_schema={
                    "type": "object", "properties": {p.name: p.json_schema for p in params},
                    "required": [], "additionalProperties": False,
                },
            )],
        ))
    session = router.prepare_field_routing(catalog=CATALOG)
    intents = PaperIntentRegistry(
        intents=(PaperIntentDeclaration(
            intent_id=SHARED_INTENT, required_concept_ids=("weather.temperature",),
            shared_parameter_semantics={"place": SHARED_SID} if approved else {},
            target_tool_keys=("north", "south") if owner_targets else (),
        ),),
        projection_snapshot_id=session.snapshot_id,
        approved_direct_parameter_routes=SHARED_ROUTES,
    )
    rank = PaperNativeRankPolicy(
        snapshot_id=session.snapshot_id, direct_score_mode="paper_v1", focus_direct=True,
    )
    return session, intents, rank


async def _shared_query(*, named=("north", "south"), hints=None, host=None,
                        original=True, text=None, **fixture):
    session, intents, rank = _shared_fixture(**fixture)
    raw = {
        "intent_id": SHARED_INTENT, "needs": [{"concept": "air temperature"}],
        "named_tools": list(named), "parameter_hints": hints if hints is not None else {
            "place": "Seoul",
        },
    }
    plan = await session.acompile_query(
        text or "Compare the air temperature in Seoul from north and south.",
        principal=ACTOR, model=lambda _: raw, intent_registry=intents,
        model_visible_intent_ids=(SHARED_INTENT,), rank_policy=rank if original else None,
        host_source_arguments=host,
    )
    assert not plan.executable_authority and not plan.bindings
    return plan


@pytest.mark.asyncio
async def test_owner_shared_input_is_a_per_source_proposal_not_an_argument():
    plan = await _shared_query()
    assert plan.status == "requires_arguments" and plan.coverage.complete
    assert {c.route_id: dict(c.parameter_proposals) for c in plan.calls} == {
        "north.read": {"city": "Seoul"}, "south.read": {"location": "Seoul"},
    }
    assert all(c.call.arguments == {} for c in plan.calls)
    evidence = [item for item in plan.coverage.covered
                if "shared_input=true" in item.qualifiers]
    assert len(evidence) == 2
    assert all("proof=pending_host_input" in item.qualifiers for item in evidence)


@pytest.mark.parametrize("options", [
    {"approved": False},
    {"wrong_semantic": True},
    {"missing": True},
    {"ambiguous": True},
    {"hidden": True},
    {"invalid_value": True},
    {"header": True},
    {"alias_collision": True},
    {"original": False},
    {"owner_targets": True, "named": ()},
])
@pytest.mark.asyncio
async def test_shared_input_never_silently_broadcasts_or_partially_certifies(options):
    plan = await _shared_query(**options)
    assert not plan.coverage.complete
    assert all(not c.parameter_proposals and c.call.arguments == {} for c in plan.calls)
    assert any(item.semantic_id == "place" for item in plan.coverage.uncovered)


@pytest.mark.asyncio
async def test_fabricated_named_provider_cannot_activate_shared_semantics():
    plan = await _shared_query(text="Get the air temperature from north in Seoul.")
    assert not plan.coverage.complete and not plan.calls


@pytest.mark.asyncio
async def test_conflict_with_another_hint_blocks_the_entire_shared_group():
    plan = await _shared_query(hints={"place": "Seoul", "city": "Busan"})
    assert not plan.coverage.complete
    assert all(not c.parameter_proposals for c in plan.calls)
    assert {"place", "city"} <= {item.semantic_id for item in plan.coverage.uncovered}


@pytest.mark.asyncio
async def test_failed_shared_group_cannot_propose_through_a_matching_native_alias():
    plan = await _shared_query(
        invalid_value=True, hints={"place": "Seoul", "city": "Seoul"},
    )
    assert not plan.coverage.complete
    assert all(not c.parameter_proposals for c in plan.calls)


@pytest.mark.asyncio
async def test_shared_value_requires_matching_explicit_host_arguments_on_each_source():
    host = {"north.read": {"city": "Seoul"}, "south.read": {"location": "Seoul"}}
    plan = await _shared_query(host=host)
    assert plan.status == "ready" and plan.coverage.complete
    assert {call.route_id: call.call.arguments for call in plan.calls} == host
    assert all(not call.parameter_proposals for call in plan.calls)
    host["south.read"]["location"] = "Busan"
    conflict = await _shared_query(host=host)
    assert not conflict.coverage.complete
    assert all(not call.parameter_proposals for call in conflict.calls)


@pytest.mark.asyncio
async def test_partial_host_approval_keeps_remaining_shared_input_pending():
    plan = await _shared_query(host={"north.read": {"city": "Seoul"}})
    assert plan.status == "requires_arguments" and plan.coverage.complete
    assert {c.route_id: dict(c.parameter_proposals) for c in plan.calls} == {
        "north.read": {}, "south.read": {"location": "Seoul"},
    }
    assert {c.route_id: c.call.arguments for c in plan.calls} == {
        "north.read": {"city": "Seoul"}, "south.read": {},
    }


def test_shared_input_semantics_require_a_snapshot_even_without_route_annotations():
    intent = PaperIntentDeclaration(
        intent_id=SHARED_INTENT, required_concept_ids=("weather.temperature",),
        shared_parameter_semantics={"place": SHARED_SID},
    )
    with pytest.raises(ValueError):
        PaperIntentRegistry(intents=(intent,))
