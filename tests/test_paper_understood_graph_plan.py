"""Original-paper named target → source-native one/two-hop typed E0 plans."""

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
from schemarouter.paper_typed_tool_plan import PaperPlanBinding
from schemarouter.paper_understood_direct_plan import (
    PaperIntentDeclaration,
    PaperIntentRegistry,
    PaperUnderstanding,
)
from schemarouter.paper_understood_graph_plan import (
    compile_paper_understood_graph_plan,
)

ACTOR = PrincipalContext(subject="native-paper", roles=("reader",))
CATALOG = NativeConceptCatalog(concepts=(NativeDeclaredConcept(
    concept_id="crm.status", aliases=("case status", "문의 상태", "問い合わせ状態"),
    source_type="crm", license="reviewed",
    required_fields=(CapabilityFieldContract(
        semantic_id="crm.status", json_schema={"type": "string"},
    ),),
),))
INTENTS = PaperIntentRegistry(intents=(PaperIntentDeclaration(
    intent_id="case.lookup", required_concept_ids=("crm.status",),
),))


def _node(
    name: str, *, input_semantic: str | None = None,
    output_semantic: str = "crm.status", identifier: bool = False,
    output_type: str = "string", safe: bool = True,
) -> ToolSpec:
    output_name = output_semantic.split(".")[-1]
    input_name = input_semantic.split(".")[-1] if input_semantic else None
    parameters = [ParameterSpec(
        name=input_name, semantic_id=input_semantic, required=True,
        json_schema={"type": "string"},
    )] if input_name else []
    return ToolSpec(
        name=name, source_type="crm", license="reviewed",
        endpoints=[EndpointSpec(
            name="read", read_only=safe, destructive=not safe,
            parameters=parameters,
            input_schema={"type": "object", "properties": {
                input_name: {"type": "string"},
            }, "required": [input_name]} if input_name else {},
            output_fields=[FieldSpec(
                name=output_name, semantic_id=output_semantic,
                json_schema={"type": output_type}, identifier=identifier,
            )],
        )],
    )


def _router(*, hops: int = 1, n_targets: int = 1, deny_middle=False,
            hidden_middle=False, wrong_middle_type=False,
            unsafe_target=False) -> SchemaRouter:
    rules = (AuthorizationRule(
        effect="deny", operation="middle.read", roles_any=("reader",),
    ),) if deny_middle else ()
    router = SchemaRouter(authorization_policy=AuthorizationPolicy(
        default_effect="deny",
        rules=rules + (AuthorizationRule(
            effect="allow", operation="*.read", roles_any=("reader",),
        ),),
        data_rules=(DataScopeRule(
            operation="middle.read", roles_any=("reader",),
            hidden_fields=("case_id",),
        ),) if hidden_middle else (),
    ))
    router.add_tool(_node(
        "root", output_semantic="crm.contact_id" if hops == 2 else "crm.case_id",
        identifier=True,
    ))
    if hops == 2:
        router.add_tool(_node(
            "middle", input_semantic="crm.contact_id",
            output_semantic="crm.case_id", identifier=True,
            output_type="integer" if wrong_middle_type else "string",
        ))
    for i in range(n_targets):
        router.add_tool(_node(
            f"target_{i}", input_semantic="crm.case_id",
            safe=not unsafe_target,
        ))
    return router


def _compile(router, *, named_tools=("target_0",), max_hops=2,
             hints=None, index=None, source_type=None, host_source_arguments=None,
             rank_policy=None, allow_unnamed_graph_discovery=False):
    return compile_paper_understood_graph_plan(
        router, PaperUnderstanding(
            intent_id="case.lookup", named_tools=named_tools,
            parameter_hints=hints or {}, source_type=source_type,
        ),
        principal=ACTOR, catalog=CATALOG, intent_registry=INTENTS,
        index=index or NativeSchemaGraphIndex.build(
            NativeSchemaPostingIndex.build(router.registry),
        ),
        max_hops=max_hops,
        host_source_arguments=host_source_arguments,
        rank_policy=rank_policy,
        allow_unnamed_graph_discovery=allow_unnamed_graph_discovery,
    )


def test_named_graph_prefers_source_approved_direct_root_argument():
    """A standalone typed direct route must not defer to an invented G5 producer."""
    router = _router()
    router.add_tool(_node("direct", input_semantic="crm.case_id", identifier=True))
    index = NativeSchemaGraphIndex.build(
        NativeSchemaPostingIndex.build(router.registry),
        approved_host_roots=frozenset({"direct.read"}),
    )
    plan = _compile(
        router, named_tools=("direct",), index=index,
        hints={"case_id": "untrusted"},
        host_source_arguments={"direct.read": {"case_id": "owner-id"}},
    )
    assert plan.status == "ready"
    assert [receipt.route_id for receipt in plan.calls] == ["direct.read"]
    assert plan.calls[0].call.arguments == {"case_id": "owner-id"}
    assert plan.bindings == ()


def test_named_graph_rejects_host_argument_mutation_during_direct_probe():
    """The first route proof must not let a callback swap the later bound ID."""
    router = _router()
    router.add_tool(_node("direct", input_semantic="crm.case_id", identifier=True))
    index = NativeSchemaGraphIndex.build(
        NativeSchemaPostingIndex.build(router.registry),
        approved_host_roots=frozenset({"direct.read"}),
    )
    host_inputs = {"direct.read": {"case_id": "owner-id"}}

    def mutate_host_input(tool, endpoint):
        host_inputs["direct.read"]["case_id"] = "changed-after-source-probe"
        return True

    router.planner.availability_predicate = mutate_host_input
    with pytest.raises(PolicyViolationError, match="host|changed"):
        _compile(router, named_tools=("direct",), index=index,
                 host_source_arguments=host_inputs)


def test_named_one_hop_emits_original_typed_binding_not_model_parameters(monkeypatch):
    router = _router()
    monkeypatch.setattr(router, "execute", lambda *a, **kw: pytest.fail("executed"))
    plan = _compile(router, hints={"case_id": "model-forgery"})
    assert plan.status == "requires_observation"
    assert tuple(call.route_id for call in plan.calls) == (
        "root.read", "target_0.read",
    )
    # The value is an original named producer field, never a generated ID.
    assert plan.bindings == (PaperPlanBinding(1, "case_id", 0, "case_id"),)
    assert plan.calls[0].call.fields == ["case_id"]
    assert plan.calls[1].call.fields == ["status"]
    assert all(call.call.arguments == {} for call in plan.calls)
    assert plan.executable_authority is False


def test_named_two_hop_emits_two_source_typed_dependencies():
    router = _router(hops=2)
    plan = _compile(router)
    assert plan.status == "requires_observation"
    assert tuple(call.route_id for call in plan.calls) == (
        "root.read", "middle.read", "target_0.read",
    )
    assert [(edge.consumer_call_index, edge.parameter,
             edge.producer_call_index, edge.producer_field)
            for edge in plan.bindings] == [
        (1, "contact_id", 0, "contact_id"),
        (2, "case_id", 1, "case_id"),
    ]
    assert [c.call.fields for c in plan.calls] == [
        ["contact_id"], ["case_id"], ["status"],
    ]
    assert plan.calls[-1].fields_meta[0].semantic_id == "crm.status"
    assert plan.executable_authority is False


def test_explicit_named_sixth_target_survives_graph_fixed_k():
    router = _router(hops=2, n_targets=6)
    assert [call.route_id for call in _compile(
        router, named_tools=("target_5",),
    ).calls] == ["root.read", "middle.read", "target_5.read"]


@pytest.mark.parametrize("reason", [
    "unknown", "hidden", "denied", "wrong_type", "unsafe",
])
def test_named_graph_never_returns_unproved_or_unauthorized_path(reason):
    router = _router(
        hops=2, hidden_middle=reason == "hidden",
        deny_middle=reason == "denied",
        wrong_middle_type=reason == "wrong_type",
        unsafe_target=reason == "unsafe",
    )
    plan = _compile(router, named_tools=(
        "unregistered" if reason == "unknown" else "target_0",
    ))
    assert plan.status == "no_proven_hit"
    assert plan.calls == () and plan.bindings == ()
    assert "middle.read" not in repr(plan)


@pytest.mark.parametrize("hidden_mode", ["denied", "hidden_field"])
def test_hidden_many_endpoint_name_is_indistinguishable_from_unknown_name(hidden_mode):
    router = _router()
    router.add_tool(ToolSpec(
        name="secret", source_type="crm", license="reviewed",
        endpoints=[EndpointSpec(
            name=f"read_{i}", read_only=True,
            output_fields=[FieldSpec(
                name="status", semantic_id="crm.status",
                json_schema={"type": "string"},
            )],
        ) for i in range(33)],
    ))
    router.authorization_policy = AuthorizationPolicy(
        default_effect="deny",
        rules=(AuthorizationRule(
            effect="allow", operation="root.read", roles_any=("reader",),
        ),) + ((AuthorizationRule(
            effect="allow", operation="secret.*", roles_any=("reader",),
        ),) if hidden_mode == "hidden_field" else ()),
        data_rules=(DataScopeRule(
            operation="secret.*", roles_any=("reader",),
            hidden_fields=("status",),
        ),) if hidden_mode == "hidden_field" else (),
    )
    hidden = _compile(router, named_tools=("secret",))
    unknown = _compile(router, named_tools=("unregistered",))
    assert hidden.status == unknown.status == "no_proven_hit"
    assert hidden.calls == unknown.calls == ()


def test_unmentioned_target_retains_no_direct_proof_without_disclosing_graph():
    router = _router(hops=2)
    plan = _compile(router, named_tools=())
    # Without a model-named dependency, the existing direct compiler reports
    # the real required host argument; it does not discover joins implicitly.
    assert plan.status == "requires_arguments"
    assert [call.route_id for call in plan.calls] == ["target_0.read"]
    assert plan.bindings == ()


def test_one_hop_bound_does_not_accidentally_search_two_hop():
    plan = _compile(_router(hops=2), max_hops=1)
    assert plan.status == "no_proven_hit" and plan.calls == ()


def test_named_source_type_constraint_cannot_disclose_other_source_dependency():
    router = _router(hops=2)
    # The target still exactly matches the requested source; the graph root
    # has an incompatible provider source and must not leak into that plan.
    root = router.registry.get("root")
    foreign_root = root.model_copy(update={"source_type": "foreign"})
    router.registry.unregister("root")
    router.add_tool(foreign_root)
    plan = _compile(router, source_type="crm")
    assert plan.status == "no_proven_hit"
    assert plan.calls == () and plan.bindings == ()


def test_ambiguous_named_dependency_paths_do_not_form_false_combined_toolcall():
    router = _router(hops=2, n_targets=2)
    plan = _compile(router, named_tools=("target_0", "target_1"))
    assert plan.status == "ambiguous_paths"
    assert plan.calls == () and plan.bindings == ()


def test_source_availability_change_during_compilation_aborts(monkeypatch):
    import schemarouter.paper_understood_graph_plan as module

    router = _router(hops=2)
    index = NativeSchemaGraphIndex.build(NativeSchemaPostingIndex.build(router.registry))
    original = module._compile_one_route

    def revoke(*args, **kwargs):
        result = original(*args, **kwargs)
        router.planner.availability_predicate = lambda tool, endpoint: (
            tool.key != "middle"
        )
        return result

    monkeypatch.setattr(module, "_compile_one_route", revoke)
    with pytest.raises(PolicyViolationError, match="changed|eligibility"):
        _compile(router, index=index)


@pytest.mark.parametrize("hops", [1, 2])
def test_owner_rank_policy_selects_one_complete_g5_dependency_dag(hops):
    from schemarouter.paper_native_rank import PaperNativeRankPolicy

    router = _router(hops=hops, n_targets=2)
    index = NativeSchemaGraphIndex.build(
        NativeSchemaPostingIndex.build(router.registry),
    )
    rank_policy = PaperNativeRankPolicy(
        snapshot_id=index.field_index.snapshot_id,
        route_priorities={"target_1.read": 10},
    )

    plan = _compile(
        router, named_tools=("target_0", "target_1"), index=index,
        rank_policy=rank_policy,
    )

    expected = (
        ("root.read", "target_1.read")
        if hops == 1
        else ("root.read", "middle.read", "target_1.read")
    )
    assert plan.status == "requires_observation"
    assert tuple(call.route_id for call in plan.calls) == expected
    assert plan.ranked_unverified is True
    assert plan.executable_authority is False
    assert len({call.route_id for call in plan.calls}) == len(plan.calls)


def test_owner_rank_policy_mutation_during_g5_lookup_fails_closed():
    from schemarouter.paper_native_rank import PaperNativeRankPolicy

    router = _router(hops=2, n_targets=2)
    index = NativeSchemaGraphIndex.build(
        NativeSchemaPostingIndex.build(router.registry),
    )
    rank_policy = PaperNativeRankPolicy(snapshot_id=index.field_index.snapshot_id)

    def mutate_only_when_dependency_is_probed(tool, _endpoint):
        if tool.key == "root":
            rank_policy.route_priorities["target_1.read"] = 99
        return True

    router.planner.availability_predicate = mutate_only_when_dependency_is_probed
    with pytest.raises(PolicyViolationError, match="rank|owner|changed"):
        _compile(
            router, named_tools=("target_0", "target_1"), index=index,
            rank_policy=rank_policy,
        )


def test_owner_rank_filters_source_incompatible_upstream_before_selecting_top_path():
    from schemarouter.paper_native_rank import PaperNativeRankPolicy

    router = _router(hops=1, n_targets=2)
    foreign_root = _node(
        "aaa_foreign", output_semantic="crm.case_id", identifier=True,
    ).model_copy(update={"source_type": "foreign"})
    router.add_tool(foreign_root)
    index = NativeSchemaGraphIndex.build(
        NativeSchemaPostingIndex.build(router.registry),
    )
    rank_policy = PaperNativeRankPolicy(
        snapshot_id=index.field_index.snapshot_id,
        route_priorities={"target_0.read": 10},
    )

    plan = _compile(
        router, named_tools=("target_0", "target_1"), source_type="crm",
        index=index, rank_policy=rank_policy,
    )

    assert plan.status == "requires_observation"
    assert tuple(call.route_id for call in plan.calls) == (
        "root.read", "target_0.read",
    )
    assert plan.ranked_unverified is True


def test_owner_ranked_two_hop_graph_exceeds_legacy_research_32_path_cap():
    from schemarouter import NativeDeclaredFieldGroup
    from schemarouter.paper_native_rank import PaperNativeRankPolicy

    router = _router(hops=2, n_targets=33)
    index = NativeSchemaGraphIndex.build(
        NativeSchemaPostingIndex.build(router.registry),
    )
    group = NativeDeclaredFieldGroup(
        aliases=("case status",),
        required_fields=CATALOG.concepts[0].required_fields,
        source_type="crm", license="reviewed",
    )
    policy = PaperNativeRankPolicy(
        snapshot_id=index.field_index.snapshot_id,
        route_priorities={"target_32.read": 100},
    )

    with pytest.raises(PolicyViolationError, match="source eligibility changed"):
        index.lookup_two_hop(
            router, "case status", group=group, principal=ACTOR,
        )
    ranked = index.lookup_two_hop(
        router, "case status", group=group, principal=ACTOR,
        _paper_rank_policy=policy,
        _paper_rank_aliases=(("case status",),),
    )
    assert ranked.status == "ranked_unverified"
    assert ranked.qualified_path_count == 33
    assert ranked.deterministic_paper_ranked
    assert len(ranked.candidates) == 5
    assert ranked.candidates[0].route_ids == (
        "root.read", "middle.read", "target_32.read",
    )
    assert not ranked.executable_authority


def test_public_prepared_session_uses_owner_rank_for_full_named_graph():
    from schemarouter.paper_native_rank import PaperNativeRankPolicy

    router = _router(hops=2, n_targets=2)
    session = router.prepare_field_routing(catalog=CATALOG)
    rank_policy = PaperNativeRankPolicy(
        snapshot_id=session.snapshot_id,
        route_priorities={"target_1.read": 100},
    )
    result = session.compile_understood(
        PaperUnderstanding(
            intent_id="case.lookup",
            named_tools=("target_0", "target_1"),
        ),
        principal=ACTOR,
        intent_registry=INTENTS,
        rank_policy=rank_policy,
    )
    assert result.status == "requires_observation"
    assert tuple(call.route_id for call in result.calls) == (
        "root.read", "middle.read", "target_1.read",
    )
    assert result.ranked_unverified
    assert result.executable_authority is False
    assert len(result.bindings) == 2


@pytest.mark.parametrize("hops", [1, 2])
def test_host_opt_in_discovers_unnamed_source_proven_dependency(hops):
    from schemarouter.paper_native_rank import PaperNativeRankPolicy

    router = _router(hops=hops, n_targets=6)
    index = NativeSchemaGraphIndex.build(
        NativeSchemaPostingIndex.build(router.registry),
    )
    policy = PaperNativeRankPolicy(
        snapshot_id=index.field_index.snapshot_id,
        route_priorities={"target_5.read": 10},
    )
    traditional = _compile(router, index=index, named_tools=(), rank_policy=policy)
    assert traditional.status == "requires_arguments"
    assert traditional.bindings == ()

    ranked = _compile(
        router, index=index, named_tools=(), rank_policy=policy,
        allow_unnamed_graph_discovery=True,
    )
    assert ranked.status == "requires_observation"
    assert tuple(call.route_id for call in ranked.calls) == (
        ("root.read", "target_5.read") if hops == 1
        else ("root.read", "middle.read", "target_5.read")
    )
    assert len(ranked.bindings) == hops
    assert ranked.ranked_unverified is True
    assert ranked.executable_authority is False


def test_host_opt_in_unnamed_graph_reaches_targets_beyond_model_five_name_limit():
    from schemarouter.paper_native_rank import PaperNativeRankPolicy

    router = _router(hops=1, n_targets=33)
    index = NativeSchemaGraphIndex.build(
        NativeSchemaPostingIndex.build(router.registry),
    )
    policy = PaperNativeRankPolicy(
        snapshot_id=index.field_index.snapshot_id,
        route_priorities={"target_32.read": 100},
    )
    plan = _compile(
        router, index=index, named_tools=(), rank_policy=policy,
        allow_unnamed_graph_discovery=True,
    )
    assert tuple(call.route_id for call in plan.calls) == (
        "root.read", "target_32.read",
    )
    assert plan.ranked_unverified and not plan.executable_authority


def test_unnamed_graph_discovery_requires_host_approval_and_current_owner_rank():
    from schemarouter.paper_native_rank import PaperNativeRankPolicy

    router = _router()
    index = NativeSchemaGraphIndex.build(
        NativeSchemaPostingIndex.build(router.registry),
    )
    with pytest.raises(ValueError, match="rank|owner|approved"):
        _compile(
            router, index=index, named_tools=(),
            allow_unnamed_graph_discovery=True,
        )
    stale = PaperNativeRankPolicy(snapshot_id="0" * 64)
    with pytest.raises(PolicyViolationError, match="source|snapshot|rank"):
        _compile(
            router, index=index, named_tools=(), rank_policy=stale,
            allow_unnamed_graph_discovery=True,
        )


def test_unnamed_graph_discovery_does_not_resurrect_hidden_or_denied_root():
    from schemarouter.paper_native_rank import PaperNativeRankPolicy

    for hidden in (True, False):
        router = _router(hops=2, hidden_middle=hidden, deny_middle=not hidden)
        index = NativeSchemaGraphIndex.build(
            NativeSchemaPostingIndex.build(router.registry),
        )
        policy = PaperNativeRankPolicy(snapshot_id=index.field_index.snapshot_id)
        plan = _compile(
            router, index=index, named_tools=(), rank_policy=policy,
            allow_unnamed_graph_discovery=True,
        )
        # An incomplete direct shape remains available; no unauthorized
        # graph path or hidden middle route may appear.
        assert plan.status == "requires_arguments"
        assert tuple(c.route_id for c in plan.calls) == ("target_0.read",)
        assert plan.bindings == ()
        assert "middle.read" not in repr(plan)


def test_unnamed_graph_direct_fallback_does_not_survive_live_health_revocation():
    from schemarouter.paper_native_rank import PaperNativeRankPolicy

    router = _router(hops=2)
    index = NativeSchemaGraphIndex.build(
        NativeSchemaPostingIndex.build(router.registry),
    )
    policy = PaperNativeRankPolicy(snapshot_id=index.field_index.snapshot_id)
    health = {"target": True}
    secret = "PRIVATE_AVAILABILITY_REASON_abc"

    def availability(tool, _endpoint):
        if tool.key == "middle":
            health["target"] = False
        if tool.key == "target_0":
            return health["target"]
        return True

    router.planner.availability_predicate = availability
    with pytest.raises(PolicyViolationError, match="changed|eligibility|source") as err:
        _compile(
            router, index=index, named_tools=(), rank_policy=policy,
            allow_unnamed_graph_discovery=True,
        )
    assert secret not in str(err.value)


def test_unnamed_graph_discovery_never_discards_unproved_host_root_arguments():
    from schemarouter.paper_native_rank import PaperNativeRankPolicy

    router = _router(hops=2, hidden_middle=True)
    index = NativeSchemaGraphIndex.build(
        NativeSchemaPostingIndex.build(router.registry),
    )
    policy = PaperNativeRankPolicy(snapshot_id=index.field_index.snapshot_id)
    unproved_inputs = {"root.read": {"case_id": "HOST"}}
    plan = _compile(
        router, index=index, named_tools=(), rank_policy=policy,
        host_source_arguments=unproved_inputs,
        allow_unnamed_graph_discovery=True,
    )
    assert plan.status == "no_proven_hit"
    assert plan.calls == () and plan.bindings == ()


@pytest.mark.parametrize("n_targets", [500, 5000])
def test_host_unnamed_g5_public_planner_selects_exact_k5_from_large_catalog(n_targets):
    from schemarouter.paper_native_rank import PaperNativeRankPolicy

    router = _router(hops=1, n_targets=n_targets)
    index = NativeSchemaGraphIndex.build(
        NativeSchemaPostingIndex.build(router.registry),
    )
    winning_target = f"target_{n_targets - 1}.read"
    policy = PaperNativeRankPolicy(
        snapshot_id=index.field_index.snapshot_id,
        route_priorities={winning_target: 100},
    )
    plan = _compile(
        router, index=index, named_tools=(), rank_policy=policy,
        allow_unnamed_graph_discovery=True,
    )
    assert plan.status == "requires_observation"
    assert tuple(c.route_id for c in plan.calls) == (
        "root.read", winning_target,
    )
    assert plan.ranked_unverified is True
    assert not plan.executable_authority
    assert len(plan.bindings) == 1


def _mixed_depth_router():
    """Source-native graph: target_short has one hop, target_long two."""
    router = SchemaRouter(authorization_policy=AuthorizationPolicy(
        default_effect="deny",
        rules=(AuthorizationRule(
            effect="allow", operation="*.read", roles_any=("reader",),
        ),),
    ))
    router.add_tool(_node(
        "root_short", output_semantic="crm.case_id", identifier=True,
    ))
    router.add_tool(_node(
        "root_long", output_semantic="crm.contact_id", identifier=True,
    ))
    router.add_tool(_node(
        "middle_long", input_semantic="crm.contact_id",
        output_semantic="crm.account_id", identifier=True,
    ))
    router.add_tool(_node("target_short", input_semantic="crm.case_id"))
    router.add_tool(_node("target_long", input_semantic="crm.account_id"))
    return router


def test_cross_depth_owner_rank_prefers_stronger_two_hop_target_over_valid_one_hop():
    from schemarouter.paper_native_rank import PaperNativeRankPolicy

    router = _mixed_depth_router()
    index = NativeSchemaGraphIndex.build(
        NativeSchemaPostingIndex.build(router.registry),
    )
    policy = PaperNativeRankPolicy(
        snapshot_id=index.field_index.snapshot_id,
        route_priorities={"target_long.read": 90},
    )
    named = ("target_short", "target_long")
    legacy = _compile(router, index=index, named_tools=named)
    assert legacy.status == "requires_observation"
    assert tuple(c.route_id for c in legacy.calls) == (
        "root_short.read", "target_short.read",
    )
    ranked = _compile(router, index=index, named_tools=named, rank_policy=policy)
    assert ranked.status == "requires_observation"
    assert tuple(c.route_id for c in ranked.calls) == (
        "root_long.read", "middle_long.read", "target_long.read",
    )
    assert len(ranked.bindings) == 2
    assert ranked.ranked_unverified
    assert ranked.executable_authority is False


def test_cross_depth_unnamed_owner_rank_uses_same_full_dag_order():
    from schemarouter.paper_native_rank import PaperNativeRankPolicy

    router = _mixed_depth_router()
    index = NativeSchemaGraphIndex.build(
        NativeSchemaPostingIndex.build(router.registry),
    )
    policy = PaperNativeRankPolicy(
        snapshot_id=index.field_index.snapshot_id,
        route_priorities={"target_long.read": 90},
    )
    ranked = _compile(
        router, index=index, named_tools=(), rank_policy=policy,
        allow_unnamed_graph_discovery=True,
    )
    assert tuple(c.route_id for c in ranked.calls) == (
        "root_long.read", "middle_long.read", "target_long.read",
    )
    assert ranked.ranked_unverified and not ranked.executable_authority


def test_cross_depth_rank_tie_uses_shorter_complete_path_as_tiebreaker():
    from schemarouter.paper_native_rank import PaperNativeRankPolicy

    router = _mixed_depth_router()
    index = NativeSchemaGraphIndex.build(
        NativeSchemaPostingIndex.build(router.registry),
    )
    policy = PaperNativeRankPolicy(snapshot_id=index.field_index.snapshot_id)
    ranked = _compile(
        router, index=index, named_tools=("target_short", "target_long"),
        rank_policy=policy,
    )
    assert tuple(c.route_id for c in ranked.calls) == (
        "root_short.read", "target_short.read",
    )


def test_cross_depth_rank_web_demotion_overrides_long_target_priority():
    from schemarouter.paper_native_rank import PaperNativeRankPolicy

    router = _mixed_depth_router()
    index = NativeSchemaGraphIndex.build(
        NativeSchemaPostingIndex.build(router.registry),
    )
    policy = PaperNativeRankPolicy(
        snapshot_id=index.field_index.snapshot_id,
        route_priorities={"target_long.read": 100},
        web_route_ids=("middle_long.read",),
    )
    ranked = _compile(
        router, index=index, named_tools=("target_short", "target_long"),
        rank_policy=policy,
    )
    assert tuple(c.route_id for c in ranked.calls) == (
        "root_short.read", "target_short.read",
    )


def test_cross_depth_rank_obeys_explicit_single_hop_cap():
    from schemarouter.paper_native_rank import PaperNativeRankPolicy

    router = _mixed_depth_router()
    index = NativeSchemaGraphIndex.build(
        NativeSchemaPostingIndex.build(router.registry),
    )
    policy = PaperNativeRankPolicy(
        snapshot_id=index.field_index.snapshot_id,
        route_priorities={"target_long.read": 100},
    )
    plan = _compile(
        router, index=index, named_tools=("target_short", "target_long"),
        rank_policy=policy, max_hops=1,
    )
    assert tuple(c.route_id for c in plan.calls) == (
        "root_short.read", "target_short.read",
    )
