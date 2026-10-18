"""Native G5: actual adapter contracts, scoped graph evidence, no executor."""
from __future__ import annotations

import pytest

from schemarouter import (
    AuthorizationPolicy,
    AuthorizationRule,
    DataScopeRule,
    EndpointSpec,
    FieldSpec,
    PrincipalContext,
    SchemaRouter,
    ToolSpec,
)
from schemarouter.adapters import tool_from_mcp, tool_from_openapi
from schemarouter.capability_contracts import CapabilityFieldContract
from schemarouter.concept_retrieval import NativeConceptCatalog, NativeDeclaredConcept
from schemarouter.errors import PolicyViolationError
from schemarouter.field_group_retrieval import NativeDeclaredFieldGroup
from schemarouter.native_graph_index import NativeSchemaGraphIndex
from schemarouter.native_semantic_index import NativeSchemaPostingIndex
from schemarouter.semantic_attestations import (
    HostSemanticAttestation,
    HostSemanticMapping,
    apply_host_semantic_attestation,
)

ANALYST = PrincipalContext(subject="analyst", roles=("reader",))
VIEWER = PrincipalContext(subject="viewer", roles=("viewer",))
ALIASES = ("case status", "문의 상태", "問い合わせ状態")
STATUS = CapabilityFieldContract(
    semantic_id="crm.status", json_schema={"type": "string"},
)
GROUP = NativeDeclaredFieldGroup(
    aliases=ALIASES, required_fields=(STATUS,),
    source_type="crm", license="owner-reviewed",
)
CATALOG = NativeConceptCatalog(concepts=(NativeDeclaredConcept(
    concept_id="crm.case_status", aliases=ALIASES, required_fields=(STATUS,),
    source_type="crm", license="owner-reviewed",
),))


def _attest(tool, endpoint, *members):
    return HostSemanticAttestation(
        expected_tool_key=tool.key,
        expected_tool_fingerprint=tool.fingerprint,
        source_type=tool.source_type, license=tool.license,
        reviewed_by="local-owner",
        mappings=tuple(HostSemanticMapping(
            endpoint_name=endpoint,
            expected_endpoint_fingerprint=tool.endpoint(endpoint).fingerprint,
            member_kind=kind, member_name=name, semantic_id=semantic,
        ) for kind, name, semantic in members),
    )


def _tools(*, n_targets=1, incompatible=False):
    root = tool_from_openapi("contacts", {
        "openapi": "3.1.0", "info": {"title": "Contacts", "version": "1"},
        "paths": {"/contacts": {"get": {
            "operationId": "read_contact",
            "responses": {"200": {"description": "OK", "content": {
                "application/json": {"schema": {
                    "type": "object",
                    "properties": {"contact_id": {"type": "string"}},
                }},
            }}},
        }}},
    })
    root.source_type = "crm"
    root.license = "owner-reviewed"
    root.endpoint("read_contact").read_only = True
    root = apply_host_semantic_attestation(
        root, attestation=_attest(
            root, "read_contact",
            ("output_field", "contact_id", "crm.contact_id"),
        ),
    )
    assert root.endpoint("read_contact").output_fields[0].identifier

    consumers = []
    for i in range(n_targets):
        tool = tool_from_mcp(f"cases_{i}", {"tools": [{
            "name": "read_case", "annotations": {"readOnlyHint": True},
            "inputSchema": {"type": "object", "properties": {
                "contact_id": {"type": "integer" if incompatible else "string"},
            }, "required": ["contact_id"]},
            "outputSchema": {"type": "object", "properties": {
                "status": {"type": "string"},
            }},
        }]})
        assert tool.endpoint("read_case").read_only is None
        # Separate explicit host permission review, not derived from MCP
        # readOnlyHint and NEVER performed by semantic attestation.
        tool.endpoint("read_case").read_only = True
        tool.source_type = "crm"
        tool.license = "owner-reviewed"
        consumers.append(apply_host_semantic_attestation(
            tool, attestation=_attest(
                tool, "read_case",
                ("input_parameter", "contact_id", "crm.contact_id"),
                ("output_field", "status", "crm.status"),
            ),
        ))
    return [root, *consumers]


def _router(*, n_targets=1, hidden=False, denied=False, incompatible=False, noise=0):
    router = SchemaRouter(authorization_policy=AuthorizationPolicy(
        default_effect="deny",
        rules=(() if denied else (AuthorizationRule(
            effect="allow", operation="*.*", roles_any=("reader", "viewer"),
        ),)),
        data_rules=(DataScopeRule(
            operation="contacts.read_contact", roles_any=("viewer",),
            hidden_fields=("contact_id",),
        ),) if hidden else (),
    ))
    for tool in _tools(n_targets=n_targets, incompatible=incompatible):
        router.add_tool(tool)
    # Huge unrelated registered native tool catalog; no provider is called.
    for i in range(noise):
        router.add_tool(ToolSpec(
            name=f"unrelated_{i}",
            source_type="science", license="owner-reviewed",
            endpoints=[EndpointSpec(
                name="read", read_only=True,
                output_fields=[FieldSpec(
                    name="label", semantic_id="science.label",
                    json_schema={"type": "string"},
                )],
            )],
        ))
    return router


def _index(router):
    return NativeSchemaGraphIndex.build(
        NativeSchemaPostingIndex.build(router.registry),
    )


@pytest.mark.parametrize("query", ALIASES)
def test_actual_adapter_graph_discovers_target_with_source_witness_and_no_gold(query):
    router = _router(noise=24)
    graph = _index(router)
    assert graph.graph.predecessors("cases_0.read_case") == ("contacts.read_contact",)
    result = graph.lookup(router, query, group=GROUP, principal=ANALYST)
    assert result.status == "complete"
    assert result.index_snapshot_id == graph.field_index.snapshot_id
    assert result.qualified_path_count == 1
    assert result.requested_k == 5
    assert result.independent_quality_evidence is False
    assert result.executable_authority is False
    assert result.calibrated_no_fit is False
    edge = result.candidates[0]
    assert edge.producer_route_id == "contacts.read_contact"
    assert edge.consumer_route_id == "cases_0.read_case"
    assert edge.producer_identifier_field == "contact_id"
    assert edge.consumer_required_parameter == "contact_id"
    assert edge.consumer_output_fields == ("status",)
    assert len(edge.consumer_tool_fingerprint) == 64


def test_semantic_aliases_resolve_without_target_name():
    router = _router()
    idx = _index(router)
    for query in ALIASES:
        result = idx.lookup_concepts(
            router, query, catalog=CATALOG, principal=ANALYST,
        )
        assert [c.consumer_route_id for c in result.candidates] == [
            "cases_0.read_case",
        ]
    with pytest.raises(ValueError, match="no declared concept"):
        idx.lookup_concepts(router, "weather", catalog=CATALOG, principal=ANALYST)


def test_hidden_root_identifier_or_denied_policy_yields_no_graph_evidence():
    for kwargs in ({"hidden": True}, {"denied": True}):
        router = _router(**kwargs)
        idx = _index(router)
        result = idx.lookup(router, ALIASES[0], group=GROUP, principal=VIEWER)
        assert result.status == "no_proven_hit"
        assert result.candidates == ()


def test_unavailable_endpoint_revocation_is_live():
    router = _router()
    idx = _index(router)
    router.planner.availability_predicate = (
        lambda tool, ep: tool.key != "contacts"
    )
    assert idx.lookup(
        router, ALIASES[0], group=GROUP, principal=ANALYST,
    ).candidates == ()


def test_mismatched_native_scalar_types_fail_canonical_graph():
    router = _router(incompatible=True)
    idx = _index(router)
    assert idx.graph.predecessors("cases_0.read_case") == ()
    assert idx.lookup(router, ALIASES[0], group=GROUP, principal=ANALYST).candidates == ()


def test_unranked_overflow_keeps_none_of_the_six_source_verified_paths():
    router = _router(n_targets=6)
    idx = _index(router)
    result = idx.lookup(router, ALIASES[0], group=GROUP, principal=ANALYST)
    assert result.status == "over_k_unranked"
    assert result.qualified_path_count == 6
    assert result.candidates == ()


def test_untrusted_metadata_only_native_tool_cannot_create_graph_edges():
    router = _router()
    router.add_tool(ToolSpec(
        name="fake", source_type="crm", license="owner-reviewed",
        endpoints=[EndpointSpec(
            name="read", read_only=True, description="contact id case status",
        )],
    ))
    idx = _index(router)
    assert "fake.read" not in idx.graph.predecessors("cases_0.read_case")
    assert idx.lookup(
        router, ALIASES[0], group=GROUP, principal=ANALYST,
    ).qualified_path_count == 1


def test_registry_revision_and_wrong_registry_fail_closed():
    router = _router()
    idx = _index(router)
    router.add_tool(ToolSpec(name="later", endpoints=[EndpointSpec(name="read")]))
    with pytest.raises(PolicyViolationError, match="stale"):
        idx.lookup(router, ALIASES[0], group=GROUP, principal=ANALYST)
    with pytest.raises(PolicyViolationError, match="stale"):
        idx.lookup(_router(), ALIASES[0], group=GROUP, principal=ANALYST)


def test_global_registered_catalog_five_thousand_routes_without_query_global_scan(
    monkeypatch,
):
    router = _router(noise=5100)
    idx = _index(router)
    assert idx.field_index.indexed_route_count == 5102
    assert idx.native_root_count == 1
    assert idx.native_consumer_count == 1
    seen = []
    original = router.registry.get

    def recorded(key):
        seen.append(key)
        if len(seen) > 3:
            pytest.fail("per-query scanned registered native catalog")
        return original(key)

    monkeypatch.setattr(router.registry, "get", recorded)
    found = idx.lookup(router, ALIASES[0], group=GROUP, principal=ANALYST)
    assert found.qualified_path_count == 1
    assert set(seen) == {"contacts", "cases_0"}


def test_no_agent_executor_or_arbitrary_k_in_native_graph_lookup(monkeypatch):
    router = _router()
    idx = _index(router)
    monkeypatch.setattr(router, "plan", lambda *_a, **_k: pytest.fail("planned"))
    monkeypatch.setattr(router, "execute", lambda *_a, **_k: pytest.fail("executed"))
    assert idx.lookup(router, ALIASES[0], group=GROUP, principal=ANALYST).candidates
    for value in (0, 6, True, 5.0):
        with pytest.raises(ValueError, match="fixed K5"):
            idx.lookup(router, ALIASES[0], group=GROUP,
                       principal=ANALYST, k=value)


def test_in_place_policy_rules_change_during_lookup_fails_closed():
    router = _router()
    idx = _index(router)
    original_policy = router.authorization_policy
    assert original_policy is not None
    changed = False

    def availability(tool, ep):
        nonlocal changed
        if not changed:
            changed = True
            # Simulate an adversarial owner-controlled hot policy rewrite
            # rather than normal immutable-dataclass replacement.
            object.__setattr__(original_policy, "default_effect", "allow")
        return True

    router.planner.availability_predicate = availability
    with pytest.raises(PolicyViolationError, match="rules changed"):
        idx.lookup(router, ALIASES[0], group=GROUP, principal=ANALYST)


def test_replacing_availability_predicate_mid_graph_lookup_fails_closed():
    router = _router()
    index = _index(router)
    consulted = False

    def replace_during_check(tool, endpoint):
        nonlocal consulted
        if not consulted:
            consulted = True
            router.planner.availability_predicate = lambda _tool, _ep: False
        return True

    router.planner.availability_predicate = replace_during_check
    with pytest.raises(PolicyViolationError, match="availability policy changed"):
        index.lookup(router, ALIASES[0], group=GROUP, principal=ANALYST)
    assert consulted
