"""E0: real adapter parsers meet the same conservative native G2 graph boundary.

All source documents here are offline fixtures. Local source-owner amendments
are intentionally explicit; this is not provider discovery or end-task evidence.
"""
from __future__ import annotations

import pytest

from schemarouter import (
    AuthorizationPolicy,
    AuthorizationRule,
    DataScopeRule,
    PrincipalContext,
    SchemaRouter,
)
from schemarouter.adapters import tool_from_mcp, tool_from_openapi
from schemarouter.adapters.optimade import _tool_from_discovery
from schemarouter.capability_contracts import CapabilityFieldContract
from scripts.research_verified_graph_paths_g2 import (
    DeclaredGraphGoalG2,
    DeclaredInputBindingG2,
    _native_required_param,
    retrieve_verified_graph_paths_g2,
)

ALIASES = ("case status", "고객 문의 상태", "顧客問い合わせの状態")
ANALYST = PrincipalContext(subject="reviewed-analyst", roles=("analyst",))
VIEWER = PrincipalContext(subject="scoped-viewer", roles=("viewer",))


def _raw_tools():
    contacts = tool_from_openapi("contacts", {
        "openapi": "3.1.0",
        "info": {"title": "Contact records", "version": "1.0.0"},
        "paths": {"/contacts": {"get": {
            "operationId": "lookup_contact",
            "responses": {"200": {"description": "Contact identifier", "content": {
                "application/json": {"schema": {
                    "type": "object",
                    "properties": {"contact_id": {"type": "string"}},
                }},
            }}},
        }}},
    })
    cases = tool_from_mcp("cases", {"tools": [{
        "name": "read_case",
        "annotations": {"readOnlyHint": True},
        "inputSchema": {
            "type": "object",
            "properties": {"contact_id": {"type": "string"}},
            "required": ["contact_id"],
        },
        "outputSchema": {
            "type": "object",
            "properties": {"status": {"type": "string"}},
        },
    }]})
    materials = _tool_from_discovery(
        name="materials", namespace=None,
        versioned_base_url="https://example.org/optimade/v1",
        base_info={"api_version": "1.2.0"},
        entries={"structures": {"properties": {
            "chemical_formula_reduced": {"type": "string"},
        }}},
        skipped=[],
    )
    return contacts, cases, materials


def _router(
    *, locally_reviewed: bool, scoped: bool = False,
    root_unknown_schema: bool = False, consumer_extra_schema: bool = False,
) -> SchemaRouter:
    contacts, cases, materials = _raw_tools()
    if locally_reviewed:
        # TRUSTED LOCAL source-owner augmentation. Never derived from remote
        # MCP annotations, OpenAPI descriptions or an inferred identifier name.
        for tool in (contacts, cases):
            tool.source_type = tool.metadata["adapter"]
            tool.license = "host-reviewed-source-contract"
        contacts.endpoint("lookup_contact").read_only = True
        contact_id = next(f for f in contacts.endpoint("lookup_contact").output_fields
                          if f.name == "contact_id")
        contact_id.identifier = True
        contact_id.semantic_id = "crm.contact_id"
        cases.endpoint("read_case").read_only = True
        status = next(f for f in cases.endpoint("read_case").output_fields
                      if f.name == "status")
        status.semantic_id = "support.status"

    # Alter source-owned adapter contracts BEFORE registration; registry.get
    # returns a defensive copy and must not be used to simulate source drift.
    if root_unknown_schema:
        contacts.endpoint("lookup_contact").input_schema[
            "unevaluatedProperties"
        ] = False
    if consumer_extra_schema:
        cases.endpoint("read_case").input_schema["additionalProperties"] = False

    rules = (
        AuthorizationRule(effect="allow", operation="contacts.lookup_contact",
                          roles_any=("analyst", "viewer")),
        AuthorizationRule(effect="allow", operation="cases.read_case",
                          roles_any=("analyst", "viewer")),
    )
    router = SchemaRouter(authorization_policy=AuthorizationPolicy(
        default_effect="deny", rules=rules,
        data_rules=(
            (DataScopeRule(
                operation="contacts.lookup_contact", roles_any=("viewer",),
                hidden_fields=("contact_id",),
            ),) if scoped else ()
        ),
    ))
    for tool in (contacts, cases, materials):
        router.add_tool(tool)
    return router


def _goal(router: SchemaRouter) -> DeclaredGraphGoalG2:
    return DeclaredGraphGoalG2(
        aliases=ALIASES,
        target_route_id="cases.read_case",
        required_outputs=(CapabilityFieldContract(
            semantic_id="support.status", json_schema={"type": "string"},
        ),),
        bindings=(DeclaredInputBindingG2(
            route_id="cases.read_case",
            parameter_name="contact_id",
            semantic_id="crm.contact_id",
            expected_endpoint_fingerprint=router.registry.get(
                "cases"
            ).endpoint("read_case").fingerprint,
        ),),
    )


def test_real_parser_contracts_do_not_infer_authority_or_ontology():
    contacts, cases, materials = _raw_tools()
    assert {t.metadata["adapter"] for t in (contacts, cases, materials)} == {
        "openapi", "mcp", "optimade",
    }
    assert cases.endpoint("read_case").read_only is None
    assert cases.endpoint("read_case").metadata["annotations"]["readOnlyHint"] is True
    assert cases.endpoint("read_case").input_schema["required"] == ["contact_id"]
    assert getattr(cases.endpoint("read_case").parameters[0], "semantic_id", None) is None
    assert all(f.semantic_id is None for f in contacts.endpoint(
        "lookup_contact").output_fields)
    assert all(f.semantic_id is None for f in cases.endpoint(
        "read_case").output_fields)
    # A source-derived read-only OPTIMADE GET is NOT sufficient proof of an
    # executable graph join: minLength must remain in the input schema.
    get = materials.endpoint("get_structures")
    assert get.read_only is True
    assert get.parameters[0].json_schema["minLength"] == 1
    assert _native_required_param(get) is None


@pytest.mark.parametrize("query", ALIASES)
def test_real_openapi_to_mcp_graph_requires_trusted_host_declaration(query):
    untreated = _router(locally_reviewed=False)
    assert retrieve_verified_graph_paths_g2(
        untreated, query, principal=ANALYST, goal=_goal(untreated),
    ) == ()

    reviewed = _router(locally_reviewed=True)
    paths = retrieve_verified_graph_paths_g2(
        reviewed, query, principal=ANALYST, goal=_goal(reviewed),
    )
    assert len(paths) == 1
    assert paths[0].route_ids == ("contacts.lookup_contact", "cases.read_case")
    assert [(e.producer_output_field, e.consumer_input_parameter)
            for e in paths[0].edges] == [("contact_id", "contact_id")]
    assert paths[0].target_output_fields == ("status",)
    assert len(paths[0].scoped_snapshot_id) == 64


def test_host_review_never_overrides_principal_scope_or_schema_constraints():
    scoped = _router(locally_reviewed=True, scoped=True)
    assert retrieve_verified_graph_paths_g2(
        scoped, ALIASES[0], principal=VIEWER, goal=_goal(scoped),
    ) == ()
    assert retrieve_verified_graph_paths_g2(
        scoped, ALIASES[0], principal=ANALYST, goal=_goal(scoped),
    )

    # Preserve actual adapter input envelopes. An unproven extra constraint
    # must fail closed rather than be dropped to claim a graph edge.
    restricted = _router(locally_reviewed=True, consumer_extra_schema=True)
    assert retrieve_verified_graph_paths_g2(
        restricted, ALIASES[0], principal=ANALYST, goal=_goal(restricted),
    ) == ()


def test_real_openapi_empty_input_envelope_refuses_unknown_constraints():
    baseline = _router(locally_reviewed=True)
    source = baseline.registry.get("contacts").endpoint("lookup_contact")
    assert source.parameters == []
    assert source.input_schema == {
        "type": "object", "properties": {}, "additionalProperties": False,
    }
    # Declare an unsupported constraint in the actual registered source.
    router = _router(locally_reviewed=True, root_unknown_schema=True)
    assert retrieve_verified_graph_paths_g2(
        router, ALIASES[0], principal=ANALYST, goal=_goal(router),
    ) == ()
