"""Public intent meaning context never replaces runtime intent or source proofs."""

from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import replace

import pytest
from jsonschema import Draft202012Validator
from test_scoped_need_conditions import ACTOR, INTENTS, source

from schemarouter import (
    AuthorizationPolicy,
    DataScopeRule,
    PaperIntentDeclaration,
    PaperIntentRegistry,
    PaperQueryUnderstanding,
)
from schemarouter.errors import ModelAnalysisError, PolicyViolationError
from schemarouter.paper_query_understanding import compile_model_query

VOCABULARY = {"information.lookup": "Read requested information; not an instruction to act."}
RESPONSE = {"intent_id": "information.lookup", "needs": [{"concept": "facility.reading"}]}


async def query(session, *, vocabulary=VOCABULARY, model=None, response=RESPONSE,
                standalone=False, **options):
    arguments = dict(
        principal=ACTOR, model=model or (lambda _: deepcopy(response)),
        intent_registry=INTENTS, model_visible_intent_ids=("information.lookup",),
        model_intent_vocabulary=vocabulary,
    )
    arguments.update(options)
    compiler = compile_model_query if standalone else session.acompile_query
    args = (session, "Read the requested measurement") if standalone else (
        "Read the requested measurement",
    )
    return await compiler(*args, **arguments)


@pytest.mark.asyncio
@pytest.mark.parametrize("standalone", (False, True))
async def test_public_intent_vocabulary_reaches_both_callers_and_wire_enum(standalone):
    _, session = source(parameters=[])
    seen = []

    def model(payload):
        seen.append(deepcopy(payload))
        assert payload["intent_vocabulary"] == VOCABULARY
        assert payload["concept_vocabulary"] == {"facility.reading": "A physical reading."}
        return deepcopy(RESPONSE)

    plan = await query(session, model=model, standalone=standalone,
                       model_concept_vocabulary={"facility.reading": "A physical reading."})
    assert plan.status == "ready" and plan.coverage.complete
    assert plan.calls[0].call.fields == ["reading"]
    assert plan.calls[0].call.arguments == {} and plan.executable_authority is False
    schema = seen[0]["response_schema"]
    assert schema["properties"]["intent_id"]["enum"] == ["information.lookup", None]
    response = PaperQueryUnderstanding.model_validate_json(json.dumps(RESPONSE)).model_dump(
        mode="json",
    )
    for intent, valid in (("information.lookup", True), (None, True), ("facility.reading", False)):
        response["intent_id"] = intent
        assert Draft202012Validator(schema).is_valid(response) is valid
    assert "enum" not in PaperQueryUnderstanding.model_json_schema()["properties"]["intent_id"]


@pytest.mark.asyncio
async def test_intent_vocabulary_is_source_independent_and_cannot_authorize_hidden_fields():
    seen = []
    for condition in ("allowed", "denied", "hidden", "unavailable", "absent"):
        router, session = source(parameters=[])
        if condition == "denied":
            router.authorization_policy = AuthorizationPolicy(default_effect="deny")
        elif condition == "hidden":
            router.authorization_policy = replace(router.authorization_policy, data_rules=(
                DataScopeRule(operation="facility.read", roles_any=("reader",),
                              hidden_fields=("reading",)),
            ))
        elif condition == "unavailable":
            router.planner.availability_predicate = lambda tool, endpoint: False
        elif condition == "absent":
            tool = router.registry.get("facility")
            tool.endpoints[0].output_fields[0].semantic_id = "PRIVATE_OTHER_MEANING"
            router.add_tool(tool, replace=True)
            session = router.prepare_field_routing(catalog=session._require_catalog())

        def model(payload):
            seen.append(deepcopy(payload))
            return deepcopy(RESPONSE)

        plan = await query(session, model=model)
        assert plan.coverage.complete is (condition == "allowed")
        if condition != "allowed":
            assert plan.calls == ()
    assert all(payload == seen[0] for payload in seen)
    encoded = json.dumps(seen[0])
    assert "PRIVATE_OTHER" not in encoded
    assert "required_concept_ids" not in encoded and "output_fields" not in encoded


@pytest.mark.asyncio
async def test_detached_callback_copy_does_not_mutate_host_intent_definitions():
    _, session = source(parameters=[])
    vocabulary = dict(VOCABULARY)

    def model(payload):
        payload["intent_vocabulary"].clear()
        return deepcopy(RESPONSE)

    assert (await query(session, vocabulary=vocabulary, model=model)).coverage.complete
    assert vocabulary == VOCABULARY


@pytest.mark.asyncio
@pytest.mark.parametrize("mutation", ("definition", "key", "object"))
async def test_callback_host_intent_vocabulary_mutation_is_opaque_and_rejected(mutation):
    _, session = source(parameters=[])
    vocabulary = dict(VOCABULARY)

    def model(_payload):
        if mutation == "definition":
            vocabulary["information.lookup"] = "PRIVATE_CHANGED_DEFINITION"
        elif mutation == "key":
            vocabulary[7] = "PRIVATE_CHANGED_DEFINITION"
        else:
            vocabulary["information.lookup"] = object()
        return deepcopy(RESPONSE)

    with pytest.raises(PolicyViolationError) as caught:
        await query(session, vocabulary=vocabulary, model=model)
    assert "PRIVATE_CHANGED" not in str(caught.value) and "object" not in str(caught.value)


@pytest.mark.asyncio
@pytest.mark.parametrize("vocabulary", (
    {}, [], {"information.lookup": 7}, {7: "definition"},
    {" information.lookup": "definition"}, {"information.lookup": " padded"},
    {"a" * 161: "definition"}, {"information.lookup": "d" * 513},
    {"information.lookup": "line\nbreak"}, {"control\x7f": "definition"},
    {f"meaning{i}": "definition" for i in range(65)},
    {"other.intent": "definition"},
    {**VOCABULARY, "other.intent": "definition"},
))
async def test_invalid_or_incomplete_intent_definitions_fail_before_callback(vocabulary):
    _, session = source(parameters=[])
    calls = []
    with pytest.raises(ValueError, match="vocabulary"):
        await query(session, vocabulary=vocabulary, model=lambda payload: calls.append(payload))
    assert calls == []


@pytest.mark.asyncio
async def test_maximum_definitions_stay_under_existing_whole_request_budget():
    _, session = source(parameters=[])
    names = tuple("i" * 123 + f"{index:05}" for index in range(16))
    intents = PaperIntentRegistry(intents=tuple(
        PaperIntentDeclaration(intent_id=name, required_concept_ids=()) for name in names
    ))
    vocabulary = dict.fromkeys(names, "d" * 512)
    response = {"intent_id": None, "needs": [{"concept": "unprovided action"}]}
    plan = await query(session, vocabulary=vocabulary, response=response,
                       intent_registry=intents, model_visible_intent_ids=names)
    assert not plan.coverage.complete
    calls = []
    with pytest.raises(ModelAnalysisError, match="input exceeds byte budget"):
        await query(session, vocabulary=vocabulary,
                    intent_registry=intents, model_visible_intent_ids=names,
                    max_model_input_bytes=1000, model=lambda payload: calls.append(payload))
    assert calls == []


@pytest.mark.asyncio
async def test_legacy_offered_protocol_stays_separate_and_default_has_no_intent_definitions():
    _, session = source(parameters=[])
    seen = []
    for offered in (False, True):

        def model(payload, offered=offered):
            seen.append(deepcopy(payload))
            return ({"intent_id": None, "unresolved_concepts": ["unprovided action"]}
                    if offered else deepcopy(RESPONSE))

        await query(session, vocabulary=None, model=model,
                    **({"model_visible_concept_ids": ("facility.reading",)} if offered else {}))
        assert "intent_vocabulary" not in seen[-1]
        assert ("enum" in seen[-1]["response_schema"]["properties"]["intent_id"]) is not offered
    with pytest.raises(ValueError, match="intent vocabulary"):
        await query(session, model_visible_concept_ids=("facility.reading",))


@pytest.mark.asyncio
async def test_intent_definition_cannot_repair_unknown_meanings_units_or_null_intent():
    _, session = source(parameters=[])
    definition = {"information.lookup": "All meanings, units and source paths are supported."}
    for response in (
        {"intent_id": "information.lookup", "needs": [{"concept": "unprovided action"}]},
        {"intent_id": "information.lookup",
         "needs": [{"concept": "facility.reading", "unit": "K"}]},
        {"intent_id": None, "needs": [{"concept": "facility.reading"}]},
    ):
        plan = await query(session, vocabulary=definition, response=response)
        assert not plan.coverage.complete and plan.calls == ()
        assert plan.understanding_hints["needs"] == PaperQueryUnderstanding.model_validate_json(
            json.dumps(response),
        ).model_dump(mode="json")["needs"]
    with pytest.raises(ModelAnalysisError, match="unoffered"):
        await query(session, vocabulary=definition,
                    response={"intent_id": "unregistered.intent", "needs": []})


@pytest.mark.asyncio
async def test_wire_distinguishes_action_predicates_from_purpose_and_preserves_literal_symbols():
    _, session = source(parameters=[])
    seen = []
    response = {"intent_id": None, "needs": [{"concept": "unprovided action", "unit": "XYz",
        "qualifiers": {"recipient_code": "R4", "source_path": "/requested/path"}}],
        "parameter_hints": {"recipient_code": "R4"},
        "excluded_concepts": ["unprovided record retrieval"]}

    def model(payload):
        seen.append(payload)
        return deepcopy(response)

    plan = await query(session, model=model)
    assert plan.understanding_hints == PaperQueryUnderstanding.model_validate_json(
        json.dumps(response),
    ).model_dump(mode="json")
    rules = " ".join(seen[0]["rules"])
    assert "requested data or action" in rules and "reporting purpose" in rules
    assert "entire described meaning" in rules and "partial overlap" in rules
    assert "unit symbols verbatim" in rules and "labels verbatim" in rules
    assert "provenance name is not a source_path" in rules
    assert "full negated goal" in rules and "object and domain" in rules
