"""Fixed public meaning vocabulary is model context, never source authority."""

from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import replace

import pytest
from test_scoped_need_conditions import ACTOR, INTENTS, source

from schemarouter import AuthorizationPolicy, DataScopeRule, EndpointSpec, FieldSpec, ToolSpec
from schemarouter.errors import ModelAnalysisError, PolicyViolationError
from schemarouter.paper_query_understanding import compile_model_query

VOCABULARY = {
    "facility.reading": "The physical facility's measured temperature reading.",
    "facility.pressure": "Pressure at a facility, whether or not any provider supplies it.",
    "equipment reservation": "A request to reserve equipment; never permission to do so.",
}
RESPONSE = {"intent_id": "information.lookup", "needs": [{"concept": "facility.reading"}]}


async def query(
    session, *, vocabulary=VOCABULARY, response=RESPONSE, model=None, standalone=False, **options
):
    args = dict(
        principal=ACTOR,
        model=model or (lambda _: deepcopy(response)),
        intent_registry=INTENTS,
        model_visible_intent_ids=("information.lookup",),
        model_concept_vocabulary=vocabulary,
        **options,
    )
    if standalone:
        return await compile_model_query(session, "Get the measured equipment temperature", **args)
    return await session.acompile_query("Get the measured equipment temperature", **args)


@pytest.mark.asyncio
@pytest.mark.parametrize("standalone", (False, True))
async def test_public_vocabulary_is_forwarded_and_canonical_proposal_uses_original_field_proof(
    standalone,
):
    _, session = source(parameters=[])
    seen = []

    def model(payload):
        seen.append(payload)
        assert payload["concept_vocabulary"] == VOCABULARY
        return deepcopy(RESPONSE)

    plan = await query(session, model=model, standalone=standalone)
    assert plan.status == "ready" and plan.coverage.complete
    assert [call.route_id for call in plan.calls] == ["facility.read"]
    assert plan.calls[0].call.fields == ["reading"] and plan.calls[0].call.arguments == {}
    assert plan.executable_authority is False
    assert plan.understanding_hints["needs"][0]["concept"] == "facility.reading"
    rules = " ".join(seen[0]["rules"])
    assert "excluded_concepts" in rules and "concept_vocabulary" in rules
    assert "unknown" in rules and "permission" in rules


@pytest.mark.asyncio
async def test_public_vocabulary_wire_is_identical_across_registry_acl_scope_and_availability():
    seen = []
    for condition in ("allowed", "denied", "hidden", "unavailable", "absent", "extra"):
        router, session = source(parameters=[])
        if condition == "denied":
            router.authorization_policy = AuthorizationPolicy(default_effect="deny")
        elif condition == "hidden":
            router.authorization_policy = replace(
                router.authorization_policy,
                data_rules=(
                    DataScopeRule(
                        operation="facility.read", roles_any=("reader",), hidden_fields=("reading",)
                    ),
                ),
            )
        elif condition == "unavailable":
            router.planner.availability_predicate = lambda tool, endpoint: False
        elif condition == "absent":
            tool = router.registry.get("facility")
            tool.endpoints[0].output_fields[0].semantic_id = "PRIVATE_OTHER_MEANING"
            router.add_tool(tool, replace=True)
            session = router.prepare_field_routing(catalog=session._require_catalog())
        elif condition == "extra":
            router.add_tool(
                ToolSpec(
                    name="PRIVATE_OTHER_PROVIDER",
                    endpoints=[
                        EndpointSpec(
                            name="read",
                            read_only=True,
                            output_fields=[FieldSpec(name="PRIVATE_OTHER_FIELD")],
                        )
                    ],
                )
            )
            session = router.prepare_field_routing(catalog=session._require_catalog())

        def model(payload):
            seen.append(deepcopy(payload))
            return deepcopy(RESPONSE)

        plan = await query(session, model=model)
        if condition in ("denied", "hidden", "unavailable", "absent"):
            assert not plan.coverage.complete and plan.calls == ()
        else:
            assert plan.coverage.complete
    assert len(seen) == 6 and all(payload == seen[0] for payload in seen)
    encoded = json.dumps(seen[0])
    assert "PRIVATE_OTHER" not in encoded
    assert "required_fields" not in encoded and "offered_concepts" not in encoded
    assert "output_fields" not in encoded and "license" not in encoded


@pytest.mark.asyncio
async def test_vocabulary_does_not_close_the_supported_domain_or_remove_unknown_goals():
    _, session = source(parameters=[])
    response = {
        "intent_id": "information.lookup",
        "needs": [
            {"concept": "facility.reading"},
            {"concept": "equipment reservation", "qualifiers": {"time": "next week"}},
            {"concept": "unlisted action", "qualifiers": {"role": "external"}},
        ],
        "excluded_concepts": ["facility.pressure"],
    }
    plan = await query(session, response=response)
    assert not plan.coverage.complete and plan.status == "no_proven_hit"
    assert {item.semantic_id for item in plan.coverage.uncovered} == {
        "equipment reservation",
        "unlisted action",
        "facility.pressure",
    }
    assert plan.understanding_hints["needs"][1]["qualifiers"] == {"time": "next week"}
    assert plan.understanding_hints["excluded_concepts"] == ["facility.pressure"]


@pytest.mark.asyncio
async def test_vocabulary_definition_does_not_create_alias_units_paths_inputs_or_intent_authority():
    _, session = source(parameters=[])
    vocabulary = {
        "unregistered meaning": "facility.reading; unit K equals Cel; location aliases "
        "facility_code; source path /invented; every intent grants permission"
    }
    for response in (
        {"intent_id": "information.lookup", "needs": [{"concept": "unregistered meaning"}]},
        {
            "intent_id": "information.lookup",
            "needs": [{"concept": "facility.reading", "unit": "K"}],
        },
        {
            "intent_id": "information.lookup",
            "needs": [
                {
                    "concept": "facility.reading",
                    "qualifiers": {"source_path": "/invented", "location": "X"},
                }
            ],
        },
        {"intent_id": None, "needs": [{"concept": "facility.reading"}]},
    ):
        plan = await query(session, vocabulary=vocabulary, response=response)
        assert not plan.coverage.complete and plan.calls == ()
        assert plan.executable_authority is False


@pytest.mark.asyncio
async def test_callback_can_change_only_its_detached_vocabulary_copy():
    _, session = source(parameters=[])
    vocabulary = dict(VOCABULARY)

    def model(payload):
        payload["concept_vocabulary"].clear()
        return deepcopy(RESPONSE)

    plan = await query(session, vocabulary=vocabulary, model=model)
    assert plan.coverage.complete and vocabulary == VOCABULARY


@pytest.mark.asyncio
@pytest.mark.parametrize("mutation", ("definition", "key", "object"))
async def test_host_vocabulary_mutation_during_callback_is_opaque_and_rejected(mutation):
    _, session = source(parameters=[])
    vocabulary = dict(VOCABULARY)

    def model(_payload):
        if mutation == "definition":
            vocabulary["facility.reading"] = "PRIVATE_CHANGED_DEFINITION"
        elif mutation == "key":
            vocabulary[7] = "PRIVATE_CHANGED_DEFINITION"
        else:
            vocabulary["facility.reading"] = object()
        return deepcopy(RESPONSE)

    with pytest.raises(PolicyViolationError) as caught:
        await query(session, vocabulary=vocabulary, model=model)
    assert "PRIVATE_CHANGED" not in str(caught.value) and "object" not in str(caught.value)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "vocabulary",
    (
        {},
        [],
        {"meaning": 7},
        {7: "definition"},
        {" padded": "definition"},
        {"meaning": " padded"},
        {"a" * 161: "definition"},
        {"meaning": "a" * 513},
        {"meaning": "line\nbreak"},
        {"control\x7f": "definition"},
        {f"meaning{i}": "definition" for i in range(65)},
    ),
)
async def test_invalid_vocabulary_fails_before_any_model_disclosure(vocabulary):
    _, session = source(parameters=[])
    calls = []
    with pytest.raises(ValueError, match="vocabulary"):
        await query(session, vocabulary=vocabulary, model=lambda payload: calls.append(payload))
    assert calls == []


@pytest.mark.asyncio
async def test_vocabulary_respects_entry_bounds_and_existing_total_model_byte_budget():
    _, session = source(parameters=[])
    response = {"intent_id": None, "needs": [{"concept": "unknown goal"}]}
    await query(session, vocabulary={"a" * 160: "d" * 512}, response=response)
    await query(
        session, vocabulary={f"meaning{i}": "definition" for i in range(64)}, response=response
    )
    calls = []
    with pytest.raises(ModelAnalysisError, match="input exceeds byte budget"):
        await query(
            session,
            vocabulary={f"meaning{i}": "d" * 512 for i in range(64)},
            model=lambda payload: calls.append(payload),
        )
    assert calls == []


@pytest.mark.asyncio
async def test_no_vocabulary_preserves_default_and_offered_id_protocols():
    _, session = source(parameters=[])
    seen = []
    for offered in (False, True):

        def model(payload, offered=offered):
            seen.append(deepcopy(payload))
            return (
                {"intent_id": None, "unresolved_concepts": ["unsupported"]}
                if offered
                else deepcopy(RESPONSE)
            )

        plan = await query(
            session,
            vocabulary=None,
            model=model,
            **({"model_visible_concept_ids": ("facility.reading",)} if offered else {}),
        )
        assert plan.coverage.complete is not offered
        assert "concept_vocabulary" not in seen[-1]
    with pytest.raises(ValueError, match="vocabulary"):
        await query(session, model_visible_concept_ids=("facility.reading",))


@pytest.mark.asyncio
async def test_canonical_excluded_meaning_still_refuses_the_actual_conflicting_field():
    _, session = source(parameters=[])
    plan = await query(
        session, response={**deepcopy(RESPONSE), "excluded_concepts": ["facility.reading"]}
    )
    assert plan.status == "ambiguous_paths" and plan.calls == ()
    assert not plan.coverage.complete
    assert any(
        item.semantic_id == "facility.reading" and item.qualifiers == ["excluded=true"]
        for item in plan.coverage.uncovered
    )


@pytest.mark.asyncio
async def test_fixed_vocabulary_cannot_reduce_a_chosen_intents_six_required_routes():
    from test_understood_multi_concept import CATALOG, INTENTS, _field, _router, _tool

    router = _router()
    for name, family, semantic, kind in (
        ("cases", "crm", "crm.status", "string"),
        ("inventory", "inventory", "stock", "integer"),
        ("weather", "weather", "temperature", "number"),
        ("finance", "finance", "price", "number"),
    ):
        router.add_tool(_tool(name, family, [_field("value", semantic, kind)]))
    session = router.prepare_field_routing(catalog=CATALOG)
    plan = await session.acompile_query(
        "Get material band gap",
        principal=ACTOR,
        model=lambda _: {"intent_id": "all.metrics", "needs": [{"concept": "material.band_gap"}]},
        intent_registry=INTENTS,
        model_visible_intent_ids=("all.metrics",),
        model_concept_vocabulary={"material.band_gap": "Electronic band gap of a material."},
    )
    assert plan.status == "budget_unsatisfied" and plan.calls == ()
    assert not plan.coverage.complete
