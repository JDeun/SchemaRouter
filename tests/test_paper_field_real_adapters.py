"""Paper Algorithm 1 required-field checks on actual OpenAPI/MCP adapters.

Remote schema/annotations are not a grant of semantic IDs, read-only
authority, license or execution. Host-signed amendments precede indexing.
"""
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
    PrincipalContext,
    SchemaRouter,
    ToolSpec,
    compile_paper_field_toolcalls,
    retrieve_paper_field_coverage,
)
from schemarouter.adapters import tool_from_mcp, tool_from_openapi
from schemarouter.adapters.optimade import _tool_from_discovery
from schemarouter.errors import PolicyViolationError

ACTOR = PrincipalContext(subject="analyst", roles=("analyst",))
ALIASES = (
    "support status and priority",
    "고객 문의 상태와 우선순위",
    "顧客問合せ状態と優先度",
)


def _catalog(*, source_type: str = "support_records",
             unit: str | None = None) -> NativeConceptCatalog:
    return NativeConceptCatalog(concepts=(NativeDeclaredConcept(
        concept_id="support.complete_fields",
        aliases=ALIASES,
        required_fields=(
            CapabilityFieldContract(
                semantic_id="support.status",
                json_schema={"type": "string"},
                unit=unit,
            ),
            CapabilityFieldContract(
                semantic_id="support.priority",
                json_schema={"type": "string"},
            ),
        ),
        source_type=source_type, license="locally-reviewed",
    ),))


def _index(router: SchemaRouter) -> NativeSchemaGraphIndex:
    return NativeSchemaGraphIndex.build(
        NativeSchemaPostingIndex.build(router.registry),
    )


def _openapi(*, complete: bool = True):
    properties = {"status": {"type": "string"}}
    if complete:
        properties["priority"] = {"type": "string"}
    tool = tool_from_openapi("api", {
        "openapi": "3.1.0",
        "info": {"title": "Support", "version": "1"},
        "paths": {"/status": {"get": {
            "operationId": "read_status",
            "responses": {"200": {
                "description": "OK",
                "content": {"application/json": {"schema": {
                    "type": "object", "properties": properties,
                }}},
            }},
        }}},
    })
    return tool


def _mcp():
    return tool_from_mcp("mcp", {"tools": [{
        "name": "read_status",
        "annotations": {"readOnlyHint": True},
        "inputSchema": {
            "type": "object", "properties": {},
            "required": [], "additionalProperties": False,
        },
        "outputSchema": {"type": "object", "properties": {
            "status": {"type": "string"},
            "priority": {"type": "string"},
        }},
    }]})


def _review(tool) -> None:
    """Host-owned approval, not untrusted remote annotation promotion."""
    tool.source_type = "support_records"
    tool.license = "locally-reviewed"
    endpoint = tool.endpoint("read_status")
    if tool.name == "mcp":
        endpoint.read_only = True
    for field in endpoint.output_fields:
        if field.name in {"status", "priority"}:
            field.semantic_id = f"support.{field.name}"


def _router(*tools, hide_priority: tuple[str, ...] = ()):
    rules = (AuthorizationRule(
        effect="allow", operation="*.read_status", roles_any=("analyst",),
    ),)
    data_rules = tuple(
        DataScopeRule(operation=f"{name}.read_status",
                      roles_any=("analyst",), hidden_fields=("priority",))
        for name in hide_priority
    )
    router = SchemaRouter(authorization_policy=AuthorizationPolicy(
        default_effect="deny", rules=rules, data_rules=data_rules,
    ))
    for tool in tools:
        router.add_tool(tool)
    return router


@pytest.mark.parametrize("query", ALIASES)
def test_actual_native_openapi_and_host_reviewed_mcp_preserve_entire_field_group(query):
    openapi, mcp = _openapi(), _mcp()
    assert mcp.endpoint("read_status").read_only is None
    assert all(f.semantic_id is None for f in mcp.endpoint("read_status").output_fields)
    for tool in (openapi, mcp):
        _review(tool)
    router = _router(openapi, mcp)
    result = retrieve_paper_field_coverage(
        router, query, principal=ACTOR, catalog=_catalog(), index=_index(router),
    )
    assert result.status == "complete"
    assert {alt.routes[0].route_id for alt in result.alternatives} == {
        "api.read_status", "mcp.read_status",
    }
    assert all(len(alt.routes) == 1 for alt in result.alternatives)
    assert all(
        set(alt.routes[0].output_fields) == {"status", "priority"}
        for alt in result.alternatives
    )
    assert all(
        set(alt.routes[0].covered_semantic_ids)
        == {"support.status", "support.priority"}
        for alt in result.alternatives
    )
    assert not result.executable_authority


def test_actual_mcp_annotations_alone_never_grant_field_or_read_only_authority():
    mcp = _mcp()
    router = _router(mcp)
    result = retrieve_paper_field_coverage(
        router, ALIASES[0], principal=ACTOR,
        catalog=_catalog(), index=_index(router),
    )
    assert result.status == "no_proven_hit"
    assert result.alternatives == ()


@pytest.mark.parametrize("query", ALIASES)
def test_actual_native_openapi_mcp_compilation_is_principal_scoped(query):
    """P2 must keep the exact P1-native converter source and field restriction."""
    openapi, mcp = _openapi(), _mcp()
    for tool in (openapi, mcp):
        _review(tool)
    router = _router(openapi, mcp, hide_priority=("mcp",))
    plan = compile_paper_field_toolcalls(
        router, query, principal=ACTOR, catalog=_catalog(), index=_index(router),
    )
    assert plan.status == "complete"
    assert len(plan.alternatives) == 1
    call = plan.alternatives[0].calls[0]
    assert (call.tool, call.endpoint) == ("api", "read_status")
    assert set(call.fields) == {"status", "priority"}
    assert call.arguments == {}
    assert plan.alternatives[0].dependencies == ()
    assert "mcp.read_status" not in str(plan)
    assert not plan.executable_authority


def test_partial_openapi_does_not_become_complete_by_text_or_unrelated_mcp():
    openapi, mcp = _openapi(complete=False), _mcp()
    for tool in (openapi, mcp):
        _review(tool)
    router = _router(openapi, mcp, hide_priority=("mcp",))
    result = retrieve_paper_field_coverage(
        router, ALIASES[0], principal=ACTOR,
        catalog=_catalog(), index=_index(router),
    )
    assert result.status == "no_proven_hit"
    assert result.alternatives == ()


def test_principal_hidden_output_never_exposes_complete_source_or_field():
    openapi, mcp = _openapi(), _mcp()
    for tool in (openapi, mcp):
        _review(tool)
    router = _router(openapi, mcp, hide_priority=("api", "mcp"))
    result = retrieve_paper_field_coverage(
        router, ALIASES[0], principal=ACTOR,
        catalog=_catalog(), index=_index(router),
    )
    assert result.status == "no_proven_hit"
    assert result.alternatives == ()
    assert "priority" not in str(result)


def test_wrong_unit_and_source_type_never_count_as_complete():
    openapi = _openapi()
    _review(openapi)
    router = _router(openapi)
    for catalog in (_catalog(unit="kPa"), _catalog(source_type="different")):
        result = retrieve_paper_field_coverage(
            router, ALIASES[0], principal=ACTOR,
            catalog=catalog, index=_index(router),
        )
        assert result.status == "no_proven_hit"
        assert result.alternatives == ()


def test_six_authorized_complete_providers_do_not_get_silently_truncated_to_five():
    router = SchemaRouter(authorization_policy=AuthorizationPolicy(
        default_effect="deny",
        rules=(AuthorizationRule(
            effect="allow", operation="*.read_status",
            roles_any=("analyst",),
        ),),
    ))
    for n in range(6):
        router.add_tool(ToolSpec(
            name=f"provider_{n}",
            source_type="support_records", license="locally-reviewed",
            endpoints=[EndpointSpec(name="read_status", read_only=True,
                output_fields=[
                    FieldSpec(name="status", semantic_id="support.status",
                              json_schema={"type": "string"}),
                    FieldSpec(name="priority", semantic_id="support.priority",
                              json_schema={"type": "string"}),
                ],
            )],
        ))
    result = retrieve_paper_field_coverage(
        router, ALIASES[0], principal=ACTOR,
        catalog=_catalog(), index=_index(router),
    )
    assert result.status == "over_k_unranked"
    assert result.alternatives == ()


def test_policy_replacement_during_current_original_source_check_fails_closed(monkeypatch):
    tool = _openapi()
    _review(tool)
    router = _router(tool)
    original = router._data_scope_endpoint_view
    invoked = False

    def replace_authority(*args, **kwargs):
        nonlocal invoked
        view = original(*args, **kwargs)
        if not invoked:
            invoked = True
            router.authorization_policy = AuthorizationPolicy(default_effect="deny")
        return view

    monkeypatch.setattr(router, "_data_scope_endpoint_view", replace_authority)
    with pytest.raises(PolicyViolationError):
        retrieve_paper_field_coverage(
            router, ALIASES[0], principal=ACTOR,
            catalog=_catalog(), index=_index(router),
        )


OPTIMADE_ALIASES = (
    "structure formula and volume",
    "구조의 화학식과 부피",
    "構造の化学式と体積",
)


def _optimade_catalog(*, unit="angstrom^3", formula_type="string"):
    return NativeConceptCatalog(concepts=(NativeDeclaredConcept(
        concept_id="materials.formula_volume",
        aliases=OPTIMADE_ALIASES,
        required_fields=(
            CapabilityFieldContract(
                semantic_id="materials.formula",
                json_schema={"type": formula_type},
            ),
            CapabilityFieldContract(
                semantic_id="materials.volume",
                json_schema={"type": "number"}, unit=unit,
            ),
        ),
        source_type="optimade", license="locally-reviewed",
    ),))


def _optimade():
    """Use the actual OPTIMADE discovery converter, not a made-up ToolSpec."""
    tool = _tool_from_discovery(
        name="materials", namespace=None,
        versioned_base_url="https://materials.example.invalid/v1",
        base_info={"api_version": "1.2.0"},
        entries={"structures": {"properties": {
            "chemical_formula_reduced": {"type": "string"},
            "volume": {"type": "number", "x-optimade-unit": "angstrom^3"},
        }}}, skipped=[],
    )
    # The converter's source metadata is not an authorization or ontology
    # decision. Only a local source owner can review the license/semantic IDs.
    tool.license = "locally-reviewed"
    for endpoint in tool.endpoints:
        for field in endpoint.output_fields:
            if field.name == "chemical_formula_reduced":
                field.semantic_id = "materials.formula"
            elif field.name == "volume":
                field.semantic_id = "materials.volume"
    return tool


def _optimade_router(*, hidden_volume=False):
    data_rules = (DataScopeRule(
        operation="materials.search_structures", roles_any=("analyst",),
        hidden_fields=("volume",),
    ),) if hidden_volume else ()
    router = SchemaRouter(authorization_policy=AuthorizationPolicy(
        default_effect="deny",
        rules=(AuthorizationRule(
            effect="allow", operation="materials.*", roles_any=("analyst",),
        ),),
        data_rules=data_rules,
    ))
    router.add_tool(_optimade())
    return router


@pytest.mark.parametrize("query", OPTIMADE_ALIASES)
def test_optimade_native_search_and_get_require_explicit_argument_policy(query):
    router = _optimade_router()
    tool = router.registry.get("materials")
    assert any(not param.required for param in tool.endpoint("search_structures").parameters)
    assert tool.endpoint("get_structures").parameters[0].required is True
    result = retrieve_paper_field_coverage(
        router, query, principal=ACTOR,
        catalog=_optimade_catalog(), index=_index(router),
    )
    # The paper P1 proof only permits input-free native roots. Search's
    # optional filter is not an owner-approved concrete argument; treating
    # it as empty risks unbounded data fetch. Get requires an ID. P2 #1560
    # must bind/approve either path explicitly before a ToolCall is offered.
    assert result.status == "no_proven_hit"
    assert result.alternatives == ()
    assert not result.executable_authority


@pytest.mark.parametrize("catalog", [
    _optimade_catalog(unit="eV"),
    _optimade_catalog(formula_type="integer"),
])
def test_optimade_native_incompatible_unit_or_shape_does_not_count(catalog):
    router = _optimade_router()
    assert retrieve_paper_field_coverage(
        router, OPTIMADE_ALIASES[0], principal=ACTOR,
        catalog=catalog, index=_index(router),
    ).status == "no_proven_hit"


def test_optimade_native_hidden_volume_abstains():
    router = _optimade_router(hidden_volume=True)
    result = retrieve_paper_field_coverage(
        router, OPTIMADE_ALIASES[0], principal=ACTOR,
        catalog=_optimade_catalog(), index=_index(router),
    )
    assert result.status == "no_proven_hit"
    assert result.alternatives == ()
