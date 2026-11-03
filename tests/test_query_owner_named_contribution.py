"""Owner narrowing and named-source contribution must preserve the requested meaning."""
from __future__ import annotations

import pytest
from test_source_neutral_query_conditions import _query, _source

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
    SchemaRouter,
    ToolSpec,
    UnitNormalizationSpec,
)
from schemarouter.errors import PolicyViolationError


@pytest.mark.asyncio
@pytest.mark.parametrize("owner_license", (None, "license_0"))
async def test_global_source_cannot_overwrite_an_intent_recall_owner_source(owner_license):
    router, session, _ = _source()
    pressure = FieldSpec(name="pressure", semantic_id="weather.pressure",
                         json_schema={"type": "number"}, unit="kPa")
    for name in ("provider_0", "provider_1"):
        tool = router.registry.get(name)
        tool.endpoints[0].output_fields.append(pressure)
        router.add_tool(tool, replace=True)
    owner = NativeDeclaredConcept(
        concept_id="weather.pressure", aliases=("pressure",), source_type="source_0",
        license=owner_license, required_fields=(CapabilityFieldContract.from_field(pressure),),
    )
    session = router.prepare_field_routing(catalog=NativeConceptCatalog(concepts=(
        *session._require_catalog().concepts, owner,
    )))
    before = session._require_catalog().model_dump_json()
    intents = PaperIntentRegistry(intents=(PaperIntentDeclaration(
        intent_id="weather.lookup",
        required_concept_ids=("weather.observation", "weather.pressure"),
    ),))
    plan = await _query(session, intents, [{"concept": "temperature"}],
                        raw={"source_type": "source_1"})
    assert plan.status == "no_proven_hit" and not plan.coverage.complete
    assert {call.route_id: call.call.fields for call in plan.calls} == {
        "provider_1.read": ["temperature"],
    }
    assert [item.semantic_id for item in plan.coverage.uncovered] == ["intent requirements"]
    assert session._require_catalog().model_dump_json() == before


def _named_source(kind):
    router = SchemaRouter(authorization_policy=AuthorizationPolicy(
        default_effect="deny", rules=(AuthorizationRule(
            effect="allow", operation="*.read", roles_any=("reader",),
        ),),
    ))
    left = FieldSpec(name="value", semantic_id="account.login", json_schema={"type": "string"},
                     qualifiers={"role": "author"})
    right = left.model_copy(deep=True)
    if kind == "role":
        right.qualifiers = {"role": "reviewer"}
    elif kind == "qualifier":
        left.qualifiers["temporal"] = "present"
        right.qualifiers["temporal"] = "future"
    elif kind == "schema":
        right.json_schema = {"type": "integer"}
    elif kind == "identifier":
        right.semantic_id = "account.id"
        right.identifier = True
    elif kind in ("unit", "dimension"):
        left.json_schema = right.json_schema = {"type": "number"}
        left.unit = "K"
        right.unit = "Cel" if kind == "unit" else "K"
        if kind == "dimension":
            left.unit_normalization = UnitNormalizationSpec(
                canonical_unit="K", dimension="temperature", scale=1, offset=0,
            )
            right.unit_normalization = UnitNormalizationSpec(
                canonical_unit="K", dimension="other_dimension", scale=1, offset=0,
            )
    concepts = []
    for index, field in enumerate((left, right)):
        source = "common_source" if kind == "license" else f"source_{index}"
        router.add_tool(ToolSpec(name=f"provider_{index}", source_type=source,
            license=f"license_{index}", endpoints=[EndpointSpec(
                name="read", read_only=True, output_fields=[field],
            )]))
        concepts.append(NativeDeclaredConcept(
            concept_id=f"owner.meaning_{index}", aliases=(f"meaning {index}",),
            source_type=None if kind == "license" or kind == "source" and index == 0 else source,
            license=f"license_{index}" if kind == "license" else None,
            required_fields=(CapabilityFieldContract.from_field(field),),
        ))
    session = router.prepare_field_routing(catalog=NativeConceptCatalog(concepts=tuple(concepts)))
    intents = PaperIntentRegistry(intents=(PaperIntentDeclaration(
        intent_id="weather.lookup", required_concept_ids=tuple(c.concept_id for c in concepts),
    ),))
    need = {"concept": "meaning 0"}
    if kind == "source":
        need["source_type"] = "source_0"
    return router, session, intents, need


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", (
    "role", "qualifier", "unit", "schema", "dimension", "source", "license", "identifier",
))
async def test_named_source_must_supply_the_requested_typed_field_not_only_its_sid(kind):
    _, session, intents, need = _named_source(kind)
    plan = await _query(session, intents, [need], query="meaning 0 from provider_0 and provider_1",
                        raw={"named_tools": ["provider_0", "provider_1"]})
    assert {call.route_id for call in plan.calls} == {"provider_0.read", "provider_1.read"}
    assert plan.status == "no_proven_hit" and not plan.coverage.complete
    assert [(item.semantic_id, item.qualifiers) for item in plan.coverage.uncovered] == [
        ("provider_1", ["named_tool=true"]),
    ]


@pytest.mark.asyncio
async def test_each_named_source_can_contribute_its_own_requested_role():
    _, session, intents, need = _named_source("role")
    plan = await _query(session, intents, [need, {"concept": "meaning 1"}],
                        query="meaning 0 and meaning 1 from provider_0 and provider_1",
                        raw={"named_tools": ["provider_0", "provider_1"]})
    assert plan.status == "ready" and plan.coverage.complete
    assert len(plan.coverage.covered) == 4


@pytest.mark.asyncio
async def test_named_contribution_does_not_restore_redacted_field_conditions():
    from dataclasses import replace

    router, session, intents, need = _named_source("source")
    tool = router.registry.get("provider_0")
    tool.endpoints[0].output_fields.append(FieldSpec(
        name="PRIVATE_SCHEMA_MARKER", json_schema={"type": "string"},
    ))
    router.add_tool(tool, replace=True)
    router.authorization_policy = replace(router.authorization_policy, data_rules=(
        DataScopeRule(operation="provider_0.read", roles_any=("reader",),
                      hidden_fields=("PRIVATE_SCHEMA_MARKER",)),
    ))
    session = router.prepare_field_routing(catalog=session._require_catalog())
    plan = await _query(session, intents, [need], query="meaning 0 from provider_0 and provider_1",
                        raw={"named_tools": ["provider_0", "provider_1"]})
    assert plan.status == "no_proven_hit" and not plan.coverage.complete
    assert not any(item.qualifiers == ["named_tool=true"] for item in plan.coverage.covered)
    from pydantic import TypeAdapter

    assert "PRIVATE_SCHEMA_MARKER" not in TypeAdapter(type(plan)).dump_json(plan).decode()


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ("scope", "registry", "health"))
async def test_named_field_recheck_rejects_callback_drift_without_private_diagnostics(
    monkeypatch, change,
):
    router, session, intents, need = _named_source("role")
    original_compile = type(session).compile_understood
    original_scope = router._data_scope_endpoint_view
    compiled = False
    healthy = True
    router.planner.availability_predicate = lambda tool, endpoint: healthy

    def mark_compiled(self, *args, **kwargs):
        nonlocal compiled
        result = original_compile(self, *args, **kwargs)
        compiled = True
        return result

    def changed_scope(principal, tool, endpoint):
        nonlocal healthy
        scoped = original_scope(principal, tool, endpoint)
        if compiled:
            if change == "registry":
                changed = router.registry.get(tool.key)
                changed.description = "PRIVATE_SCHEMA_MARKER"
                router.add_tool(changed, replace=True)
            elif change == "health":
                healthy = False
            else:
                scoped = scoped.model_copy(deep=True)
                scoped.output_fields[0].qualifiers["role"] = "PRIVATE_SCHEMA_MARKER"
        return scoped

    monkeypatch.setattr(type(session), "compile_understood", mark_compiled)
    monkeypatch.setattr(router, "_data_scope_endpoint_view", changed_scope)
    with pytest.raises(PolicyViolationError) as raised:
        await _query(session, intents, [need], query="meaning 0 from provider_0 and provider_1",
                     raw={"named_tools": ["provider_0", "provider_1"]})
    assert "PRIVATE_SCHEMA_MARKER" not in str(raised.value)
