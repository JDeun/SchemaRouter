"""#1773: only safe, currently visible input shapes leave original P2 plans."""
from __future__ import annotations

import pytest

from schemarouter import (
    AuthorizationPolicy,
    AuthorizationRule,
    DataScopeRule,
    NativeConceptCatalog,
    NativeDeclaredConcept,
    NativeSchemaGraphIndex,
    NativeSchemaPostingIndex,
    ParameterSpec,
    SchemaRouter,
)
from schemarouter.errors import PolicyViolationError
from schemarouter.paper_typed_tool_plan import (
    _check_current_call_scopes,
    compile_paper_typed_tool_plan,
)
from scripts.benchmark_native_fork_fieldgroup_e0 import (
    ACTOR,
    ALIASES,
    GROUP,
    LEFT,
    RIGHT,
    ROOT,
    build_fixture,
)


def _catalog():
    return NativeConceptCatalog(concepts=(NativeDeclaredConcept(
        concept_id="crm.customer_fields", aliases=ALIASES,
        required_fields=GROUP.required_fields,
        source_type=GROUP.source_type, license=GROUP.license,
    ),))


def _index(router):
    return NativeSchemaGraphIndex.build(
        NativeSchemaPostingIndex.build(router.registry),
    )


def test_paper_plan_exposes_required_typed_original_consumer_parameters():
    router = build_fixture(500)
    plan = compile_paper_typed_tool_plan(
        router, ALIASES[0], principal=ACTOR, catalog=_catalog(),
        index=_index(router),
    )
    assert plan.status == "requires_observation"
    assert plan.executable_authority is False
    by_route = {call.route_id: call for call in plan.calls}
    assert by_route[ROOT].parameters_meta == ()
    for route_id in (LEFT, RIGHT):
        params = by_route[route_id].parameters_meta
        assert len(params) == 1
        assert (
            params[0].name, params[0].required,
            params[0].location, params[0].json_types,
        ) == ("customer_id", True, "argument", ("string",))


def test_prepared_schema_session_wires_typed_parameter_metadata():
    router = build_fixture(500)
    session = router.prepare_field_routing(catalog=_catalog())
    plan = session.compile(ALIASES[1], principal=ACTOR)
    assert plan.status == "requires_observation"
    assert {item.route_id: tuple(p.name for p in item.parameters_meta)
            for item in plan.calls} == {
        ROOT: (), LEFT: ("customer_id",), RIGHT: ("customer_id",),
    }


def test_private_wire_descriptions_and_unselected_fields_never_enter_parameter_receipt():
    secret = "private_column_aba9_do_not_expose"
    router = build_fixture(500)
    leaf = router.registry.get("fork_owner")
    param = leaf.endpoints[0].parameters[0]
    param.description = f"Internal join: {secret}"
    param.wire_name = f"X-{secret}"
    param.aliases = [secret]
    leaf.endpoints[0].output_fields.append(
        type(leaf.endpoints[0].output_fields[0])(
            name=secret, json_schema={"type": "string"},
        ),
    )
    router.add_tool(leaf, replace=True)
    router.authorization_policy = AuthorizationPolicy(
        default_effect="deny",
        rules=(AuthorizationRule(
            effect="allow", operation="*.read", roles_any=("reader",),
        ),),
        data_rules=(DataScopeRule(
            operation="unrelated.read", roles_any=("reader",),
            visible_fields=("owner",),
        ),),
    )

    plan = router.prepare_field_routing(catalog=_catalog()).compile(
        ALIASES[0], principal=ACTOR,
    )
    assert plan.status == "requires_observation"
    assert secret not in repr(plan)
    selected = next(item for item in plan.calls if item.route_id == RIGHT)
    assert len(selected.parameters_meta) == 1
    assert selected.parameters_meta[0].name == "customer_id"
    assert selected.parameters_meta[0].json_types == ("string",)


def test_denied_field_alias_cannot_survive_as_scoped_input_parameter_name():
    """An input's canonical name may repeat a separately denied field alias."""
    secret_alias = "owner_private_token_alias"
    router = build_fixture(500)
    tool = router.registry.get("fork_owner")
    endpoint = tool.endpoints[0]
    endpoint.output_fields.append(type(endpoint.output_fields[0])(
        name="private_token", aliases=[secret_alias],
        json_schema={"type": "string"},
    ))
    endpoint.parameters.append(ParameterSpec(
        name=secret_alias, required=False,
        json_schema={"type": "string"},
    ))
    router.add_tool(tool, replace=True)
    router.authorization_policy = AuthorizationPolicy(
        default_effect="deny",
        rules=(AuthorizationRule(
            effect="allow", operation="*.read", roles_any=("reader",),
        ),),
        data_rules=(DataScopeRule(
            operation="fork_owner.read", roles_any=("reader",),
            visible_fields=("owner",),
        ),),
    )

    scoped = router._data_scope_endpoint_view(
        ACTOR, router.registry.get("fork_owner"),
        router.registry.get("fork_owner").endpoints[0],
    )
    assert scoped is not None
    assert [p.name for p in scoped.parameters] == ["customer_id"]
    assert secret_alias not in repr(scoped)


@pytest.mark.parametrize("parameter_change", [
    "location", "required", "json_type", "removed", "renamed",
])
def test_changed_live_parameter_projection_cannot_keep_stale_public_metadata(
    monkeypatch, parameter_change,
):
    router: SchemaRouter = build_fixture(500)
    plan = router.prepare_field_routing(catalog=_catalog()).compile(
        ALIASES[0], principal=ACTOR,
    )
    original = router._data_scope_endpoint_view

    def revised_scope(principal, tool, endpoint):
        visible = original(principal, tool, endpoint)
        if visible is not None and tool.key == "fork_owner":
            visible = visible.model_copy(deep=True)
            if parameter_change == "location":
                visible.parameters[0].location = "query"
            elif parameter_change == "required":
                visible.parameters[0].required = False
                visible.input_schema = {
                    **visible.input_schema, "required": [],
                }
            elif parameter_change == "json_type":
                visible.parameters[0].json_schema = {"type": "integer"}
            elif parameter_change == "removed":
                visible.parameters.clear()
            elif parameter_change == "renamed":
                visible.parameters[0].name = "different_customer_id"
        return visible

    monkeypatch.setattr(router, "_data_scope_endpoint_view", revised_scope)
    with pytest.raises(PolicyViolationError, match="parameter|scope|changed"):
        _check_current_call_scopes(router, ACTOR, list(plan.calls))
