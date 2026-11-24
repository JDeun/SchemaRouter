"""Direct scalar-valued native unions, not complex input or G5 authorization."""
from __future__ import annotations

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
    SchemaRouter,
    ToolSpec,
)
from schemarouter.errors import PolicyViolationError
from schemarouter.paper_typed_tool_plan import _bounded_direct_scalar_fit

ACTOR = PrincipalContext(subject="direct-union-review")
SID = "material.band_gap"
ROUTE = "material.search"
INTENT = "find_band_gap"
FORMULA = {"anyOf": [{"type": "string"}, {"type": "array", "items": {"type": "string"}}]}
IDENTIFIER = {"anyOf": [{"type": "string"}, {"type": "integer"}]}


@pytest.mark.parametrize("schema,value,expected", [
    (FORMULA, "LiFePO4", True),
    (FORMULA, ["LiFePO4"], False),
    (FORMULA, 42, False),
    (IDENTIFIER, "aspirin", True),
    (IDENTIFIER, 2244, True),
    (IDENTIFIER, True, False),
    (IDENTIFIER, 2244.0, False),
    (IDENTIFIER, 2**63, False),
    (IDENTIFIER, "x" * 4097, False),
    ({"type": ["string", "integer"]}, "aspirin", True),
    ({"type": ["string", "integer"]}, 2244, True),
    ({"type": ["string", "integer"]}, False, False),
    ({"anyOf": [{"type": "string", "minLength": 3}, {"type": "integer"}]}, "x", False),
    ({"oneOf": [{"type": "number"}, {"type": "integer"}]}, 4, False),
    ({"oneOf": [{"type": "string"}, {"type": "integer"}]}, "graphene", True),
    ({"anyOf": [{"type": "string", "enum": ["A"]}, {"type": "integer"}]}, "B", False),
    ({"anyOf": [{"type": "string"}, {}]}, "x", False),
    ({"anyOf": [{"type": "string"}, {"$ref": "https://example.invalid/schema"}]}, "x", False),
    ({"type": "object"}, {"formula": "LiFePO4"}, False),
    ({"type": "number"}, float("nan"), False),
    ({}, "anything", False),
])
def test_direct_union_requires_actual_scalar_branch_and_full_native_validation(
    schema, value, expected,
):
    assert _bounded_direct_scalar_fit(schema, value) is expected


def _fixture(schema, *, approval=False, restricted=False, required=False):
    router = SchemaRouter(authorization_policy=AuthorizationPolicy(
        default_effect="allow",
        data_rules=(DataScopeRule(operation=ROUTE, hidden_fields=("private",)),)
        if restricted else (),
    ))
    fields = [
        FieldSpec(name="gap", semantic_id=SID, unit="eV", json_schema={"type": "number"}),
        FieldSpec(name="private", json_schema={"type": "string"}),
    ]
    parameter = ParameterSpec(name="formula", required=required, json_schema=schema)
    router.add_tool(ToolSpec(
        name="material", source_type="calculated", license="reviewed",
        endpoints=[EndpointSpec(
            name="search", read_only=True, output_fields=fields, parameters=[parameter],
            input_schema={
                "type": "object", "properties": {"formula": schema},
                "required": ["formula"] if required else [], "additionalProperties": False,
            },
        )],
    ))
    catalog = NativeConceptCatalog(concepts=(NativeDeclaredConcept(
        concept_id=SID, aliases=("band gap",), source_type="calculated",
        required_fields=(CapabilityFieldContract(
            semantic_id=SID, unit="eV", json_schema={"type": "number"},
        ),),
    ),))
    session = router.prepare_field_routing(catalog=catalog)
    intents = PaperIntentRegistry(
        intents=(PaperIntentDeclaration(intent_id=INTENT, required_concept_ids=(SID,)),),
        projection_snapshot_id=session.snapshot_id if approval else None,
        approved_direct_parameter_routes=(ROUTE,) if approval else (),
    )
    rank = PaperNativeRankPolicy(
        snapshot_id=session.snapshot_id, focus_direct=True, direct_score_mode="paper_v1",
    )
    return session, intents, rank


async def _query(schema, *, value="LiFePO4", host=None, approval=False, restricted=False,
                 required=False, original=True):
    session, intents, rank = _fixture(
        schema, approval=approval, restricted=restricted, required=required,
    )
    plan = await session.acompile_query(
        "Get band gap for the specified material.", principal=ACTOR,
        intent_registry=intents, model_visible_intent_ids=(INTENT,),
        rank_policy=rank if original else None,
        host_source_arguments={ROUTE: host} if host is not None else None,
        model=lambda _: {
            "intent_id": INTENT, "needs": [{"concept": "band gap"}],
            "parameter_hints": {"formula": value},
        },
    )
    assert not plan.executable_authority and not plan.bindings
    return plan


@pytest.mark.parametrize("schema,value", [(FORMULA, "LiFePO4"), (IDENTIFIER, 2244)])
@pytest.mark.asyncio
async def test_actual_direct_plan_proposes_scalar_union_without_binding(schema, value):
    plan = await _query(schema, value=value)
    assert plan.status == "requires_arguments" and plan.coverage.complete
    assert plan.calls[0].call.arguments == {}
    assert dict(plan.calls[0].parameter_proposals) == {"formula": value}
    assert any("proof=pending_host_input" in item.qualifiers for item in plan.coverage.covered)


@pytest.mark.asyncio
async def test_original_direct_approval_accepts_scalar_union_but_not_complex_host_value():
    plan = await _query(FORMULA, approval=True, required=True, host={"formula": "LiFePO4"})
    assert plan.status == "ready" and plan.coverage.complete
    assert plan.calls[0].call.arguments == {"formula": "LiFePO4"}
    assert not plan.calls[0].parameter_proposals
    with pytest.raises(PolicyViolationError):
        await _query(FORMULA, approval=True, required=True, host={"formula": ["LiFePO4"]})


@pytest.mark.asyncio
async def test_union_does_not_change_default_or_hidden_scoped_input_fit():
    for opts in ({"original": False}, {"restricted": True}):
        plan = await _query(FORMULA, **opts)
        assert not plan.coverage.complete
        assert plan.calls[0].call.arguments == {}
        assert not plan.calls[0].parameter_proposals
    with pytest.raises(PolicyViolationError):
        await _query(FORMULA, approval=True, restricted=True, host={"formula": "LiFePO4"})


@pytest.mark.asyncio
async def test_conflicting_approved_host_union_value_remains_uncovered():
    plan = await _query(FORMULA, approval=True, required=True, host={"formula": "GaN"})
    assert not plan.coverage.complete
    assert plan.calls[0].call.arguments == {"formula": "GaN"}
    assert not plan.calls[0].parameter_proposals
    assert any("proof=conflicting_host_input" in item.qualifiers for item in plan.coverage.uncovered)


def test_union_approval_never_registers_a_g5_root():
    session, _, _ = _fixture(FORMULA, approval=True, required=True)
    assert ROUTE not in session._index.approved_host_roots
    with pytest.raises((ValueError, PolicyViolationError)):
        session.revise_catalog(
            catalog=session._require_catalog(), approved_host_roots=frozenset({ROUTE}),
        )
