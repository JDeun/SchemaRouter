"""Query-only Understand contracts, not natural-language model accuracy evidence."""
from __future__ import annotations

import json

import pytest
from test_understood_multi_concept import ACTOR, CATALOG, INTENTS, _router

from schemarouter import (
    AuthorizationPolicy,
    CapabilityFieldContract,
    EndpointSpec,
    FieldSpec,
    NativeConceptCatalog,
    NativeDeclaredConcept,
    PaperIntentDeclaration,
    PaperIntentRegistry,
    ToolSpec,
)
from schemarouter.errors import ModelAnalysisError, PolicyViolationError


async def _query(router, response, *, query="band gap and paper abstract", intents=INTENTS,
                 observe=None):
    session = router.prepare_field_routing(catalog=CATALOG)

    def model(payload):
        if observe is not None:
            observe.append(payload)
        return response(payload) if callable(response) else response

    return await session.acompile_query(
        query, principal=ACTOR, model=model, intent_registry=intents,
        model_visible_intent_ids=tuple(i.intent_id for i in intents.intents),
    )


@pytest.mark.asyncio
async def test_understand_receives_fixed_vocabulary_without_catalog_or_source_aliases():
    seen = []
    for denied in (False, True):
        router = _router()
        for index in range(30 if denied else 1):
            router.add_tool(ToolSpec(name=f"HIDDEN_CATALOG_{index}", endpoints=[
                EndpointSpec(name="SOURCE_ENDPOINT_MARKER", read_only=True),
            ]))
        if denied:
            router.authorization_policy = AuthorizationPolicy(default_effect="deny")
        plan = await _query(router, {"intent_id": None, "needs": [
            {"concept": "unsupported spin"},
        ]}, observe=seen)
        assert plan.status == "no_proven_hit" and plan.calls == ()
    assert len(seen) == 2 and seen[0] == seen[1]
    encoded = json.dumps(seen[0])
    assert "offered_concepts" not in encoded and "required_concept_ids" not in encoded
    assert "HIDDEN_CATALOG" not in encoded and "SOURCE_ENDPOINT_MARKER" not in encoded
    assert "material.band_gap" not in encoded and "materials-fixture-license" not in encoded


@pytest.mark.asyncio
async def test_schema_independent_needs_reuse_complete_mixed_source_field_plans():
    plan = await _query(_router(), {"intent_id": "research.summary", "needs": [
        {"concept": "band gap"}, {"concept": "paper abstract"},
    ]})
    assert plan.status == "ready" and plan.coverage.complete
    assert {item.semantic_id for item in plan.coverage.covered} == {"band gap", "paper abstract"}
    assert {c.route_id: c.call.fields for c in plan.calls} == {
        "materials.read": ["materials_id", "gap"],
        "papers.read": ["papers_id", "abstract"],
    }
    assert plan.understanding_hints["needs"] == [
        {"concept": "band gap", "unit": None, "source_type": None, "qualifiers": {}},
        {"concept": "paper abstract", "unit": None, "source_type": None, "qualifiers": {}},
    ]
    assert plan.executable_authority is False


@pytest.mark.asyncio
async def test_missing_need_identity_and_all_conditions_survive_partial_plan():
    plan = await _query(_router(), {"intent_id": "research.summary", "needs": [
        {"concept": "band gap"}, {"concept": "paper abstract"},
        {"concept": "material density", "unit": "g/cm3", "qualifiers": {"phase": "solid"}},
    ]})
    assert plan.status == "no_proven_hit" and not plan.coverage.complete
    assert {c.route_id for c in plan.calls} == {"materials.read", "papers.read"}
    missing = plan.coverage.uncovered
    assert len(missing) == 1 and missing[0].semantic_id == "material density"
    assert {"unit=g/cm3", "phase=solid"} <= set(missing[0].qualifiers)


@pytest.mark.asyncio
async def test_generic_intent_has_no_arbitrary_required_fields():
    intents = PaperIntentRegistry(intents=(PaperIntentDeclaration(
        intent_id="information.lookup", required_concept_ids=(),
    ),))
    plan = await _query(_router(), {"intent_id": "information.lookup", "needs": [
        {"concept": "paper abstract"},
    ]}, intents=intents)
    assert plan.status == "ready" and plan.coverage.complete
    assert [c.route_id for c in plan.calls] == ["papers.read"]


@pytest.mark.asyncio
@pytest.mark.parametrize("need", [
    {"concept": "band gap", "unit": "K"},
    {"concept": "band gap", "qualifiers": {"time": "tomorrow"}},
    {"concept": "band gap", "source_type": "experimental"},
    {"concept": "band gap and unsupported spin"},
])
async def test_unproved_condition_never_uses_intent_group_as_an_answer(need):
    plan = await _query(_router(), {"intent_id": "material.lookup", "needs": [need]})
    assert plan.status == "no_proven_hit" and plan.calls == ()
    assert not plan.coverage.complete and len(plan.coverage.uncovered) == 1
    assert plan.coverage.uncovered[0].semantic_id == need["concept"]


@pytest.mark.asyncio
async def test_negated_concept_is_not_restored_by_intent_required_group():
    plan = await _query(_router(), {"intent_id": "research.summary", "needs": [
        {"concept": "band gap"},
    ], "excluded_concepts": ["paper abstract"]})
    assert plan.status == "ambiguous_paths" and plan.calls == ()
    assert not plan.coverage.complete
    assert any("excluded=true" in item.qualifiers for item in plan.coverage.uncovered)


@pytest.mark.asyncio
async def test_null_intent_retains_actual_unsupported_need_and_parameters():
    plan = await _query(_router(), {"intent_id": None, "needs": [
        {"concept": "send a payment"},
    ], "parameter_hints": {"amount": 37}}, query="send a payment of 37")
    assert plan.calls == () and not plan.coverage.complete
    assert [r.semantic_id for r in plan.coverage.uncovered] == ["send a payment"]
    assert plan.understanding_hints["parameter_hints"] == {"amount": 37}


@pytest.mark.asyncio
async def test_raw_response_cannot_select_source_ids_or_hide_unmet_needs():
    with pytest.raises(ModelAnalysisError):
        await _query(_router(), {"intent_id": "material.lookup", "concept_ids": [
            "material.band_gap",
        ]})
    plan = await _query(_router(), {"intent_id": "material.lookup", "needs": []})
    assert plan.calls == () and not plan.coverage.complete


@pytest.mark.asyncio
async def test_source_revocation_during_understand_prevents_every_receipt():
    router = _router()

    def revoke(_payload):
        router.authorization_policy = AuthorizationPolicy(default_effect="deny")
        return {"intent_id": "material.lookup", "needs": [{"concept": "band gap"}]}

    with pytest.raises(PolicyViolationError):
        await _query(router, revoke)


@pytest.mark.asyncio
async def test_inaccessible_known_need_reveals_only_the_requested_meaning():
    router = _router()
    router.authorization_policy = AuthorizationPolicy(default_effect="deny")
    plan = await _query(router, {"intent_id": "material.lookup", "needs": [
        {"concept": "band gap"},
    ]})
    assert plan.calls == () and not plan.coverage.complete
    assert [r.semantic_id for r in plan.coverage.uncovered] == ["band gap"]
    from pydantic import TypeAdapter

    from schemarouter import PaperTypedToolPlan

    serialized = TypeAdapter(PaperTypedToolPlan).dump_json(plan).decode()
    assert "materials-fixture-license" not in serialized
    assert "material.band_gap" not in serialized and "materials.read" not in serialized


@pytest.mark.asyncio
async def test_explicit_parameters_remain_advisory_until_the_host_supplies_them():
    from test_public_p2_source_field_mapping import ACTOR as WEATHER_ACTOR
    from test_public_p2_source_field_mapping import source

    _, session, intents = source(units=True)
    for host in (None, {"weather.read": {"city": "HOST"}}):
        plan = await session.acompile_query(
            "Get temperature in Celsius for city QUERY", principal=WEATHER_ACTOR,
            model=lambda _: {"intent_id": "weather.lookup", "needs": [
                {"concept": "temperature", "unit": "Cel"},
            ], "parameter_hints": {"city": "QUERY"}},
            intent_registry=intents, model_visible_intent_ids=("weather.lookup",),
            host_source_arguments=host,
        )
        assert plan.status == ("ready" if host else "requires_arguments")
        assert plan.coverage.complete
        assert plan.calls[0].call.arguments == ({"city": "HOST"} if host else {})
        assert plan.calls[0].fields_meta[0].source_path == ("payload", "temperature")
        assert plan.calls[0].fields_meta[0].unit == "Cel"
        assert plan.understanding_hints["parameter_hints"] == {"city": "QUERY"}


@pytest.mark.asyncio
@pytest.mark.parametrize("query,tool,ready", [
    ("band gap from materials", "materials", True),
    ("band gap", "materials", False),
    ("band gap from absent_source", "absent_source", False),
])
async def test_model_can_only_copy_an_explicit_current_source_name(query, tool, ready):
    plan = await _query(_router(), {"intent_id": "material.lookup", "needs": [
        {"concept": "band gap"},
    ], "named_tools": [tool]}, query=query)
    assert plan.status == ("ready" if ready else "no_proven_hit")
    assert bool(plan.calls) is ready
    assert plan.coverage.complete is ready


@pytest.mark.asyncio
async def test_every_explicit_source_must_supply_requested_data():
    plan = await _query(_router(), {"intent_id": "material.lookup", "needs": [
        {"concept": "band gap"},
    ], "named_tools": ["materials", "papers"]},
        query="Get band gap from materials and papers")
    assert plan.status == "no_proven_hit" and not plan.coverage.complete
    assert [call.route_id for call in plan.calls] == ["materials.read"]
    assert any(item.semantic_id == "papers" and "named_tool=true" in item.qualifiers
               for item in plan.coverage.uncovered)


@pytest.mark.asyncio
async def test_unserializable_owner_mutation_is_rejected_without_private_details():
    session = _router().prepare_field_routing(catalog=CATALOG)

    def model(_payload):
        object.__setattr__(session._catalog.concepts[0], "aliases", (object(),))
        return {"intent_id": "material.lookup", "needs": [{"concept": "band gap"}]}

    with pytest.raises(PolicyViolationError, match="owner authority changed"):
        await session.acompile_query(
            "band gap", principal=ACTOR, model=model, intent_registry=INTENTS,
            model_visible_intent_ids=("material.lookup",),
        )


@pytest.mark.asyncio
async def test_named_source_availability_errors_are_opaque():
    router = _router()

    def unavailable(_tool, _endpoint):
        raise RuntimeError("PRIVATE_AVAILABILITY_CANARY")

    router.planner.availability_predicate = unavailable
    with pytest.raises(PolicyViolationError) as failure:
        await _query(router, {"intent_id": "material.lookup", "needs": [
            {"concept": "band gap"},
        ], "named_tools": ["materials"]}, query="band gap from materials")
    assert "PRIVATE_AVAILABILITY_CANARY" not in str(failure.value)


@pytest.mark.asyncio
@pytest.mark.parametrize("role,expected", [
    ("author", "ready"), (None, "ambiguous_paths"), ("reviewer", "ambiguous_paths"),
])
async def test_exclusion_uses_declared_role_and_never_assumes_a_missing_one(role, expected):
    router = _router()
    qualifiers = {"role": role} if role else {}
    router.add_tool(ToolSpec(name="selected", source_type="crm", license="reviewed",
        endpoints=[EndpointSpec(name="read", read_only=True, output_fields=[FieldSpec(
            name="login", semantic_id="crm.login", json_schema={"type": "string"},
            qualifiers=qualifiers,
        )])]))
    catalog = NativeConceptCatalog(concepts=tuple(NativeDeclaredConcept(
        concept_id=cid, aliases=(alias,), source_type="crm", license="reviewed",
        required_fields=(CapabilityFieldContract(
            semantic_id="crm.login", json_schema={"type": "string"}, qualifiers=condition,
        ),),
    ) for cid, alias, condition in (
        ("crm.selected", "selected login", qualifiers),
        ("crm.reviewer", "reviewer login", {"role": "reviewer"}),
    )))
    session = router.prepare_field_routing(catalog=catalog)
    intents = PaperIntentRegistry(intents=(PaperIntentDeclaration(
        intent_id="information.lookup", required_concept_ids=(),
    ),))
    plan = await session.acompile_query(
        "selected login excluding reviewer login", principal=ACTOR,
        model=lambda _: {"intent_id": "information.lookup", "needs": [
            {"concept": "selected login"},
        ], "excluded_concepts": ["reviewer login"]},
        intent_registry=intents, model_visible_intent_ids=("information.lookup",),
    )
    assert plan.status == expected
    assert plan.coverage.complete is (expected == "ready")
    assert bool(plan.calls) is (expected == "ready")


@pytest.mark.asyncio
async def test_unrepresented_query_needs_cannot_become_a_complete_partial_answer():
    plan = await _query(_router(), {"intent_id": "material.lookup", "needs": [
        {"concept": "band gap"},
    ], "needs_truncated": True})
    assert plan.status == "budget_unsatisfied" and plan.calls == ()
    assert not plan.coverage.complete
    assert any(r.semantic_id == "unrepresented query needs" for r in plan.coverage.uncovered)


@pytest.mark.asyncio
async def test_independent_query_budget_accepts_multiline_multilingual_questions():
    seen = []
    query = ("추가 맥락을 포함한 자연어 질문입니다. " * 20) + "\n밴드갭을 알려줘."
    plan = await _query(_router(), {"intent_id": "material.lookup", "needs": [
        {"concept": "band gap"},
    ]}, query=query, observe=seen)
    assert plan.status == "ready" and seen[0]["query"] == query
