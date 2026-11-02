"""Algorithm 1 structured Understand hints → source-owned direct ToolCall E0."""
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
    NativeSchemaGraphIndex,
    NativeSchemaPostingIndex,
    ParameterSpec,
    PrincipalContext,
    SchemaRouter,
    ToolSpec,
)
from schemarouter.errors import PolicyViolationError
from schemarouter.paper_understood_direct_plan import (
    PaperIntentDeclaration,
    PaperIntentRegistry,
    PaperUnderstanding,
    compile_paper_understood_direct_plan,
)

ANALYST = PrincipalContext(subject="source-researcher", roles=("analyst",))
VIEWER = PrincipalContext(subject="limited-viewer", roles=("viewer",))


def _catalog():
    return NativeConceptCatalog(concepts=(
        NativeDeclaredConcept(
            concept_id="crm.status", aliases=("case status", "문의 상태", "状態"),
            required_fields=(CapabilityFieldContract(
                semantic_id="crm.status", json_schema={"type": "string"},
            ),), source_type="crm", license="owner-reviewed",
        ),
        NativeDeclaredConcept(
            concept_id="crm.priority", aliases=("case priority", "우선순위", "優先度"),
            required_fields=(CapabilityFieldContract(
                semantic_id="crm.priority", json_schema={"type": "string"},
            ),), source_type="crm", license="owner-reviewed",
        ),
    ))


def _intents():
    return PaperIntentRegistry(intents=(PaperIntentDeclaration(
        intent_id="case.lookup",
        required_concept_ids=("crm.status", "crm.priority"),
    ),))


def _understanding(*, named_tools=(), source_type=None, hints=None):
    return PaperUnderstanding(
        intent_id="case.lookup", concept_ids=("crm.status",),
        source_type=source_type, named_tools=named_tools,
        parameter_hints=hints or {},
    )


def _tool(name, *, complete=True, safe=True, license_id="owner-reviewed",
          required_input=False):
    fields = [FieldSpec(
        name="status", semantic_id="crm.status", json_schema={"type": "string"},
    )]
    if complete:
        fields.append(FieldSpec(
            name="priority", semantic_id="crm.priority",
            json_schema={"type": "string"},
        ))
    fields.append(FieldSpec(
        name="case_id", semantic_id="crm.case_id",
        json_schema={"type": "string"}, identifier=True,
    ))
    args = [ParameterSpec(
        name="case_id", required=True, json_schema={"type": "string"},
    )] if required_input else []
    return ToolSpec(
        name=name, source_type="crm", license=license_id,
        endpoints=[EndpointSpec(
            name="read", read_only=safe, destructive=not safe,
            output_fields=fields, parameters=args,
            input_schema={
                "type": "object",
                "properties": {"case_id": {"type": "string"}},
                "required": ["case_id"],
            } if required_input else {},
        )],
    )


def _router():
    router = SchemaRouter(authorization_policy=AuthorizationPolicy(
        default_effect="deny",
        rules=(
            AuthorizationRule(
                effect="deny", operation="denied.read",
                roles_any=("analyst", "viewer"),
            ),
            AuthorizationRule(
                effect="allow", operation="*.read",
                roles_any=("analyst", "viewer"),
            ),
        ),
        data_rules=(DataScopeRule(
            operation="full_5.read", roles_any=("viewer",),
            hidden_fields=("priority",),
        ),),
    ))
    for i in range(6):
        router.add_tool(_tool(f"full_{i}"))
    router.add_tool(_tool("partial", complete=False))
    router.add_tool(_tool("denied"))
    router.add_tool(_tool("unsafe", safe=False))
    router.add_tool(_tool("wrong_license", license_id="unreviewed"))
    router.add_tool(_tool("parameterized", required_input=True))
    return router


def _index(router, *, approved_host_roots=frozenset()):
    return NativeSchemaGraphIndex.build(
        NativeSchemaPostingIndex.build(router.registry),
        approved_host_roots=approved_host_roots,
    )


def _compile(router, understanding, *, principal=ANALYST, catalog=None,
             intents=None, index=None, host_source_arguments=None):
    return compile_paper_understood_direct_plan(
        router, understanding, principal=principal,
        catalog=catalog or _catalog(), intent_registry=intents or _intents(),
        index=index or _index(router),
        host_source_arguments=host_source_arguments,
    )


def test_understood_named_sixth_tool_is_source_scoped_before_k(monkeypatch):
    router = _router()
    monkeypatch.setattr(router, "execute", lambda *a, **k: pytest.fail("executed"))
    unranked = _compile(router, _understanding())
    assert unranked.status == "over_k_unranked"
    assert unranked.calls == ()

    plan = _compile(router, _understanding(named_tools=("full_5",)))
    assert plan.status == "ready" and plan.executable_authority is False
    assert plan.bindings == ()
    assert [x.route_id for x in plan.calls] == ["full_5.read"]
    assert plan.calls[0].call.arguments == {}
    assert plan.calls[0].call.fields == ["status", "priority", "case_id"]
    assert {m.name for m in plan.calls[0].fields_meta} == {
        "status", "priority", "case_id",
    }
    assert {m.license for m in plan.calls[0].fields_meta} == {"owner-reviewed"}
    assert "partial" not in repr(plan)


def test_understood_intent_required_b_cannot_be_dropped_by_model_a():
    router = _router()
    plan = _compile(router, _understanding(named_tools=("partial",)))
    assert plan.status == "no_proven_hit"
    assert plan.calls == ()


@pytest.mark.parametrize("named_tools,principal", [
    (("no_such_tool",), ANALYST),
    (("denied",), ANALYST),
    (("unsafe",), ANALYST),
    (("wrong_license",), ANALYST),
    (("full_5",), VIEWER),
])
def test_understood_named_tool_does_not_bypass_host_authority(named_tools, principal):
    router = _router()
    result = _compile(
        router, _understanding(named_tools=named_tools), principal=principal,
    )
    assert result.status == "no_proven_hit"
    assert result.calls == () and result.bindings == ()
    assert "denied" not in repr(result)


def test_understood_source_constraint_only_narrows_candidates():
    router = _router()
    selected = _compile(router, _understanding(
        named_tools=("full_5",), source_type="crm",
    ))
    assert selected.status == "ready"
    mismatch = _compile(router, _understanding(
        named_tools=("full_5",), source_type="web",
    ))
    assert mismatch.status == "no_proven_hit" and mismatch.calls == ()


def test_untrusted_parameter_hints_never_bind_original_toolcall():
    router = _router()
    plan = _compile(router, _understanding(
        named_tools=("parameterized",), hints={"case_id": "forged-from-llm"},
    ))
    assert plan.status == "requires_arguments"
    assert [c.route_id for c in plan.calls] == ["parameterized.read"]
    assert plan.calls[0].call.arguments == {}
    assert plan.calls[0].call.missing_required_arguments == ["case_id"]
    assert plan.executable_authority is False


def test_owner_approved_direct_scalar_is_bound_without_trusting_model_hint():
    """Regression: direct Understand previously ignored even approved host roots."""
    router = _router()
    index = _index(router, approved_host_roots=frozenset({"parameterized.read"}))
    plan = _compile(router, _understanding(
        named_tools=("parameterized",), hints={"case_id": "model-forgery"},
    ), index=index, host_source_arguments={
        "parameterized.read": {"case_id": "trusted-42"},
    })
    assert plan.status == "ready"
    assert len(plan.calls) == 1 and plan.bindings == ()
    assert plan.calls[0].call.arguments == {"case_id": "trusted-42"}
    assert plan.calls[0].call.missing_required_arguments == []
    assert plan.executable_authority is False


def test_public_field_discovery_preserves_only_visible_identifiers_of_approved_root():
    """Algorithm 1 Identifiers(t) applies to approved roots within current scope."""
    router = _router()
    session = router.prepare_field_routing(
        catalog=_catalog(),
        approved_host_roots=frozenset({"parameterized.read"}),
    )
    result = session.discover("case status", principal=ANALYST)
    assert result.status == "complete"
    assert [alternative.routes[0].route_id for alternative in result.alternatives] == [
        "parameterized.read"
    ]
    assert result.alternatives[0].routes[0].output_fields == ("status", "case_id")

    original = router.authorization_policy
    assert original is not None
    router.authorization_policy = AuthorizationPolicy(
        default_effect=original.default_effect, rules=original.rules,
        data_rules=original.data_rules + (DataScopeRule(
            operation="parameterized.read", roles_any=("viewer",),
            hidden_fields=("case_id",),
        ),),
    )
    scoped = router.prepare_field_routing(
        catalog=_catalog(),
        approved_host_roots=frozenset({"parameterized.read"}),
    ).discover("case status", principal=VIEWER)
    assert scoped.status == "complete"
    assert scoped.alternatives[0].routes[0].output_fields == ("status",)


@pytest.mark.parametrize("arguments", [
    {"parameterized.read": {}},
    {"parameterized.read": {"case_id": "ok", "private": "bad"}},
    {"unknown.read": {"case_id": "ok"}},
    {"full_5.read": {"case_id": "ok"}},
])
def test_direct_arguments_must_match_original_approved_route_and_closed_schema(arguments):
    router = _router()
    index = _index(router, approved_host_roots=frozenset({"parameterized.read"}))
    with pytest.raises((ValueError, PolicyViolationError)):
        _compile(router, _understanding(named_tools=("parameterized",)),
                 index=index, host_source_arguments=arguments)


def test_unapproved_direct_source_root_cannot_bind_arguments():
    router = _router()
    with pytest.raises(PolicyViolationError):
        _compile(router, _understanding(named_tools=("parameterized",)),
                 host_source_arguments={"parameterized.read": {"case_id": "ok"}})


def test_understood_unregistered_intent_or_concept_is_rejected():
    router = _router()
    with pytest.raises(ValueError, match="intent"):
        _compile(router, PaperUnderstanding(intent_id="undeclared"))
    with pytest.raises(ValueError, match="concept"):
        _compile(router, PaperUnderstanding(
            intent_id="case.lookup", concept_ids=("private.unknown",),
        ))


def test_understood_source_change_aborts_without_partial_toolcall(monkeypatch):
    import schemarouter.paper_understood_direct_plan as module

    router = _router()
    index = _index(router)
    original = module._compile_one_route

    def revoke_after_compile(*args, **kwargs):
        result = original(*args, **kwargs)
        router.planner.availability_predicate = lambda tool, ep: (
            tool.key != "full_5"
        )
        return result

    monkeypatch.setattr(module, "_compile_one_route", revoke_after_compile)
    with pytest.raises(PolicyViolationError, match="changed|eligibility"):
        _compile(router, _understanding(named_tools=("full_5",)), index=index)
