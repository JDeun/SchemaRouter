"""Independent owner meanings need not fit a single SID-keyed FieldGroup."""
from __future__ import annotations

import pytest

from schemarouter import (
    AuthorizationPolicy,
    CapabilityFieldContract,
    EndpointSpec,
    FieldSpec,
    NativeConceptCatalog,
    NativeDeclaredConcept,
    PaperIntentDeclaration,
    PaperIntentRegistry,
    PaperUnderstanding,
    PrincipalContext,
    SchemaRouter,
    ToolSpec,
)

ACTOR = PrincipalContext(subject="typed-groups")
CONDITIONS = (
    ({"json_schema": {"type": "string"}, "qualifiers": {"role": "author"}},
     {"json_schema": {"type": "string"}, "qualifiers": {"role": "reviewer"}}),
    ({"json_schema": {"type": "number"}, "unit": "K"},
     {"json_schema": {"type": "number"}, "unit": "Cel"}),
    ({"json_schema": {"type": "string"}}, {"json_schema": {"type": "integer"}}),
    ({"json_schema": {"type": "string", "const": "first"}},
     {"json_schema": {"type": "string", "const": "second"}}),
)


def _source(conditions, *, neutral=False, separate=False):
    router = SchemaRouter(authorization_policy=AuthorizationPolicy(default_effect="allow"))
    concepts, fields = [], []
    for name, attributes in zip(("first", "second"), conditions, strict=True):
        source = name if separate else "common"
        output = FieldSpec(
            name=f"{name}_value", semantic_id="sample.value", path=["payload", name],
            **attributes,
        )
        fields.append(output)
        contract = CapabilityFieldContract.from_field(output)
        assert contract is not None
        concepts.append(NativeDeclaredConcept(
            concept_id=f"sample.{name}", aliases=(f"{name} value",),
            required_fields=(contract,), source_type=None if neutral and name == "second"
            else source, license="reviewed",
        ))
        if separate:
            router.add_tool(ToolSpec(name=name, source_type=source, license="reviewed", endpoints=[
                EndpointSpec(name="read", read_only=True, output_fields=[output]),
            ]))
    if not separate:
        router.add_tool(ToolSpec(name="common", source_type="common", license="reviewed",
            endpoints=[EndpointSpec(name="read", read_only=True, output_fields=fields)]))
    session = router.prepare_field_routing(catalog=NativeConceptCatalog(concepts=tuple(concepts)))
    intents = PaperIntentRegistry(intents=(PaperIntentDeclaration(
        intent_id="lookup", required_concept_ids=tuple(c.concept_id for c in concepts),
    ),))
    return session, intents


@pytest.mark.parametrize("conditions", CONDITIONS)
@pytest.mark.parametrize("neutral", (False, True))
@pytest.mark.parametrize("separate", (False, True))
def test_public_understood_plan_composes_conflicting_typed_contracts(
    conditions, neutral, separate,
):
    session, intents = _source(conditions, neutral=neutral, separate=separate)
    plan = session.compile_understood(
        PaperUnderstanding(intent_id="lookup"), principal=ACTOR, intent_registry=intents,
    )
    assert plan.status == "ready" and plan.coverage.complete
    assert len(plan.coverage.required) == len(plan.coverage.covered) == 2
    expected = ["first_value", "second_value"]
    assert [name for call in plan.calls for name in call.call.fields] == expected
    assert [field.source_path for call in plan.calls for field in call.fields_meta] == [
        ("payload", "first"), ("payload", "second"),
    ]
    assert not plan.executable_authority


@pytest.mark.asyncio
@pytest.mark.parametrize("neutral", (False, True))
async def test_raw_query_contract_keeps_both_role_needs_without_a_model_or_provider(neutral):
    session, intents = _source(CONDITIONS[0], neutral=neutral)
    # A fixed DTO callback exercises public query plumbing, with no model or tool I/O.
    plan = await session.acompile_query(
        "first value and second value", principal=ACTOR, intent_registry=intents,
        model_visible_intent_ids=("lookup",), model=lambda _: {
            "intent_id": "lookup", "needs": [{"concept": "first value"},
                                               {"concept": "second value"}],
        },
    )
    assert plan.status == "ready" and plan.coverage.complete
    assert [call.call.fields for call in plan.calls] == [["first_value", "second_value"]]
    assert {item.semantic_id for item in plan.coverage.covered} == {"first value", "second value"}
