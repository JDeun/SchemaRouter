"""Actual OpenAPI/MCP/discovered OPTIMADE native contracts in ONE G5 catalog.

E0 adapter/compiler + authorization proof only: no remote provider or agent.
All semantic links/read-only/license decisions are separately host-reviewed.
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
from schemarouter.errors import PolicyViolationError
from schemarouter.field_group_retrieval import NativeDeclaredFieldGroup
from schemarouter.native_graph_index import NativeSchemaGraphIndex
from schemarouter.native_semantic_index import NativeSchemaPostingIndex
from schemarouter.semantic_attestations import (
    HostSemanticAttestation,
    HostSemanticMapping,
    apply_host_semantic_attestation,
)

READER = PrincipalContext(subject="verified-reader", roles=("reader",))
SCOPED = PrincipalContext(subject="restricted-reader", roles=("viewer",))
ALIASES = ("case status", "문의 상태", "問い合わせ状態")
GROUP = NativeDeclaredFieldGroup(
    aliases=ALIASES,
    required_fields=(CapabilityFieldContract(
        semantic_id="crm.status", json_schema={"type": "string"},
    ),),
    source_type="crm", license="owner-reviewed",
)


def _attestation(tool, endpoint: str, *members) -> HostSemanticAttestation:
    return HostSemanticAttestation(
        expected_tool_key=tool.key,
        expected_tool_fingerprint=tool.fingerprint,
        source_type=tool.source_type,
        license=tool.license,
        reviewed_by="local-host-contract-review",
        mappings=tuple(HostSemanticMapping(
            endpoint_name=endpoint,
            expected_endpoint_fingerprint=tool.endpoint(endpoint).fingerprint,
            member_kind=kind,
            member_name=name,
            semantic_id=meaning,
        ) for kind, name, meaning in members),
    )


def _openapi_contact():
    """Actual OpenAPI 3.1 adapter compiler (not a hand-built ToolSpec)."""
    tool = tool_from_openapi("contacts", {
        "openapi": "3.1.0",
        "info": {"title": "CRM Contacts", "version": "1"},
        "paths": {"/contacts": {"get": {
            "operationId": "read_contact",
            "responses": {"200": {
                "description": "OK",
                "content": {"application/json": {"schema": {
                    "type": "object",
                    "properties": {"contact_id": {"type": "string"}},
                    "required": ["contact_id"],
                }}},
            }},
        }}},
    })
    # Adapter free text is never proof of source licensing or read-only.
    tool.source_type = "crm"
    tool.license = "owner-reviewed"
    tool.endpoint("read_contact").read_only = True
    return apply_host_semantic_attestation(
        tool, attestation=_attestation(
            tool, "read_contact",
            ("output_field", "contact_id", "crm.contact_id"),
        ),
    )


def _mcp_case(*, host_review: bool):
    """Actual MCP tools/list schema including an untrusted readOnlyHint."""
    tool = tool_from_mcp("case_service", {"tools": [{
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
            "required": ["status"],
        },
    }]})
    assert tool.endpoint("read_case").read_only is None
    assert tool.endpoint("read_case").input_schema.get("required") == [
        "contact_id"
    ]
    tool.source_type = "crm"
    tool.license = "owner-reviewed"
    if not host_review:
        return tool
    # Local reviewer, not MCP annotations, allows a non-destructive route.
    tool.endpoint("read_case").read_only = True
    return apply_host_semantic_attestation(
        tool, attestation=_attestation(
            tool, "read_case",
            ("input_parameter", "contact_id", "crm.contact_id"),
            ("output_field", "status", "crm.status"),
        ),
    )


def _discovered_optimade():
    """Actual OPTIMADE discovery adapter compiler, mocked discovery document.

    This intentionally is NOT a material-specific branch in the G5 index.
    """
    tool = _tool_from_discovery(
        name="materials", namespace=None,
        versioned_base_url="https://provider.example.invalid/v1",
        base_info={"api_version": "1.2.0"},
        entries={"structures": {
            "properties": {
                "chemical_formula_reduced": {"type": "string"},
            },
            "output_fields_by_format": {
                "json": ["chemical_formula_reduced"],
            },
        }},
        skipped=[],
    )
    tool.license = "owner-reviewed"
    # Host can review an existing native ID's semantics. This does NOT
    # simplify or overwrite the original minLength input requirement.
    return apply_host_semantic_attestation(
        tool, attestation=_attestation(
            tool, "get_structures",
            ("output_field", "id", "materials.structure_id"),
        ),
    )


def _catalog(*, mcp_review: bool = True, hide_contact: bool = False):
    policy = AuthorizationPolicy(
        default_effect="deny",
        rules=(AuthorizationRule(
            effect="allow", operation="*.*",
            roles_any=("reader", "viewer"),
        ),),
        data_rules=(DataScopeRule(
            operation="contacts.read_contact",
            roles_any=("viewer",),
            hidden_fields=("contact_id",),
        ),) if hide_contact else (),
    )
    router = SchemaRouter(authorization_policy=policy)
    for tool in (
        _openapi_contact(), _mcp_case(host_review=mcp_review),
        _discovered_optimade(),
    ):
        router.add_tool(tool)
    index = NativeSchemaGraphIndex.build(
        NativeSchemaPostingIndex.build(router.registry),
    )
    return router, index


@pytest.mark.parametrize("query", ALIASES)
def test_three_original_adapter_compilers_share_one_authorized_graph(query):
    router, graph = _catalog()
    assert graph.field_index.indexed_route_count == 4
    assert graph.graph.predecessors("case_service.read_case") == (
        "contacts.read_contact",
    )
    result = graph.lookup(router, query, group=GROUP, principal=READER)
    assert result.status == "complete"
    assert result.requested_k == 5
    assert len(result.candidates) == 1
    edge = result.candidates[0]
    assert edge.producer_route_id == "contacts.read_contact"
    assert edge.consumer_route_id == "case_service.read_case"
    assert edge.parameter_bindings == (("contact_id", "contact_id"),)
    assert edge.consumer_output_fields == ("status",)
    assert not result.independent_quality_evidence
    assert not result.executable_authority
    # Merely registering a materials adapter never makes CRM concepts
    # resolve to an unrelated OPTIMADE route.
    assert all("materials" not in route for route in (
        edge.producer_route_id, edge.consumer_route_id,
    ))


def test_remote_mcp_read_only_hint_never_grants_graph_authority():
    router, graph = _catalog(mcp_review=False)
    result = graph.lookup(router, ALIASES[0], group=GROUP, principal=READER)
    assert result.status == "no_proven_hit"
    assert result.candidates == ()


def test_original_optimade_get_minlength_never_silently_weakens_to_g5_root():
    materials = _discovered_optimade()
    endpoint = materials.endpoint("get_structures")
    assert endpoint.read_only is True
    assert endpoint.parameters[0].required is True
    assert endpoint.parameters[0].json_schema == {
        "type": "string", "minLength": 1,
    }
    assert materials.endpoint("search_structures").server_projection is not None

    router, graph = _catalog()
    assert not any(
        "materials" in edge.producer_route_id
        for edge in graph.lookup(
            router, ALIASES[0], group=GROUP, principal=READER,
        ).candidates
    )
    with pytest.raises(ValueError, match="invalid explicit host-approved"):
        NativeSchemaGraphIndex.build(
            NativeSchemaPostingIndex.build(router.registry),
            approved_host_roots=frozenset({"materials.get_structures"}),
        )


def test_scoped_hidden_openapi_identifier_denies_cross_protocol_edge():
    router, graph = _catalog(hide_contact=True)
    visible = graph.lookup(
        router, ALIASES[0], group=GROUP, principal=READER,
    )
    restricted = graph.lookup(
        router, ALIASES[0], group=GROUP, principal=SCOPED,
    )
    assert visible.status == "complete"
    assert restricted.status == "no_proven_hit"
    assert restricted.candidates == ()


def test_adapter_revision_invalidates_snapshot_before_exposing_graph():
    router, graph = _catalog()
    tool = router.registry.get("case_service")
    tool.endpoint("read_case").description = "source contract changed"
    router.registry.register(tool, replace=True)
    with pytest.raises(PolicyViolationError, match="stale|changed"):
        graph.lookup(
            router, ALIASES[0], group=GROUP, principal=READER,
        )


def test_remote_source_schema_drift_refuses_old_semantic_receipt():
    original = _mcp_case(host_review=False)
    attestation = _attestation(
        original, "read_case",
        ("input_parameter", "contact_id", "crm.contact_id"),
    )
    original.endpoint("read_case").parameters[0].json_schema = {
        "type": "string", "minLength": 1,
    }
    with pytest.raises(ValueError, match="source-owned|changed|differs"):
        apply_host_semantic_attestation(original, attestation=attestation)


@pytest.mark.parametrize("scoped", [False, True], ids=("authorized", "hidden-id"))
@pytest.mark.parametrize(
    "change",
    ("semantic-id", "source-type", "license", "read-only", "description"),
)
def test_real_adapter_journal_churn_revocation_and_restore(change, scoped):
    """Source-converted contracts must track journal revisions, not cache grants."""
    router, original_graph = _catalog(hide_contact=scoped)
    original = router.registry.get("case_service")
    amended = original.model_copy(deep=True)
    endpoint = amended.endpoint("read_case")
    if change == "semantic-id":
        endpoint.parameters[0].semantic_id = "crm.other_contact_id"
    elif change == "source-type":
        amended.source_type = "unrelated"
    elif change == "license":
        amended.license = "other-license"
    elif change == "read-only":
        endpoint.read_only = False
    else:
        endpoint.description = "new reviewed native schema revision"
    router.registry.register(amended, replace=True)

    with pytest.raises(PolicyViolationError):
        original_graph.lookup(router, ALIASES[0], group=GROUP, principal=READER)
    refreshed = NativeSchemaGraphIndex.refresh_from_inmemory_journal(
        original_graph, router.registry,
    )
    rebuilt = NativeSchemaGraphIndex.build(
        NativeSchemaPostingIndex.build(router.registry),
    )

    def check_pair(left, right, expected):
        assert left.field_index.snapshot_id == right.field_index.snapshot_id
        assert left.field_index.registry_version == right.field_index.registry_version
        assert left.native_root_count == right.native_root_count
        assert left.native_consumer_count == right.native_consumer_count
        assert tuple(sorted(
            (edge.producer_id, edge.consumer_id) for edge in left.graph.edges
        )) == tuple(sorted(
            (edge.producer_id, edge.consumer_id) for edge in right.graph.edges
        ))
        for query in ALIASES:
            for principal in (READER, SCOPED):
                lhs = left.lookup(router, query, group=GROUP, principal=principal)
                rhs = right.lookup(router, query, group=GROUP, principal=principal)
                assert lhs == rhs
                want = expected and (principal is READER or not scoped)
                assert lhs.status == ("complete" if want else "no_proven_hit")
                assert len(lhs.candidates) == int(want)

    check_pair(refreshed, rebuilt, expected=change == "description")
    router.registry.register(original, replace=True)
    with pytest.raises(PolicyViolationError):
        refreshed.lookup(router, ALIASES[0], group=GROUP, principal=READER)
    restored = NativeSchemaGraphIndex.refresh_from_inmemory_journal(
        refreshed, router.registry,
    )
    restored_rebuilt = NativeSchemaGraphIndex.build(
        NativeSchemaPostingIndex.build(router.registry),
    )
    check_pair(restored, restored_rebuilt, expected=True)
