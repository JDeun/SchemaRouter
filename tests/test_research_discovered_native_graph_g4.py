"""G4 E0: discover native one-hop graph targets, not preselected task-gold routes."""
from __future__ import annotations

from dataclasses import replace

import pytest

from schemarouter import (
    AuthorizationPolicy,
    AuthorizationRule,
    CapabilityFieldContract,
    DataScopeRule,
    NativeConceptCatalog,
    NativeDeclaredConcept,
    PrincipalContext,
    SchemaRouter,
)
from schemarouter.adapters import tool_from_mcp, tool_from_openapi
from schemarouter.semantic_attestations import (
    HostSemanticAttestation,
    HostSemanticMapping,
    apply_host_semantic_attestation,
)
from scripts.research_discovered_native_graph_g4 import (
    discover_authorized_native_graph_paths_g4,
)
from scripts.research_native_semantic_graph_g3 import ApprovedNativeRouteG3

ANALYST = PrincipalContext(subject="analyst", roles=("analyst",))
VIEWER = PrincipalContext(subject="viewer", roles=("viewer",))
ALIASES = ("case status", "문의 상태", "問い合わせ状態")
CATALOG = NativeConceptCatalog(concepts=(NativeDeclaredConcept(
    concept_id="crm.case_status",
    aliases=ALIASES,
    required_fields=(CapabilityFieldContract(
        semantic_id="crm.case_status", json_schema={"type": "string"},
    ),),
    source_type="crm", license="host-terms",
),))


def _attest(tool, endpoint, members):
    return HostSemanticAttestation(
        expected_tool_key=tool.key,
        expected_tool_fingerprint=tool.fingerprint,
        source_type=tool.source_type, license=tool.license,
        reviewed_by="local-reviewer-not-a-signature",
        mappings=tuple(HostSemanticMapping(
            endpoint_name=endpoint,
            expected_endpoint_fingerprint=tool.endpoint(endpoint).fingerprint,
            member_kind=kind, member_name=name, semantic_id=semantic,
        ) for kind, name, semantic in members),
    )


def _native_tools(*, targets: int = 1):
    producer = tool_from_openapi("contacts", {
        "openapi": "3.1.0", "info": {"title": "Contacts", "version": "1"},
        "paths": {"/contacts": {"get": {
            "operationId": "read_contact",
            "responses": {"200": {"description": "OK", "content": {
                "application/json": {"schema": {
                    "type": "object", "properties": {
                        "contact_id": {"type": "string"},
                    },
                }},
            }}},
        }}},
    })
    producer.source_type = "crm"
    producer.license = "host-terms"
    producer.endpoint("read_contact").read_only = True
    producer = apply_host_semantic_attestation(
        producer, attestation=_attest(
            producer, "read_contact", (
                ("output_field", "contact_id", "crm.contact_id"),
            ),
        ),
    )
    source_id = producer.endpoint("read_contact").output_fields[0]
    assert source_id.identifier is True

    consumers = []
    for i in range(targets):
        name = f"cases_{i}"
        tool = tool_from_mcp(name, {"tools": [{
            "name": "read_case", "annotations": {"readOnlyHint": True},
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
        tool.source_type = "crm"
        tool.license = "host-terms"
        assert tool.endpoint("read_case").read_only is None
        # Explicit separate host-side operation review, never a semantic
        # overlay or remote annotation granting invocation permission.
        tool.endpoint("read_case").read_only = True
        tool = apply_host_semantic_attestation(
            tool, attestation=_attest(
                tool, "read_case", (
                    ("input_parameter", "contact_id", "crm.contact_id"),
                    ("output_field", "status", "crm.case_status"),
                ),
            ),
        )
        consumers.append(tool)
    return [producer, *consumers]


def _approved(tools):
    return tuple(
        ApprovedNativeRouteG3(
            route_id=f"{tool.key}.{endpoint.name}",
            expected_tool_fingerprint=tool.fingerprint,
            expected_endpoint_fingerprint=endpoint.fingerprint,
        )
        for tool in tools for endpoint in tool.endpoints
    )


def _router(*, targets=1, hidden=False, denied=False):
    tools = _native_tools(targets=targets)
    router = SchemaRouter(authorization_policy=AuthorizationPolicy(
        default_effect="deny",
        rules=() if denied else (AuthorizationRule(
            effect="allow", operation="*.*", roles_any=("analyst", "viewer"),
        ),),
        data_rules=(DataScopeRule(
            operation="contacts.read_contact", roles_any=("viewer",),
            hidden_fields=("contact_id",),
        ),) if hidden else (),
    ))
    for tool in tools:
        router.add_tool(tool)
    return router, _approved(tools)


@pytest.mark.parametrize("query", ALIASES)
def test_attested_native_graph_discovers_target_without_user_pinned_route(query):
    router, catalog = _router()
    expected = discover_authorized_native_graph_paths_g4(
        router, query, principal=ANALYST, catalog=CATALOG,
        approved_routes=catalog,
    )
    assert len(expected) == 1
    assert expected[0].route_ids == (
        "contacts.read_contact", "cases_0.read_case",
    )
    assert [(e.producer_output_field, e.consumer_input_parameter)
            for e in expected[0].edges] == [("contact_id", "contact_id")]
    assert expected[0].target_output_fields == ("status",)
    assert len(expected[0].scoped_snapshot_id) == 64


def test_no_gold_route_or_target_is_needed_to_discover_native_schema_edge():
    router, approved = _router()
    names = list(NativeConceptCatalog.model_fields)
    assert "target_route_id" not in names
    assert all(not hasattr(x, "target_route_id") for x in approved)
    found = discover_authorized_native_graph_paths_g4(
        router, "case status", principal=ANALYST,
        catalog=CATALOG, approved_routes=approved,
    )
    assert found[0].route_ids[-1] == "cases_0.read_case"


def test_principal_hidden_identifier_and_denied_routes_do_not_create_graph():
    for hidden, denied in ((True, False), (False, True)):
        router, approved = _router(hidden=hidden, denied=denied)
        result = discover_authorized_native_graph_paths_g4(
            router, ALIASES[0], principal=VIEWER, catalog=CATALOG,
            approved_routes=approved,
        )
        assert result == ()


def test_wrong_or_missing_concept_fails_closed_not_calibrated_no_fit():
    router, approved = _router()
    with pytest.raises(ValueError, match="no declared concept"):
        discover_authorized_native_graph_paths_g4(
            router, "weather forecast", principal=ANALYST,
            catalog=CATALOG, approved_routes=approved,
        )
    for k in (1, 6, True, 5.0):
        with pytest.raises(ValueError, match="fixed K5"):
            discover_authorized_native_graph_paths_g4(
                router, ALIASES[0], principal=ANALYST,
                catalog=CATALOG, approved_routes=approved, k=k,
            )


def test_stale_endpoint_and_tool_fingerprints_cannot_sneak_in():
    router, approved = _router()
    for field in ("expected_tool_fingerprint", "expected_endpoint_fingerprint"):
        stale = replace(approved[0], **{field: "a" * 64})
        with pytest.raises(ValueError, match="source revision is stale"):
            discover_authorized_native_graph_paths_g4(
                router, ALIASES[0], principal=ANALYST,
                catalog=CATALOG, approved_routes=(stale, *approved[1:]),
            )


def test_six_real_distinct_native_targets_abstain_instead_of_truncating_k():
    router, approved = _router(targets=6)
    with pytest.raises(ValueError, match="paths exceed K5"):
        discover_authorized_native_graph_paths_g4(
            router, ALIASES[0], principal=ANALYST,
            catalog=CATALOG, approved_routes=approved,
        )


def test_authority_and_registry_drift_fail_before_a_nonexecuting_graph_hint(monkeypatch):
    router, approved = _router()
    def forbidden(*_args, **_kwargs):
        raise AssertionError("G4 must never execute or plan")
    monkeypatch.setattr(router, "plan", forbidden)
    monkeypatch.setattr(router, "execute", forbidden)
    assert discover_authorized_native_graph_paths_g4(
        router, ALIASES[0], principal=ANALYST,
        catalog=CATALOG, approved_routes=approved,
    )
    # Registry mutation after the source-attested snapshots fails closed.
    router.registry.get("cases_0").endpoint("read_case").description = "revised"
    # registry.get returns a defensive copy, thus this CANNOT change source.
    assert discover_authorized_native_graph_paths_g4(
        router, ALIASES[0], principal=ANALYST,
        catalog=CATALOG, approved_routes=approved,
    )


def test_duplicate_catalog_and_nonapproved_complete_route_do_not_expand_results():
    router, approved = _router()
    with pytest.raises(ValueError, match="unique bounded"):
        discover_authorized_native_graph_paths_g4(
            router, ALIASES[0], principal=ANALYST,
            catalog=CATALOG, approved_routes=(approved[0], approved[0]),
        )
    # Added live registry tool not attested by the owner must not become
    # a discovered candidate, even if an exact typed source clone matches.
    clone = router.registry.get("cases_0").model_copy(deep=True)
    clone.name = "unaudited_consumer"
    router.add_tool(clone)
    found = discover_authorized_native_graph_paths_g4(
        router, ALIASES[0], principal=ANALYST,
        catalog=CATALOG, approved_routes=approved,
    )
    assert len(found) == 1
    assert "unaudited_consumer" not in found[0].route_ids
