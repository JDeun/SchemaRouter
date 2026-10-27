"""#1775: reuse prepared schema-only routing for structured Understand(q)."""
from __future__ import annotations

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
    PaperUnderstanding,
    ParameterSpec,
    SchemaRouter,
    ToolSpec,
)
from schemarouter.errors import PolicyViolationError
from scripts.benchmark_native_fork_fieldgroup_e0 import (
    ACTOR,
    RIGHT,
    ROOT,
    build_fixture,
)

CATALOG = NativeConceptCatalog(concepts=(NativeDeclaredConcept(
    concept_id="crm.owner", aliases=("customer owner", "고객 담당자", "顧客担当者"),
    source_type="crm", license="host-reviewed-synthetic",
    required_fields=(CapabilityFieldContract(
        semantic_id="crm.fork_owner", json_schema={"type": "string"},
    ),),
),))
INTENTS = PaperIntentRegistry(intents=(PaperIntentDeclaration(
    intent_id="crm.owner_lookup", required_concept_ids=("crm.owner",),
),))


def test_prepared_session_compiles_structured_understanding_to_one_hop_schema_only():
    router = build_fixture(500)
    session = router.prepare_field_routing(catalog=CATALOG)
    plan = session.compile_understood(
        PaperUnderstanding(
            intent_id="crm.owner_lookup", named_tools=("fork_owner",),
            parameter_hints={"customer_id": "MODEL_FORGED_VALUE"},
        ),
        principal=ACTOR, intent_registry=INTENTS,
    )

    assert plan.status == "requires_observation"
    assert plan.executable_authority is False
    assert tuple(item.route_id for item in plan.calls) == (ROOT, RIGHT)
    assert [item.call.fields for item in plan.calls] == [
        ["customer_id"], ["owner"],
    ]
    assert [item.call.arguments for item in plan.calls] == [{}, {}]
    assert [(edge.consumer_call_index, edge.parameter,
             edge.producer_call_index, edge.producer_field)
            for edge in plan.bindings] == [(1, "customer_id", 0, "customer_id")]
    assert [(p.name, p.required, p.json_types)
            for p in plan.calls[1].parameters_meta] == [
        ("customer_id", True, ("string",)),
    ]


def test_understood_direct_host_root_accepts_only_explicit_host_inputs():
    router = build_fixture(500)
    session = router.prepare_field_routing(
        catalog=CATALOG, approved_host_roots=frozenset({RIGHT}),
    )
    plan = session.compile_understood(
        PaperUnderstanding(
            intent_id="crm.owner_lookup", named_tools=("fork_owner",),
            parameter_hints={"customer_id": "FORGED"},
        ), principal=ACTOR, intent_registry=INTENTS,
        host_source_arguments={RIGHT: {"customer_id": "HOST-OWNED"}},
    )
    assert plan.status == "ready"
    assert not plan.executable_authority
    assert [call.route_id for call in plan.calls] == [RIGHT]
    assert plan.calls[0].call.arguments == {"customer_id": "HOST-OWNED"}
    assert plan.bindings == ()


def _two_hop_router() -> SchemaRouter:
    router = SchemaRouter(authorization_policy=AuthorizationPolicy(
        default_effect="deny", rules=(AuthorizationRule(
            effect="allow", operation="*.read", roles_any=("reader",),
        ),),
    ))
    for tool_name, output_name, output_semantic, input_name, input_semantic in (
        ("origin", "contact_id", "crm.contact_id", None, None),
        ("middle", "case_id", "crm.case_id", "contact_id", "crm.contact_id"),
        ("leaf", "owner", "crm.fork_owner", "case_id", "crm.case_id"),
    ):
        parameters = [ParameterSpec(
            name=input_name, semantic_id=input_semantic,
            required=True, json_schema={"type": "string"},
        )] if input_name is not None else []
        router.add_tool(ToolSpec(
            name=tool_name, source_type="crm", license="host-reviewed-synthetic",
            endpoints=[EndpointSpec(
                name="read", read_only=True, parameters=parameters,
                input_schema={"type": "object", "properties": {
                    input_name: {"type": "string"},
                }, "required": [input_name]} if input_name is not None else {},
                output_fields=[FieldSpec(
                    name=output_name, semantic_id=output_semantic,
                    json_schema={"type": "string"},
                    identifier=tool_name != "leaf",
                )],
            )],
        ))
    return router


def test_understood_named_two_hop_uses_exact_existing_graph_contract():
    router = _two_hop_router()
    plan = router.prepare_field_routing(catalog=CATALOG).compile_understood(
        PaperUnderstanding(intent_id="crm.owner_lookup", named_tools=("leaf",)),
        principal=ACTOR, intent_registry=INTENTS,
    )
    assert plan.status == "requires_observation"
    assert [call.route_id for call in plan.calls] == [
        "origin.read", "middle.read", "leaf.read",
    ]
    assert [(binding.consumer_call_index, binding.parameter,
             binding.producer_call_index, binding.producer_field)
            for binding in plan.bindings] == [
        (1, "contact_id", 0, "contact_id"),
        (2, "case_id", 1, "case_id"),
    ]
    assert all(not call.call.arguments for call in plan.calls)
    assert [p.name for p in plan.calls[2].parameters_meta] == ["case_id"]


def test_understood_session_honors_live_authorization_and_schema_drift():
    router = build_fixture(500)
    session = router.prepare_field_routing(catalog=CATALOG)
    hints = PaperUnderstanding(
        intent_id="crm.owner_lookup", named_tools=("fork_owner",),
    )
    router.authorization_policy = AuthorizationPolicy(
        default_effect="deny", rules=(AuthorizationRule(
            effect="allow", operation="fork_origin.read", roles_any=("reader",),
        ),),
    )
    denied = session.compile_understood(
        hints, principal=ACTOR, intent_registry=INTENTS,
    )
    assert denied.status == "no_proven_hit"
    assert denied.calls == ()

    router.add_tool(ToolSpec(name="new_tool", endpoints=[EndpointSpec(name="read")]))
    with pytest.raises(PolicyViolationError, match="stale|changed|source"):
        session.compile_understood(hints, principal=ACTOR, intent_registry=INTENTS)


def test_understood_session_abstains_when_required_output_field_becomes_hidden():
    router = build_fixture(500)
    tool = router.registry.get("fork_owner")
    tool.endpoints[0].output_fields.append(FieldSpec(
        name="audit_note", json_schema={"type": "string"},
    ))
    router.add_tool(tool, replace=True)
    session = router.prepare_field_routing(catalog=CATALOG)
    router.authorization_policy = AuthorizationPolicy(
        default_effect="deny", rules=(AuthorizationRule(
            effect="allow", operation="*.read", roles_any=("reader",),
        ),),
        data_rules=(DataScopeRule(
            operation="fork_owner.read", roles_any=("reader",),
            visible_fields=("audit_note",),
        ),),
    )
    plan = session.compile_understood(
        PaperUnderstanding(intent_id="crm.owner_lookup", named_tools=("fork_owner",)),
        principal=ACTOR, intent_registry=INTENTS,
    )
    assert plan.status == "no_proven_hit"
    assert plan.calls == ()


@pytest.mark.parametrize("bad_k,bad_hops", [(4, 2), (6, 2), (5, 0), (5, 3)])
def test_understood_session_preserves_exact_paper_plan_bounds(bad_k, bad_hops):
    session = build_fixture(500).prepare_field_routing(catalog=CATALOG)
    with pytest.raises(ValueError, match="K5|one or two"):
        session.compile_understood(
            PaperUnderstanding(intent_id="crm.owner_lookup"),
            principal=ACTOR, intent_registry=INTENTS,
            k=bad_k, max_hops=bad_hops,
        )


def test_understood_session_rejects_unreviewed_intent_and_never_executes(monkeypatch):
    router = build_fixture(500)
    session = router.prepare_field_routing(catalog=CATALOG)

    def forbidden(*_args, **_kwargs):
        pytest.fail("schema-only understood route may not execute provider data")

    monkeypatch.setattr(router.executor, "execute", forbidden)
    monkeypatch.setattr(router, "execute", forbidden)
    with pytest.raises(ValueError, match="unregistered|unknown"):
        session.compile_understood(
            PaperUnderstanding(intent_id="invented.intent"),
            principal=ACTOR, intent_registry=INTENTS,
        )
    plan = session.compile_understood(
        PaperUnderstanding(intent_id="crm.owner_lookup", named_tools=("fork_owner",)),
        principal=ACTOR, intent_registry=INTENTS,
    )
    assert plan.status == "requires_observation"
