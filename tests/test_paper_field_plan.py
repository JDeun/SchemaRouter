"""#1560: P1 original-paper field proof -> nonexecuting native ToolCall recipe."""
from __future__ import annotations

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
    NativeSchemaGraphIndex,
    NativeSchemaPostingIndex,
    ParameterSpec,
    SchemaRouter,
    ToolCall,
    ToolSpec,
    compile_paper_field_toolcalls,
)
from schemarouter.errors import PolicyViolationError
from schemarouter.paper_field_retrieval import retrieve_paper_field_coverage
from scripts.benchmark_native_fork_fieldgroup_e0 import (
    ACTOR,
    ALIASES,
    GROUP,
    LEFT,
    RIGHT,
    ROOT,
    build_fixture,
)


def _index(router):
    return NativeSchemaGraphIndex.build(NativeSchemaPostingIndex.build(router.registry))


def _fork_catalog():
    return NativeConceptCatalog(concepts=(NativeDeclaredConcept(
        concept_id="crm.customer_fields", aliases=ALIASES,
        required_fields=GROUP.required_fields,
        source_type=GROUP.source_type, license=GROUP.license,
    ),))


def _direct_fixture():
    router = SchemaRouter(authorization_policy=AuthorizationPolicy(
        default_effect="deny", rules=(AuthorizationRule(
            effect="allow", operation="*.read", roles_any=("reader",),
        ),),
    ))
    router.add_tool(ToolSpec(
        name="complete", source_type="crm", license="host-reviewed-synthetic",
        endpoints=[EndpointSpec(name="read", read_only=True, output_fields=[
            FieldSpec(name="status", semantic_id="crm.fork_status",
                      json_schema={"type": "string"}),
            FieldSpec(name="owner", semantic_id="crm.fork_owner",
                      json_schema={"type": "string"}),
            FieldSpec(name="request_id", semantic_id="crm.request_id",
                      json_schema={"type": "string"}, identifier=True),
            FieldSpec(name="private_excess", semantic_id="crm.extra",
                      json_schema={"type": "string"}),
        ])],
    ))
    return router


def test_compiled_direct_reuses_exact_scoped_field_projection():
    router = _direct_fixture()
    router.authorization_policy = AuthorizationPolicy(
        default_effect="deny",
        rules=(AuthorizationRule(
            effect="allow", operation="*.read", roles_any=("reader",),
        ),),
        data_rules=(DataScopeRule(
            operation="complete.read", roles_any=("reader",),
            hidden_fields=("private_excess",),
        ),),
    )
    index = _index(router)
    before = router.retrieve_authorized(ALIASES[0], principal=ACTOR, k=5)
    plan = compile_paper_field_toolcalls(
        router, ALIASES[0], principal=ACTOR, catalog=_fork_catalog(), index=index,
    )
    assert plan.status == "complete"
    assert not plan.executable_authority
    assert not plan.independent_quality_evidence
    assert len(plan.alternatives) == 1
    alternative = plan.alternatives[0]
    assert alternative.dependencies == ()
    assert set(alternative.required_semantic_ids) == {
        "crm.fork_status", "crm.fork_owner",
    }
    assert len(alternative.calls) == 1
    call = alternative.calls[0]
    assert isinstance(call, ToolCall)
    assert (call.tool, call.endpoint) == ("complete", "read")
    assert call.fields == ["status", "owner", "request_id"]
    assert call.arguments == {}
    assert call.missing_required_arguments == []
    assert call.tool_fingerprint == router.registry.get("complete").fingerprint
    assert call.schema_fingerprint == router.registry.get("complete").endpoint("read").fingerprint
    assert router.retrieve_authorized(ALIASES[0], principal=ACTOR, k=5) == before


def test_compiler_never_republishes_hidden_shared_root_identifier():
    router = build_fixture(500)
    router.authorization_policy = AuthorizationPolicy(
        default_effect="deny",
        rules=(AuthorizationRule(
            effect="allow", operation="*.*", roles_any=("reader",),
        ),),
        data_rules=(DataScopeRule(
            operation="fork_origin.read", roles_any=("reader",),
            hidden_fields=("customer_id",),
        ),),
    )
    plan = compile_paper_field_toolcalls(
        router, ALIASES[0], principal=ACTOR,
        catalog=_fork_catalog(), index=_index(router),
    )
    assert plan.status == "no_proven_hit"
    assert plan.alternatives == ()
    assert "customer_id" not in str(plan)


def test_host_approved_parameterized_root_is_a_nonexecutable_recipe():
    router = SchemaRouter(authorization_policy=AuthorizationPolicy(
        default_effect="deny",
        rules=(AuthorizationRule(
            effect="allow", operation="*.*", roles_any=("reader",),
        ),),
    ))
    router.add_tool(ToolSpec(
        name="posts", source_type="crm", license="host-reviewed-synthetic",
        endpoints=[EndpointSpec(
            name="by_id", read_only=True,
            parameters=[ParameterSpec(
                name="post_id", required=True, json_schema={"type": "integer"},
            )],
            input_schema={"type": "object",
                          "properties": {"post_id": {"type": "integer"}},
                          "required": ["post_id"]},
            output_fields=[FieldSpec(
                name="userId", identifier=True,
                semantic_id="crm.user_id", json_schema={"type": "integer"},
            )],
        )],
    ))
    router.add_tool(ToolSpec(
        name="users", source_type="crm", license="host-reviewed-synthetic",
        endpoints=[EndpointSpec(
            name="by_id", read_only=True,
            parameters=[ParameterSpec(
                name="user_id", required=True, semantic_id="crm.user_id",
                json_schema={"type": "integer"},
            )],
            input_schema={"type": "object",
                          "properties": {"user_id": {"type": "integer"}},
                          "required": ["user_id"]},
            output_fields=[FieldSpec(
                name="username", semantic_id="crm.username",
                json_schema={"type": "string"},
            )],
        )],
    ))
    catalog = NativeConceptCatalog(concepts=(NativeDeclaredConcept(
        concept_id="crm.user_name", aliases=("lookup username",),
        required_fields=(CapabilityFieldContract(
            semantic_id="crm.username", json_schema={"type": "string"},
        ),),
        source_type="crm", license="host-reviewed-synthetic",
    ),))
    index = NativeSchemaGraphIndex.build(
        NativeSchemaPostingIndex.build(router.registry),
        approved_host_roots=frozenset({"posts.by_id"}),
    )
    assert retrieve_paper_field_coverage(
        router, "lookup username", principal=ACTOR,
        catalog=catalog, index=index,
    ).status == "complete"
    plan = compile_paper_field_toolcalls(
        router, "lookup username", principal=ACTOR,
        catalog=catalog, index=index,
    )
    assert plan.status == "complete"
    alternative = plan.alternatives[0]
    assert [(call.tool, call.endpoint) for call in alternative.calls] == [
        ("posts", "by_id"), ("users", "by_id"),
    ]
    assert [call.arguments for call in alternative.calls] == [{}, {}]
    assert [call.missing_required_arguments for call in alternative.calls] == [
        ["post_id"], ["user_id"],
    ]
    assert not any(call.executable for call in alternative.calls)
    assert len(alternative.dependencies) == 1
    assert alternative.dependencies[0].producer_field == "userId"
    assert not plan.executable_authority


@pytest.mark.parametrize("query", ALIASES)
def test_compiled_fork_unbound_arguments_remain_nonexecutable(query):
    router = build_fixture(500)
    plan = compile_paper_field_toolcalls(
        router, query, principal=ACTOR, catalog=_fork_catalog(), index=_index(router),
    )
    assert plan.status == "complete"
    assert len(plan.alternatives) == 1
    alternative = plan.alternatives[0]
    route_ids = [f"{call.tool}.{call.endpoint}" for call in alternative.calls]
    assert route_ids[0] == ROOT
    assert set(route_ids[1:]) == {LEFT, RIGHT}
    assert {
        f"{call.tool}.{call.endpoint}": call.fields
        for call in alternative.calls
    } == {ROOT: ["customer_id"], LEFT: ["status"], RIGHT: ["owner"]}
    assert all(call.arguments == {} for call in alternative.calls)
    assert alternative.calls[0].executable
    assert not alternative.calls[1].executable
    assert not alternative.calls[2].executable
    assert alternative.calls[1].missing_required_arguments == ["customer_id"]
    assert alternative.calls[2].missing_required_arguments == ["customer_id"]
    assert {(
        route_ids[dep.consumer_call_index], dep.parameter,
        route_ids[dep.producer_call_index], dep.producer_field,
    ) for dep in alternative.dependencies} == {
        (LEFT, "customer_id", ROOT, "customer_id"),
        (RIGHT, "customer_id", ROOT, "customer_id"),
    }
    assert not plan.executable_authority


def test_compiler_preserves_no_proven_hit_or_over_k():
    router = build_fixture(500, mixed_scope=True)
    index = _index(router)
    router.planner.availability_predicate = lambda tool, ep: tool.key != "fork_owner"
    missing = compile_paper_field_toolcalls(
        router, ALIASES[0], principal=ACTOR, catalog=_fork_catalog(), index=index,
    )
    assert missing.status == "no_proven_hit"
    assert missing.alternatives == ()

    all_complete = _direct_fixture()
    source_fields = all_complete.registry.get("complete").endpoint("read").output_fields
    for n in range(5):
        all_complete.add_tool(ToolSpec(
            name=f"additional_{n}", source_type="crm",
            license="host-reviewed-synthetic",
            endpoints=[EndpointSpec(
                name="read", read_only=True,
                output_fields=[field.model_copy(deep=True) for field in source_fields],
            )],
        ))
    overflow = compile_paper_field_toolcalls(
        all_complete, ALIASES[0], principal=ACTOR,
        catalog=_fork_catalog(), index=_index(all_complete),
    )
    assert overflow.status == "over_k_unranked"
    assert overflow.alternatives == ()


def test_compiled_fork_uses_original_5000_route_index_without_rescanning_or_guessing():
    router = build_fixture(5000)
    plan = compile_paper_field_toolcalls(
        router, ALIASES[0], principal=ACTOR, catalog=_fork_catalog(),
        index=_index(router),
    )
    assert plan.status == "complete"
    assert len(plan.alternatives) == 1
    assert len(plan.alternatives[0].calls) == 3
    assert len(plan.alternatives[0].dependencies) == 2
    assert not plan.executable_authority


def test_compiler_rejects_unproved_or_changed_dependency(monkeypatch):
    router = build_fixture(500)
    index = _index(router)
    authentic = retrieve_paper_field_coverage(
        router, ALIASES[0], principal=ACTOR, catalog=_fork_catalog(), index=index,
    )
    alternative = authentic.alternatives[0]
    leaf = alternative.routes[1]
    forgery = replace(authentic, alternatives=(replace(
        alternative, routes=(alternative.routes[0], replace(
            leaf, input_bindings=(("customer_id", RIGHT, "owner"),),
        ), alternative.routes[2]),
    ),))
    import schemarouter.paper_field_plan as module

    first = True

    def forged_once(*args, **kwargs):
        nonlocal first
        if first:
            first = False
            return forgery
        return retrieve_paper_field_coverage(*args, **kwargs)

    monkeypatch.setattr(module, "retrieve_paper_field_coverage", forged_once)
    with pytest.raises(PolicyViolationError):
        compile_paper_field_toolcalls(
            router, ALIASES[0], principal=ACTOR, catalog=_fork_catalog(), index=index,
        )


def test_compiler_rejects_mid_projection_source_revocation(monkeypatch):
    router = build_fixture(500)
    index = _index(router)
    import schemarouter.paper_field_plan as module

    original = retrieve_paper_field_coverage
    published = False

    def revoke_after_p1(*args, **kwargs):
        nonlocal published
        result = original(*args, **kwargs)
        if not published:
            published = True
            router.planner.availability_predicate = (
                lambda tool, _ep: tool.key != "fork_origin"
            )
        return result

    monkeypatch.setattr(module, "retrieve_paper_field_coverage", revoke_after_p1)
    with pytest.raises(PolicyViolationError):
        compile_paper_field_toolcalls(
            router, ALIASES[0], principal=ACTOR, catalog=_fork_catalog(), index=index,
        )
    assert published


@pytest.mark.parametrize("mutation", ["catalog", "policy"])
def test_compiler_catches_owner_declaration_or_policy_change_after_first_proof(
    monkeypatch, mutation,
):
    router = _direct_fixture()
    index = _index(router)
    catalog = _fork_catalog()
    import schemarouter.paper_field_plan as module

    first = True

    def late_mutation(*args, **kwargs):
        nonlocal first
        result = retrieve_paper_field_coverage(*args, **kwargs)
        if first:
            first = False
            if mutation == "catalog":
                concept = catalog.concepts[0]
                concept.aliases += ("reviewed-but-not-current-query",)
            else:
                previous = router.authorization_policy
                router.authorization_policy = AuthorizationPolicy(
                    default_effect="deny", rules=(*previous.rules, AuthorizationRule(
                        effect="allow", operation="unrelated.read",
                        roles_any=("admin",),
                    )),
                )
        return result

    monkeypatch.setattr(module, "retrieve_paper_field_coverage", late_mutation)
    with pytest.raises(PolicyViolationError):
        compile_paper_field_toolcalls(
            router, ALIASES[0], principal=ACTOR, catalog=catalog, index=index,
        )
    assert not first
