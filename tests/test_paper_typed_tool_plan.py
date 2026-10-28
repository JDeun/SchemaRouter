"""#1560: Algorithm 1 field proof -> non-executing typed ToolCall receipt."""
from __future__ import annotations

import pytest

from schemarouter import (
    AuthorizationPolicy,
    AuthorizationRule,
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
)
from schemarouter.errors import PolicyViolationError
from schemarouter.paper_typed_tool_plan import compile_paper_typed_tool_plan
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


def _catalog():
    return NativeConceptCatalog(concepts=(NativeDeclaredConcept(
        concept_id="crm.customer_fields", aliases=ALIASES,
        required_fields=GROUP.required_fields,
        source_type=GROUP.source_type, license=GROUP.license,
    ),))


def _single_source():
    router = SchemaRouter(authorization_policy=AuthorizationPolicy(
        default_effect="deny", rules=(AuthorizationRule(
            effect="allow", operation="*.read", roles_any=("reader",),
        ),),
    ))
    router.add_tool(ToolSpec(
        name="complete", source_type="crm", license="host-reviewed-synthetic",
        endpoints=[EndpointSpec(name="read", read_only=True, output_fields=[
            FieldSpec(name="status", semantic_id="crm.fork_status",
                      json_schema={"type": "string"}, unit=None),
            FieldSpec(name="owner", semantic_id="crm.fork_owner",
                      json_schema={"type": "string"}),
            FieldSpec(name="request_id", semantic_id="crm.request_id",
                      json_schema={"type": "string"}, identifier=True),
            FieldSpec(name="hidden_extra", semantic_id="crm.extra",
                      json_schema={"type": "string"}),
        ])],
    ))
    return router


def test_direct_compiles_exact_original_typed_toolcall_without_executing(monkeypatch):
    router = _single_source()
    monkeypatch.setattr(router, "execute", lambda *a, **k: pytest.fail("executed"))
    plan = compile_paper_typed_tool_plan(
        router, ALIASES[0], principal=ACTOR, catalog=_catalog(), index=_index(router),
    )
    assert plan.status == "ready"
    assert plan.executable_authority is False
    assert plan.bindings == ()
    assert len(plan.calls) == 1
    item = plan.calls[0]
    assert item.route_id == "complete.read"
    assert isinstance(item.call, ToolCall)
    assert item.call.tool == "complete" and item.call.endpoint == "read"
    assert item.call.arguments == {} and item.call.missing_required_arguments == []
    assert item.call.fields == ["status", "owner", "request_id"]
    assert item.call.schema_fingerprint == (
        router.registry.get("complete").endpoint("read").fingerprint
    )
    assert item.call.tool_fingerprint == router.registry.get("complete").fingerprint
    assert item.source_type == "crm" and item.license == "host-reviewed-synthetic"
    assert {field.name for field in item.fields_meta} == set(item.call.fields)
    assert "hidden_extra" not in repr(plan)


def test_fork_compiles_deferred_typed_calls_and_original_identifier_edges(monkeypatch):
    router = build_fixture(500, mixed_scope=True)
    monkeypatch.setattr(router, "execute", lambda *a, **k: pytest.fail("executed"))
    plan = compile_paper_typed_tool_plan(
        router, ALIASES[1], principal=ACTOR, catalog=_catalog(), index=_index(router),
    )
    assert plan.status == "requires_observation"
    assert plan.executable_authority is False
    assert plan.calls[0].route_id == ROOT
    assert {entry.route_id for entry in plan.calls[1:]} == {LEFT, RIGHT}
    assert all(isinstance(entry.call, ToolCall) for entry in plan.calls)
    assert plan.calls[0].call.fields == ["customer_id"]
    assert plan.calls[0].call.arguments == {}
    for leaf in plan.calls[1:]:
        selected = "status" if leaf.route_id == LEFT else "owner"
        assert leaf.call.fields == [selected]
        assert leaf.call.arguments == {}
        assert leaf.call.missing_required_arguments == ["customer_id"]
        assert leaf.call.executable is False
    assert {
        (edge.consumer_call_index, edge.parameter,
         edge.producer_call_index, edge.producer_field)
        for edge in plan.bindings
    } == {(1, "customer_id", 0, "customer_id"),
          (2, "customer_id", 0, "customer_id")}
    assert "fork_owner_hidden" not in repr(plan)


def test_missing_leaf_abstains_without_partial_typed_calls():
    router = build_fixture(500)
    router.planner.availability_predicate = lambda t, e: t.key != "fork_owner"
    plan = compile_paper_typed_tool_plan(
        router, ALIASES[0], principal=ACTOR, catalog=_catalog(), index=_index(router),
    )
    assert plan.status == "no_proven_hit"
    assert plan.calls == () and plan.bindings == ()


@pytest.mark.parametrize("k", [0, 4, 6, True, 5.0])
def test_compiler_preserves_exact_k5(k):
    router = _single_source()
    with pytest.raises(ValueError, match="exact K5"):
        compile_paper_typed_tool_plan(
            router, ALIASES[0], principal=ACTOR, catalog=_catalog(),
            index=_index(router), k=k,
        )


@pytest.mark.parametrize("choice", [-1, 1, True, 0.0])
def test_out_of_range_alternative_fails_closed(choice):
    router = _single_source()
    with pytest.raises(ValueError, match="alternative index"):
        compile_paper_typed_tool_plan(
            router, ALIASES[0], principal=ACTOR, catalog=_catalog(),
            index=_index(router), alternative_index=choice,
        )


def test_registry_change_does_not_compile_stale_call():
    router = build_fixture(500)
    index = _index(router)
    router.add_tool(ToolSpec(name="late", endpoints=[EndpointSpec(
        name="read", read_only=True,
    )]))
    with pytest.raises(PolicyViolationError):
        compile_paper_typed_tool_plan(
            router, ALIASES[0], principal=ACTOR, catalog=_catalog(), index=index,
        )


def test_direct_required_argument_without_host_proof_abstains():
    router = _single_source()
    tool = router.registry.get("complete")
    tool.endpoint("read").parameters.append(
        ParameterSpec(name="customer_id", semantic_id="crm.request_id",
                      required=True, json_schema={"type": "string"}),
    )
    router.add_tool(tool, replace=True)
    # Build a fresh original index for the revised declared source surface.
    plan = compile_paper_typed_tool_plan(
        router, ALIASES[0], principal=ACTOR, catalog=_catalog(), index=_index(router),
    )
    assert plan.status == "no_proven_hit"
    assert plan.calls == ()


def test_mid_compile_revocation_suppresses_stale_typed_call(monkeypatch):
    import schemarouter.paper_typed_tool_plan as compiler

    router = build_fixture(500)
    index = _index(router)
    original = compiler.retrieve_paper_field_coverage
    call_count = 0

    def revoke_before_final_proof(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            router.planner.availability_predicate = (
                lambda tool, ep: tool.key != "fork_owner"
            )
        return original(*args, **kwargs)

    monkeypatch.setattr(compiler, "retrieve_paper_field_coverage", revoke_before_final_proof)
    with pytest.raises(PolicyViolationError, match="source eligibility changed"):
        compile_paper_typed_tool_plan(
            router, ALIASES[0], principal=ACTOR, catalog=_catalog(), index=index,
        )
    assert call_count == 2
