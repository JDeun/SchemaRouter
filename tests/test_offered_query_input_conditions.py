"""Offered-ID query finalization; static DTOs, not natural-language accuracy evidence."""
from __future__ import annotations

import pytest
from test_query_input_conditions import ACTOR, INTENTS, city, source

from schemarouter import (
    CapabilityFieldContract,
    FieldSpec,
    NativeConceptCatalog,
    NativeDeclaredConcept,
    PaperIntentDeclaration,
    PaperIntentRegistry,
    PaperNativeRankPolicy,
    PaperUnderstanding,
)
from schemarouter.errors import PolicyViolationError


async def offered(session, hints, *, host=None, intent_id="information.lookup",
                  concepts=("weather.temperature",), unresolved=(), intents=INTENTS, observe=None,
                  rank_policy=None):
    response = {"intent_id": intent_id, "concept_ids": list(concepts),
                "unresolved_concepts": list(unresolved), "parameter_hints": hints}

    def model(payload):
        if observe is not None:
            observe.append(payload)
        return response

    return await session.acompile_query("Get air temperature in Seoul",
        principal=ACTOR, model=model,
        intent_registry=intents,
        model_visible_intent_ids=tuple(i.intent_id for i in intents.intents),
        model_visible_concept_ids=tuple(c.concept_id for c in session._catalog.concepts),
        host_source_arguments={"weather.read": host} if host is not None else None,
        rank_policy=rank_policy)


@pytest.mark.parametrize("host,status,complete", [
    ({"city": "Berlin"}, "no_proven_hit", False),
    ({"city": "Seoul"}, "ready", True),
    (None, "requires_arguments", True),
])
@pytest.mark.asyncio
async def test_offered_ids_require_field_proof_and_input_mapping(host, status, complete):
    _, session = source(parameters=(city(),))
    plan = await offered(session, {"city": "Seoul"}, host=host)
    assert plan.status == status and plan.coverage is not None
    assert plan.coverage.complete is complete
    assert "weather.temperature" in {item.semantic_id for item in plan.coverage.required}
    assert any("query_input_condition=true" in item.qualifiers for item in plan.coverage.required)
    assert plan.calls[0].call.arguments == (host or {})
    assert plan.calls[0].call.missing_required_arguments == ([] if host else ["city"])
    assert "Berlin" not in plan.coverage.model_dump_json()


@pytest.mark.asyncio
async def test_offered_ids_without_source_input_relation_are_not_complete():
    _, session = source()
    plan = await offered(session, {"city": "Seoul"})
    assert plan.status == "no_proven_hit" and not plan.coverage.complete
    assert {r.semantic_id for r in plan.coverage.required} == {"weather.temperature", "city"}
    assert [r.semantic_id for r in plan.coverage.covered] == ["weather.temperature"]


@pytest.mark.asyncio
async def test_owner_intent_fields_supply_ledger_when_model_selects_no_concept_id():
    router, _ = source()
    tool = router.registry.get("weather")
    tool.endpoint("read").output_fields.append(FieldSpec(name="humidity",
        semantic_id="weather.humidity", json_schema={"type": "number"}))
    router.registry.register(tool, replace=True)
    catalog = NativeConceptCatalog(concepts=(NativeDeclaredConcept(
        concept_id="weather.bundle", aliases=("weather bundle",), source_type="weather",
        license="reviewed", required_fields=(
            CapabilityFieldContract(semantic_id="weather.temperature",
                json_schema={"type": "number"}),
            CapabilityFieldContract(semantic_id="weather.humidity", json_schema={"type": "number"}),
        ),
    ),))
    intents = PaperIntentRegistry(intents=(PaperIntentDeclaration(intent_id="weather.lookup",
        required_concept_ids=("weather.bundle",)),))
    session = router.prepare_field_routing(catalog=catalog)
    plan = await offered(session, {}, intent_id="weather.lookup", concepts=(), intents=intents)
    assert plan.status == "ready" and plan.coverage.complete
    assert {r.semantic_id for r in plan.coverage.required} == {
        "weather.temperature", "weather.humidity",
    }
    assert plan.coverage.required == plan.coverage.covered
    # The question-free core receipt contract is unchanged by query finalization.
    structured = session.compile_understood(PaperUnderstanding(intent_id="weather.lookup"),
        principal=ACTOR, intent_registry=intents)
    assert structured.coverage is None


@pytest.mark.asyncio
async def test_null_intent_preserves_fields_and_unresolved_need_without_input_only_completion():
    _, session = source()
    plan = await offered(session, {"city": "Seoul"}, intent_id=None,
                         unresolved=("unsupported need",))
    assert plan.status == "no_proven_hit" and plan.calls == () and not plan.coverage.complete
    assert [r.semantic_id for r in plan.coverage.uncovered] == [
        "weather.temperature", "unresolved", "city",
    ]
    assert "query_concept=unsupported need" in plan.coverage.uncovered[1].qualifiers
    assert plan.understanding_hints["intent_id"] is None
    assert plan.understanding_hints["parameter_hints"] == {"city": "Seoul"}
    empty = await offered(session, {"city": "Seoul"}, intent_id=None, concepts=())
    assert not empty.coverage.complete and empty.coverage.covered == []


@pytest.mark.asyncio
async def test_existing_partial_coverage_survives_matching_source_input():
    _, session = source(parameters=(city(),))
    plan = await offered(session, {"city": "Seoul"}, host={"city": "Seoul"},
                         unresolved=("unsupported need",))
    assert plan.status == "no_proven_hit" and not plan.coverage.complete
    assert any("query_concept=unsupported need" in r.qualifiers for r in plan.coverage.uncovered)
    assert any("proof=matching_host_input" in r.qualifiers for r in plan.coverage.covered)


@pytest.mark.asyncio
async def test_offered_wire_payload_decoder_and_ids_are_unchanged():
    _, session = source()
    seen = []
    await offered(session, {}, observe=seen)
    payload, = seen
    assert payload["response_schema"] == PaperUnderstanding.model_json_schema()
    assert payload["offered_concepts"] == [{"concept_id": "weather.temperature",
        "aliases": ["air temperature"]}]
    assert payload["response_fields"] == ["intent_id", "concept_ids", "unresolved_concepts",
        "source_type", "named_tools", "parameter_hints"]
    assert "host_source_arguments" not in payload and "needs" not in payload


@pytest.mark.parametrize("mode", ("independent", "offered"))
@pytest.mark.parametrize("owner", ("catalog", "intents", "rank", "host_arguments"))
@pytest.mark.asyncio
async def test_common_final_verify_refuses_owner_mutation_during_condition_callback(
    monkeypatch, mode, owner,
):
    import schemarouter.paper_query_understanding as query_module

    router, session = source(parameters=(city(),))
    intents = INTENTS.model_copy(deep=True)
    host = {"weather.read": {"city": "Seoul"}}
    rank = PaperNativeRankPolicy(snapshot_id=session.snapshot_id)
    applying = False
    changed = False
    original = query_module._apply_query_input_conditions

    def apply(*args, **kwargs):
        nonlocal applying
        applying = True
        return original(*args, **kwargs)

    def available(tool, endpoint):
        nonlocal changed
        if applying and not changed:
            changed = True
            if owner == "catalog":
                session._catalog.concepts[0].aliases = ("changed",)
            elif owner == "intents":
                intents.intents[0].domains = ("changed",)
            elif owner == "rank":
                rank.route_priorities["weather.read"] = 1
            else:
                host["weather.read"]["city"] = "PRIVATE_CHANGED_HOST"
        return True

    monkeypatch.setattr(query_module, "_apply_query_input_conditions", apply)
    router.planner.availability_predicate = available
    raw = ({"needs": [{"concept": "air temperature"}]} if mode == "independent"
           else {"concept_ids": ["weather.temperature"]})
    with pytest.raises(PolicyViolationError, match="owner authority changed") as caught:
        await session.acompile_query("Get air temperature in Seoul", principal=ACTOR,
            model=lambda _: {"intent_id": "information.lookup", **raw,
                "parameter_hints": {"city": "Seoul"}}, intent_registry=intents,
            model_visible_intent_ids=("information.lookup",),
            model_visible_concept_ids=None if mode == "independent" else ("weather.temperature",),
            host_source_arguments=host, rank_policy=rank)
    assert changed and "PRIVATE_CHANGED_HOST" not in str(caught.value)


@pytest.mark.asyncio
async def test_failed_current_proof_does_not_restore_owner_field_metadata():
    from pydantic import TypeAdapter

    from schemarouter import PaperTypedToolPlan

    router, _ = source()
    tool = router.registry.get("weather")
    tool.source_type = "PRIVATE_OWNER_SOURCE"
    tool.license = "PRIVATE_OWNER_LICENSE"
    tool.endpoint("read").output_fields[0].semantic_id = "PRIVATE_OWNER_FIELD"
    router.registry.register(tool, replace=True)
    catalog = NativeConceptCatalog(concepts=(NativeDeclaredConcept(
        concept_id="weather.public_meaning", aliases=("air temperature",),
        source_type=tool.source_type, license=tool.license,
        required_fields=(CapabilityFieldContract(semantic_id="PRIVATE_OWNER_FIELD",
            json_schema={"type": "number"}),),
    ),))
    session = router.prepare_field_routing(catalog=catalog)
    available = {"current": True}
    router.planner.availability_predicate = lambda *_: available["current"]

    def model(payload):
        assert payload["offered_concepts"][0]["concept_id"] == "weather.public_meaning"
        available["current"] = False
        return {"intent_id": "information.lookup", "concept_ids": ["weather.public_meaning"]}

    plan = await session.acompile_query("Get air temperature", principal=ACTOR, model=model,
        intent_registry=INTENTS, model_visible_intent_ids=("information.lookup",),
        model_visible_concept_ids=("weather.public_meaning",))
    assert plan.status == "no_proven_hit" and plan.calls == () and not plan.coverage.complete
    assert [r.semantic_id for r in plan.coverage.uncovered] == ["weather.public_meaning"]
    assert "PRIVATE_OWNER" not in TypeAdapter(PaperTypedToolPlan).dump_json(plan).decode()
