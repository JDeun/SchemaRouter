"""Raw source conditions narrow owner meanings; they never grant provider access."""
from __future__ import annotations

import json
from dataclasses import replace

import pytest

from schemarouter import (
    AuthorizationPolicy,
    AuthorizationRule,
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
from schemarouter.errors import ModelAnalysisError, PolicyViolationError

ACTOR = PrincipalContext(subject="reader", roles=("reader",))


def _source(*, required=(), parameters=False, routes=2):
    router = SchemaRouter(authorization_policy=AuthorizationPolicy(
        default_effect="deny", rules=(AuthorizationRule(
            effect="allow", operation="*.read", roles_any=("reader",),
        ),),
    ))
    fields = [FieldSpec(
        name="temperature", semantic_id="weather.temperature",
        json_schema={"type": "number"}, unit="Cel", qualifiers={"role": "observation"},
    )]
    for index in range(routes):
        router.add_tool(ToolSpec(
            name=f"provider_{index}", source_type=f"source_{index}", license=f"license_{index}",
            endpoints=[EndpointSpec(
                name="read", read_only=True, output_fields=fields,
                parameters=[ParameterSpec(
                    name="city", json_schema={"type": "string"}, required=True,
                )] if parameters else [],
                input_schema={
                    "type": "object", "properties": {"city": {"type": "string"}},
                    "required": ["city"],
                } if parameters else {},
            )],
        ))
    concept = NativeDeclaredConcept(
        concept_id="weather.observation", aliases=("temperature",), required_fields=(
            CapabilityFieldContract.from_field(fields[0]),
        ),
    )
    catalog = NativeConceptCatalog(concepts=(concept,))
    session = router.prepare_field_routing(
        catalog=catalog,
        approved_host_roots=frozenset({f"provider_{index}.read" for index in range(routes)})
        if parameters else frozenset(),
    )
    intents = PaperIntentRegistry(intents=(PaperIntentDeclaration(
        intent_id="weather.lookup", required_concept_ids=required,
    ),))
    return router, session, intents


async def _query(session, intents, needs, **kwargs):
    raw = {"intent_id": "weather.lookup", "needs": needs, **kwargs.pop("raw", {})}
    return await session.acompile_query(
        kwargs.pop("query", "temperature source comparison"), principal=ACTOR,
        model=lambda _: raw, intent_registry=intents,
        model_visible_intent_ids=("weather.lookup",), **kwargs,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("global_source", (False, True))
async def test_neutral_concept_preserves_explicit_source_on_actual_candidate(global_source):
    _, session, intents = _source()
    before = session._require_catalog().model_dump_json()
    need = {"concept": "temperature", "unit": "Cel", "qualifiers": {"role": "observation"}}
    extra = {"raw": {"source_type": "source_1"}} if global_source else {}
    if not global_source:
        need["source_type"] = "source_1"
    plan = await _query(session, intents, [need], **extra)
    assert plan.status == "ready" and plan.coverage.complete
    assert [call.route_id for call in plan.calls] == ["provider_1.read"]
    assert "source_type=source_1" in plan.coverage.covered[0].qualifiers
    assert session._require_catalog().model_dump_json() == before
    assert session._require_catalog().concepts[0].source_type is None
    assert plan.snapshot_id == session.snapshot_id
    assert not plan.executable_authority


@pytest.mark.asyncio
async def test_neutral_concept_keeps_the_existing_explicit_id_model_protocol():
    _, session, intents = _source()
    seen = []

    def model(payload):
        seen.append(payload)
        return {"intent_id": "weather.lookup", "concept_ids": ["weather.observation"],
                "source_type": "source_1"}

    plan = await session.acompile_query(
        "temperature from source_1", principal=ACTOR, model=model, intent_registry=intents,
        model_visible_intent_ids=("weather.lookup",),
        model_visible_concept_ids=("weather.observation",),
    )
    assert plan.status == "ready" and [call.route_id for call in plan.calls] == ["provider_1.read"]
    assert seen[0]["offered_concepts"] == [{
        "concept_id": "weather.observation", "aliases": ["temperature"],
    }]
    assert "needs" not in seen[0]["response_fields"]


@pytest.mark.asyncio
async def test_same_concept_from_two_sources_is_two_independent_requirements():
    _, session, intents = _source()
    plan = await _query(session, intents, [
        {"concept": "temperature", "source_type": "source_0"},
        {"concept": "temperature", "source_type": "source_1"},
    ])
    assert plan.status == "ready" and plan.coverage.complete
    assert {call.route_id for call in plan.calls} == {"provider_0.read", "provider_1.read"}
    assert len(plan.coverage.required) == len(plan.coverage.covered) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ("missing", "denied", "scoped", "health"))
async def test_covered_cid_does_not_cover_another_source_requirement(failure):
    router, session, intents = _source()
    other = "source_1"
    if failure == "missing":
        other = "missing_source"
    elif failure == "denied":
        router.authorization_policy = replace(router.authorization_policy, rules=(
            AuthorizationRule(effect="allow", operation="provider_0.read", roles_any=("reader",)),
        ))
    elif failure == "scoped":
        router.authorization_policy = replace(router.authorization_policy, data_rules=(
            DataScopeRule(operation="provider_1.read", roles_any=("reader",),
                          hidden_fields=("temperature",)),
        ))
    else:
        router.planner.availability_predicate = lambda tool, endpoint: tool.name != "provider_1"
    plan = await _query(session, intents, [
        {"concept": "temperature", "source_type": "source_0"},
        {"concept": "temperature", "source_type": other},
    ])
    assert plan.status == "no_proven_hit" and not plan.coverage.complete
    assert [call.route_id for call in plan.calls] == ["provider_0.read"]
    assert len(plan.coverage.covered) == len(plan.coverage.uncovered) == 1
    assert f"source_type={other}" in plan.coverage.uncovered[0].qualifiers
    assert "license_1" not in json.dumps(plan.understanding_hints)


@pytest.mark.asyncio
async def test_conflicting_global_and_local_source_stays_uncovered():
    _, session, intents = _source()
    plan = await _query(session, intents, [
        {"concept": "temperature", "source_type": "source_1"},
    ], raw={"source_type": "source_0"})
    assert plan.status == "no_proven_hit" and plan.calls == ()
    assert {"source_type=source_1", "global_source_type=source_0"} <= set(
        plan.coverage.uncovered[0].qualifiers
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("intent_recall", (False, True))
async def test_different_concepts_keep_their_own_sources_and_intent_recall(intent_recall):
    router, session, _ = _source()
    tool = router.registry.get("provider_1")
    pressure = FieldSpec(name="pressure", semantic_id="weather.pressure",
                         json_schema={"type": "number"}, unit="kPa")
    tool.endpoints[0].output_fields.append(pressure)
    router.add_tool(tool, replace=True)
    concepts = (*session._require_catalog().concepts, NativeDeclaredConcept(
        concept_id="weather.pressure", aliases=("pressure",),
        required_fields=(CapabilityFieldContract.from_field(pressure),),
    ))
    session = router.prepare_field_routing(catalog=NativeConceptCatalog(concepts=concepts))
    intents = PaperIntentRegistry(intents=(PaperIntentDeclaration(
        intent_id="weather.lookup",
        required_concept_ids=("weather.observation", "weather.pressure") if intent_recall else (),
    ),))
    needs = [{"concept": "temperature", "source_type": "source_0"}]
    if not intent_recall:
        needs.append({"concept": "pressure", "source_type": "source_1"})
    plan = await _query(session, intents, needs)
    assert plan.status == "ready" and plan.coverage.complete
    assert {call.route_id: call.call.fields for call in plan.calls} == {
        "provider_0.read": ["temperature"], "provider_1.read": ["pressure"],
    }


@pytest.mark.asyncio
async def test_source_narrowing_does_not_split_unit_and_role_between_fields():
    router, session, intents = _source()
    concept = session._require_catalog().concepts[0].model_copy(deep=True)
    concept.required_fields = (*concept.required_fields, CapabilityFieldContract(
        semantic_id="weather.forecast", json_schema={"type": "number"}, unit="K",
        qualifiers={"role": "forecast"},
    ))
    session = router.prepare_field_routing(catalog=NativeConceptCatalog(concepts=(concept,)))
    plan = await _query(session, intents, [{
        "concept": "temperature", "source_type": "source_0", "unit": "Cel",
        "qualifiers": {"role": "forecast"},
    }])
    assert plan.status == "no_proven_hit" and plan.calls == ()
    assert {"source_type=source_0", "unit=Cel", "role=forecast"} <= set(
        plan.coverage.uncovered[0].qualifiers
    )


@pytest.mark.asyncio
async def test_per_source_proofs_do_not_promote_query_parameters():
    _, session, intents = _source(parameters=True)
    needs = [{"concept": "temperature", "source_type": f"source_{i}"} for i in range(2)]
    plan = await _query(session, intents, needs, raw={"parameter_hints": {"city": "QUERY"}})
    assert plan.status == "requires_arguments" and not plan.coverage.complete
    assert any("proof=ambiguous_source_input" in item.qualifiers
               for item in plan.coverage.uncovered)
    assert all(call.call.arguments == {} for call in plan.calls)
    assert all(call.call.missing_required_arguments == ["city"] for call in plan.calls)
    ready = await _query(session, intents, needs, host_source_arguments={
        "provider_0.read": {"city": "HOST0"}, "provider_1.read": {"city": "HOST1"},
    })
    assert ready.status == "ready"
    assert {call.route_id: call.call.arguments for call in ready.calls} == {
        "provider_0.read": {"city": "HOST0"}, "provider_1.read": {"city": "HOST1"},
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("host", (
    {"provider_0.read": []}, {"provider_0.read": {}},
    {f"provider_{i}.read": {"city": "HOST"} for i in range(6)},
))
async def test_per_source_proofs_preserve_full_host_argument_boundary(host):
    _, session, intents = _source(parameters=True)
    with pytest.raises(ModelAnalysisError):
        await _query(session, intents, [{"concept": "temperature", "source_type": "source_0"}],
                     host_source_arguments=host)


@pytest.mark.asyncio
async def test_unrelated_host_arguments_cannot_complete_the_selected_source():
    _, session, intents = _source(parameters=True)
    plan = await _query(session, intents, [{"concept": "temperature", "source_type": "source_0"}],
                        host_source_arguments={"unknown.read": {"city": "HOST"}})
    assert plan.status == "requires_arguments"
    assert plan.calls[0].call.arguments == {}
    assert plan.calls[0].call.missing_required_arguments == ["city"]


@pytest.mark.asyncio
async def test_per_source_union_preserves_k5_budget():
    _, session, intents = _source(routes=6)
    plan = await _query(session, intents, [
        {"concept": "temperature", "source_type": f"source_{i}"} for i in range(6)
    ])
    assert plan.status == "budget_unsatisfied" and plan.calls == ()
    assert not plan.coverage.complete and len(plan.coverage.uncovered) == 6


@pytest.mark.asyncio
async def test_original_owner_witness_still_rejects_mutation_during_narrowed_proof(monkeypatch):
    router, session, intents = _source()
    original = router._data_scope_endpoint_view

    def mutate_owner(principal, tool, endpoint):
        session._require_catalog().concepts[0].aliases = ("changed",)
        return original(principal, tool, endpoint)

    monkeypatch.setattr(router, "_data_scope_endpoint_view", mutate_owner)
    with pytest.raises(PolicyViolationError):
        await _query(session, intents, [{"concept": "temperature", "source_type": "source_1"}])


@pytest.mark.asyncio
async def test_narrowed_proofs_preserve_exclusions_and_named_source_contribution():
    _, session, intents = _source()
    need = {"concept": "temperature", "source_type": "source_0"}
    conflict = await _query(session, intents, [need], raw={"excluded_concepts": ["temperature"]})
    assert conflict.status == "ambiguous_paths" and conflict.calls == ()
    assert not conflict.coverage.complete
    wrong = await _query(session, intents, [need], query="temperature from provider_1",
                         raw={"named_tools": ["provider_1"]})
    assert wrong.status == "no_proven_hit" and wrong.calls == ()
    assert any("named_tool=true" in item.qualifiers for item in wrong.coverage.uncovered)
    right = await _query(session, intents, [need], query="temperature from provider_0",
                         raw={"named_tools": ["provider_0"]})
    assert right.status == "ready" and right.coverage.complete


@pytest.mark.asyncio
@pytest.mark.parametrize("mutation", ("replace_source", "revoke_health"))
async def test_narrowed_group_reproof_rejects_inflight_source_changes(monkeypatch, mutation):
    router, session, intents = _source()
    original = router._data_scope_endpoint_view
    changed = False
    healthy = True
    router.planner.availability_predicate = lambda tool, endpoint: healthy

    def change_source(principal, tool, endpoint):
        nonlocal changed, healthy
        visible = original(principal, tool, endpoint)
        if not changed:
            changed = True
            if mutation == "replace_source":
                replaced = router.registry.get("provider_1")
                replaced.endpoints[0].output_fields[0].json_schema = {"type": "integer"}
                router.add_tool(replaced, replace=True)
            else:
                healthy = False
        return visible

    monkeypatch.setattr(router, "_data_scope_endpoint_view", change_source)
    with pytest.raises(PolicyViolationError):
        await _query(session, intents, [{"concept": "temperature", "source_type": "source_1"}])
