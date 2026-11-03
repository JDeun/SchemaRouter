"""Source-contract P2 regressions; not natural-language accuracy evidence."""
from __future__ import annotations

import json
from dataclasses import asdict

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
    PolicyViolationError,
    PrincipalContext,
    SchemaRouter,
    ToolSpec,
    UnitNormalizationSpec,
)
from schemarouter.paper_understood_direct_plan import PaperUnderstanding

ACTOR = PrincipalContext(subject="p2-probe", roles=("reader",))
SECRET = "PRIVATE_HIDDEN_SCHEMA_MARKER"


def source(*, units=False, restricted=False, identifier_input=False, output_identifier=False):
    router = SchemaRouter(authorization_policy=AuthorizationPolicy(
        default_effect="deny", rules=(AuthorizationRule(
            effect="allow", operation="weather.read", roles_any=("reader",),
        ),),
        data_rules=(DataScopeRule(
            operation="weather.read", roles_any=("reader",), hidden_fields=("secret",),
        ),) if restricted else (),
    ))
    schema = {"type": "number", "minimum": 0, "maximum": 373.15}
    if restricted:
        schema["description"] = SECRET
    router.add_tool(ToolSpec(name="weather", source_type="weather", license="reviewed",
        endpoints=[EndpointSpec(name="read", read_only=True,
            parameters=[ParameterSpec(name="city", required=True,
                semantic_id="weather.city" if identifier_input else None,
                json_schema={"type": "string"})],
            input_schema={"type": "object", "properties": {"city": {"type": "string"}},
                          "required": ["city"]},
            output_fields=[FieldSpec(name="temperature", semantic_id="weather.temperature",
                path=["payload", "temperature"], result_path=["answer", "temperature"],
                json_schema=schema, unit="K" if units else None, identifier=output_identifier,
                unit_normalization=UnitNormalizationSpec(
                    canonical_unit="Cel", dimension="temperature", scale=1, offset=-273.15,
                ) if units else None)] + ([
                FieldSpec(name="secret", semantic_id="weather.secret",
                          json_schema={"type": "string"}, description=SECRET),
            ] if restricted else []),
        )]))
    catalog = NativeConceptCatalog(concepts=(NativeDeclaredConcept(
        concept_id="weather.temperature", aliases=("temperature",),
        source_type="weather", license="reviewed",
        required_fields=(CapabilityFieldContract(semantic_id="weather.temperature",
            json_schema={"type": "number"}, unit="Cel" if units else None),),
    ),))
    intents = PaperIntentRegistry(intents=(PaperIntentDeclaration(
        intent_id="weather.lookup", required_concept_ids=("weather.temperature",),
    ),))
    session = router.prepare_field_routing(
        catalog=catalog, approved_host_roots=frozenset({"weather.read"}),
    )
    return router, session, intents


def compile_understood(session, intents, *, host=None):
    return session.compile_understood(
        PaperUnderstanding(intent_id="weather.lookup", named_tools=("weather",),
                           parameter_hints={"city": "MODEL_FORGED"}),
        principal=ACTOR, intent_registry=intents, host_source_arguments=host,
    )


def test_named_direct_scalar_input_retains_source_fields_and_missing_arguments():
    _, session, intents = source()
    plan = compile_understood(session, intents)
    assert plan.status == "requires_arguments"
    assert plan.calls[0].call.fields == ["temperature"]
    assert plan.calls[0].call.missing_required_arguments == ["city"]
    assert plan.calls[0].call.arguments == {}
    assert plan.bindings == () and plan.executable_authority is False


@pytest.mark.parametrize("output_identifier", (False, True))
def test_approved_unit_bearing_root_is_direct_only_and_has_canonical_metadata(output_identifier):
    router, session, intents = source(units=True, output_identifier=output_identifier)
    assert all(not c.produces for c in session._index._source_contracts)
    assert session._index.graph.edges == ()
    missing = compile_understood(session, intents)
    assert missing.status == "requires_arguments"
    plan = compile_understood(session, intents, host={"weather.read": {"city": "Busan"}})
    assert plan.status == "ready" and plan.bindings == ()
    assert plan.calls[0].call.arguments == {"city": "Busan"}
    meta, = plan.calls[0].fields_meta
    assert meta.source_path == ("payload", "temperature")
    assert meta.result_path == ("answer", "temperature")
    assert meta.source_unit == "K" and meta.unit == "Cel"
    assert meta.json_schema == {"type": "number", "minimum": -273.15, "maximum": 100.0}
    original = router.registry.get("weather").endpoint("read").output_fields[0]
    assert original.json_schema["minimum"] == 0 and original.unit == "K"


@pytest.mark.asyncio
@pytest.mark.parametrize("host", (None, {"weather.read": {"city": "Busan"}}))
async def test_public_model_query_keeps_typed_direct_mapping_without_trusting_model_values(host):
    _, session, intents = source(units=True)
    payloads = []

    def model(payload):
        payloads.append(payload)
        return {"intent_id": "weather.lookup", "named_tools": ["weather"],
                "parameter_hints": {"city": "MODEL_FORGED"}}

    plan = await session.acompile_query(
        "temperature in Busan", principal=ACTOR, model=model, intent_registry=intents,
        model_visible_intent_ids=("weather.lookup",),
        model_visible_concept_ids=("weather.temperature",),
        model_visible_tool_keys=("weather",), host_source_arguments=host,
    )
    assert len(payloads) == 1
    assert plan.status == ("requires_arguments" if host is None else "no_proven_hit")
    assert plan.coverage.complete is (host is None)
    conditions = plan.coverage.covered if host is None else plan.coverage.uncovered
    expected = "proof=pending_host_input" if host is None else "proof=conflicting_host_input"
    assert any(expected in item.qualifiers for item in conditions)
    assert plan.calls[0].call.arguments == ({} if host is None else {"city": "Busan"})
    assert plan.calls[0].call.fields == ["temperature"]
    assert plan.calls[0].fields_meta[0].source_path == ("payload", "temperature")
    assert plan.executable_authority is False


def test_field_schema_metadata_is_detached_and_original_paths_are_stable():
    router, session, intents = source()
    before = router.registry.get("weather").fingerprint
    plan = compile_understood(session, intents, host={"weather.read": {"city": "Busan"}})
    meta, = plan.calls[0].fields_meta
    meta.json_schema["minimum"] = 999
    assert router.registry.get("weather").fingerprint == before
    again = compile_understood(session, intents, host={"weather.read": {"city": "Busan"}})
    assert again.calls[0].fields_meta[0].json_schema["minimum"] == 0
    assert meta.source_path == ("payload", "temperature")


def test_restricted_metadata_uses_only_current_visible_field_view():
    _, session, intents = source(restricted=True)
    plan = compile_understood(session, intents, host={"weather.read": {"city": "Busan"}})
    meta, = plan.calls[0].fields_meta
    assert meta.source_path == meta.result_path == ("temperature",)
    assert meta.json_schema == {"type": "number"}
    exposed = json.dumps(asdict(meta))
    assert SECRET not in exposed and "secret" not in exposed
    assert "payload" not in exposed and "answer" not in exposed


def test_missing_semantic_identifier_retains_direct_mapping_when_no_producer_is_proven():
    _, session, intents = source(identifier_input=True)
    plan = compile_understood(session, intents)
    assert plan.status == "requires_arguments"
    assert plan.calls[0].call.fields == ["temperature"]
    assert plan.calls[0].call.missing_required_arguments == ["city"]
    assert not plan.bindings and plan.executable_authority is False


@pytest.mark.parametrize("value", (42, True, None))
def test_p2_host_inputs_still_require_exact_source_types(value):
    _, session, intents = source(units=True)
    with pytest.raises(PolicyViolationError, match="source|eligibility|argument"):
        compile_understood(session, intents, host={"weather.read": {"city": value}})


def test_unit_bearing_direct_mapping_does_not_approve_host_arguments():
    router, session, intents = source(units=True)
    unapproved = router.prepare_field_routing(catalog=session._catalog)
    with pytest.raises(PolicyViolationError, match="source|eligibility|argument"):
        compile_understood(unapproved, intents, host={"weather.read": {"city": "Busan"}})


@pytest.mark.parametrize("mutation", ("host", "policy", "schema"))
def test_mutation_during_p2_source_proof_still_fails_closed(mutation):
    router, session, intents = source()
    host = {"weather.read": {"city": "Busan"}}

    def availability(tool, endpoint):
        if mutation == "host":
            host["weather.read"]["city"] = "FORGED"
        elif mutation == "policy":
            router.authorization_policy.default_effect = "allow"
        else:
            replacement = router.registry.get("weather")
            replacement.endpoint("read").output_fields[0].path = ["FORGED"]
            router.add_tool(replacement, replace=True)
        return True

    router.planner.availability_predicate = availability
    with pytest.raises(PolicyViolationError):
        compile_understood(session, intents, host=host)
