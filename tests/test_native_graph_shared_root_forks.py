"""#1560 opt-in E0: one source-owned flat ID branches into two leaf fields."""
from __future__ import annotations

import pytest

from schemarouter import (
    AuthorizationPolicy,
    AuthorizationRule,
    DataScopeRule,
    EndpointSpec,
    FieldSpec,
    ParameterSpec,
    PrincipalContext,
    SchemaRouter,
    ToolSpec,
)
from schemarouter.capability_contracts import CapabilityFieldContract
from schemarouter.errors import PolicyViolationError
from schemarouter.field_group_retrieval import NativeDeclaredFieldGroup
from schemarouter.native_graph_index import NativeSchemaGraphIndex
from schemarouter.native_semantic_index import NativeSchemaPostingIndex

ACTOR = PrincipalContext(subject="agent-host", roles=("reader",))
ALIASES = ("status and owner", "상태와 담당자", "状態と担当者")
GROUP = NativeDeclaredFieldGroup(
    aliases=ALIASES,
    required_fields=(
        CapabilityFieldContract(
            semantic_id="crm.status", json_schema={"type": "string"},
        ),
        CapabilityFieldContract(
            semantic_id="crm.owner", json_schema={"type": "string"},
        ),
    ),
    source_type="crm",
    license="reviewed",
)


def _root(
    *, required: bool = True, name: str = "origin",
    source_type: str = "crm", license: str = "reviewed",
) -> ToolSpec:
    return ToolSpec(
        name=name, source_type=source_type, license=license,
        endpoints=[EndpointSpec(
            name="read", read_only=True,
            output_fields=[FieldSpec(
                name="customer_id", semantic_id="crm.customer_id",
                identifier=True, json_schema={"type": "string"},
            )],
            output_schema={
                "type": "object",
                "properties": {"customer_id": {"type": "string"}},
                "required": ["customer_id"] if required else [],
            },
        )],
    )


def _leaf(name: str, semantic: str, field_name: str) -> ToolSpec:
    return ToolSpec(
        name=name, source_type="crm", license="reviewed",
        endpoints=[EndpointSpec(
            name="read", read_only=True,
            parameters=[ParameterSpec(
                name="key", semantic_id="crm.customer_id",
                required=True, json_schema={"type": "string"},
            )],
            input_schema={
                "type": "object",
                "properties": {"key": {"type": "string"}},
                "required": ["key"],
            },
            output_fields=[FieldSpec(
                name=field_name, semantic_id=semantic,
                json_schema={"type": "string"},
            )],
        )],
    )


def _router(
    *,
    hidden_right: bool = False,
    deny_right: bool = False,
    required_root_key: bool = True,
    right_count: int = 1,
    noise: int = 0,
    root_source_type: str = "crm",
    root_license: str = "reviewed",
) -> SchemaRouter:
    policy = AuthorizationPolicy(
        default_effect="deny",
        rules=(
            (AuthorizationRule(
                effect="deny", operation="right_0.read",
                roles_any=("reader",),
            ),) if deny_right else ()
        ) + (AuthorizationRule(
            effect="allow", operation="*.read",
            roles_any=("reader",),
        ),),
        data_rules=(DataScopeRule(
            operation="right_0.read",
            roles_any=("reader",),
            hidden_fields=("owner",),
        ),) if hidden_right else (),
    )
    router = SchemaRouter(authorization_policy=policy)
    router.add_tool(_root(
        required=required_root_key,
        source_type=root_source_type, license=root_license,
    ))
    router.add_tool(_leaf("left", "crm.status", "status"))
    for idx in range(right_count):
        router.add_tool(_leaf(
            f"right_{idx}", "crm.owner", "owner",
        ))
    for idx in range(noise):
        router.add_tool(_leaf(
            f"noise_{idx}", f"unrelated.{idx}", "other",
        ))
    return router


def _index(router: SchemaRouter) -> NativeSchemaGraphIndex:
    return NativeSchemaGraphIndex.build(
        NativeSchemaPostingIndex.build(router.registry),
    )


@pytest.mark.parametrize("query", ALIASES)
def test_shared_root_two_leaf_fieldgroup_is_source_attested_not_executable(query):
    router = _router(noise=80)
    idx = _index(router)
    # Neither leaf is a full FieldGroup candidate on its own.
    assert idx.lookup(router, query, group=GROUP, principal=ACTOR).status == (
        "no_proven_hit"
    )
    out = idx.lookup_shared_root_forks(
        router, query, group=GROUP, principal=ACTOR,
    )
    assert out.status == "complete"
    assert out.qualified_fork_count == 1
    fork, = out.candidates
    assert fork.root_route_id == "origin.read"
    assert fork.branch_route_ids == ("left.read", "right_0.read")
    assert fork.root_identifier_field == "customer_id"
    assert fork.branch_input_parameters == ("key", "key")
    assert fork.branch_output_fields == (("status",), ("owner",))
    assert fork.root_fingerprints == idx.field_index.route_fingerprints["origin.read"]
    assert fork.branch_fingerprints == (
        idx.field_index.route_fingerprints["left.read"],
        idx.field_index.route_fingerprints["right_0.read"],
    )
    assert out.index_snapshot_id == idx.field_index.snapshot_id
    assert not out.executable_authority
    assert not out.independent_quality_evidence
    assert not out.calibrated_no_fit


@pytest.mark.parametrize("condition", (
    "denied", "hidden", "optional_root", "unavailable",
))
def test_shared_root_rejects_hidden_denied_optional_or_unhealthy_branch(condition):
    router = _router(
        deny_right=condition == "denied",
        hidden_right=condition == "hidden",
        required_root_key=condition != "optional_root",
    )
    if condition == "unavailable":
        router.planner.availability_predicate = (
            lambda tool, _endpoint: tool.key != "right_0"
        )
    result = _index(router).lookup_shared_root_forks(
        router, ALIASES[0], group=GROUP, principal=ACTOR,
    )
    assert result.status == "no_proven_hit"
    assert result.qualified_fork_count == 0
    assert result.candidates == ()


def test_fork_six_source_visible_leaf_paths_abstain_without_candidate_ids():
    router = _router(right_count=6)
    result = _index(router).lookup_shared_root_forks(
        router, ALIASES[0], group=GROUP, principal=ACTOR,
    )
    assert result.status == "over_k_unranked"
    assert result.candidates == ()
    assert not result.executable_authority


def test_shared_root_does_not_scan_unrelated_registered_routes(monkeypatch):
    router = _router(noise=300)
    index = _index(router)
    real_get = router.registry.get
    touched: list[str] = []

    def only_relevant(key):
        touched.append(key)
        assert key in ("origin", "left", "right_0")
        return real_get(key)

    monkeypatch.setattr(router.registry, "get", only_relevant)
    result = index.lookup_shared_root_forks(
        router, ALIASES[0], group=GROUP, principal=ACTOR,
    )
    assert result.status == "complete"
    assert touched


def test_shared_root_rechecks_both_fields_after_live_health_change():
    router = _router()
    index = _index(router)
    right_seen = 0

    def health(tool, _endpoint):
        nonlocal right_seen
        if tool.key == "right_0":
            right_seen += 1
            return right_seen <= 2
        return True

    router.planner.availability_predicate = health
    with pytest.raises(
        PolicyViolationError, match="G5 fork eligibility changed during lookup",
    ):
        index.lookup_shared_root_forks(
            router, ALIASES[0], group=GROUP, principal=ACTOR,
        )
    assert right_seen >= 3


def test_shared_root_invalid_group_wrong_k_and_source_mutation_fail_closed():
    router = _router()
    index = _index(router)
    with pytest.raises(ValueError, match="fixed K5"):
        index.lookup_shared_root_forks(
            router, ALIASES[0], group=GROUP, principal=ACTOR, k=4,
        )
    with pytest.raises(ValueError, match="approved query-to-field"):
        index.lookup_shared_root_forks(
            router, "not declared", group=GROUP, principal=ACTOR,
        )
    router.add_tool(_root(name="new_origin"))
    with pytest.raises(PolicyViolationError, match="source revision is stale"):
        index.lookup_shared_root_forks(
            router, ALIASES[0], group=GROUP, principal=ACTOR,
        )


def test_shared_root_callback_error_redacts_original_private_exception():
    router = _router()
    index = _index(router)
    secret = "private-fork-health-593"

    def bad_health(_tool, _endpoint):
        raise RuntimeError(secret)

    router.planner.availability_predicate = bad_health
    with pytest.raises(
        PolicyViolationError, match="G5 fork eligibility changed",
    ) as caught:
        index.lookup_shared_root_forks(
            router, ALIASES[0], group=GROUP, principal=ACTOR,
        )
    assert secret not in str(caught.value)
    assert caught.value.__suppress_context__

def test_shared_root_pair_count_over_k_abstains_even_with_each_arm_under_k():
    """Three authorized left and three right routes yield 9 eligible forks."""
    router = _router(right_count=3)
    router.add_tool(_leaf("left_extra_1", "crm.status", "status"))
    router.add_tool(_leaf("left_extra_2", "crm.status", "status"))
    out = _index(router).lookup_shared_root_forks(
        router, ALIASES[0], group=GROUP, principal=ACTOR,
    )
    assert out.status == "over_k_unranked"
    assert out.qualified_fork_count == 9
    assert out.candidates == ()
    assert not out.calibrated_no_fit


@pytest.mark.parametrize("qualifier", ("source_type", "license"))
def test_fork_rejects_mismatched_root_provenance_or_license(qualifier):
    router = _router(
        root_source_type="external" if qualifier == "source_type" else "crm",
        root_license="unreviewed" if qualifier == "license" else "reviewed",
    )
    index = _index(router)
    # Both individual leaf routes can still prove their typed required
    # inputs; that does not certify the combined source/license contract.
    sub_group = NativeDeclaredFieldGroup(
        aliases=ALIASES,
        required_fields=(GROUP.required_fields[0],),
        source_type=GROUP.source_type,
        license=GROUP.license,
    )
    assert index.lookup(
        router, ALIASES[0], group=sub_group, principal=ACTOR,
    ).status == "complete"
    forks = index.lookup_shared_root_forks(
        router, ALIASES[0], group=GROUP, principal=ACTOR,
    )
    assert forks.status == "no_proven_hit"
    assert forks.candidates == ()


@pytest.mark.parametrize("approve_owner_semantics", (True, False))
def test_original_openapi_and_mcp_fork_requires_host_semantic_attestation(
    approve_owner_semantics,
):
    """Actual two-adapter compilers: never invent an MCP field semantic edge."""
    from schemarouter.adapters import tool_from_mcp, tool_from_openapi
    from schemarouter.semantic_attestations import (
        HostSemanticAttestation,
        HostSemanticMapping,
        apply_host_semantic_attestation,
    )

    root = tool_from_openapi("contacts_openapi", {
        "openapi": "3.1.0",
        "info": {"title": "Contacts", "version": "1"},
        "paths": {"/contacts": {"get": {
            "operationId": "read_contact",
            "responses": {"200": {"description": "OK", "content": {
                "application/json": {"schema": {
                    "type": "object",
                    "properties": {"customer_id": {"type": "string"}},
                    "required": ["customer_id"],
                }},
            }}},
        }}},
    })
    root.source_type = "crm"
    root.license = "reviewed"
    root.endpoint("read_contact").read_only = True
    root = apply_host_semantic_attestation(
        root, attestation=HostSemanticAttestation(
            expected_tool_key=root.key,
            expected_tool_fingerprint=root.fingerprint,
            source_type=root.source_type,
            license=root.license,
            reviewed_by="fixture-source-owner",
            mappings=(HostSemanticMapping(
                endpoint_name="read_contact",
                expected_endpoint_fingerprint=(
                    root.endpoint("read_contact").fingerprint
                ),
                member_kind="output_field",
                member_name="customer_id",
                semantic_id="crm.customer_id",
            ),),
        ),
    )

    leaves = []
    for tool_name, method, field, semantic in (
        ("status_mcp", "read_status", "status", "crm.status"),
        ("owner_mcp", "read_owner", "owner", "crm.owner"),
    ):
        leaf = tool_from_mcp(tool_name, {"tools": [{
            "name": method,
            "annotations": {"readOnlyHint": True},
            "inputSchema": {
                "type": "object",
                "properties": {"key": {"type": "string"}},
                "required": ["key"],
            },
            "outputSchema": {
                "type": "object",
                "properties": {field: {"type": "string"}},
            },
        }]})
        # MCP readOnlyHint is not authorization; the source-owning host
        # separately reviews operation safety and typed semantic mappings.
        assert leaf.endpoint(method).read_only is None
        leaf.endpoint(method).read_only = True
        leaf.source_type = "crm"
        leaf.license = "reviewed"
        if field != "owner" or approve_owner_semantics:
            leaf = apply_host_semantic_attestation(
                leaf, attestation=HostSemanticAttestation(
                    expected_tool_key=leaf.key,
                    expected_tool_fingerprint=leaf.fingerprint,
                    source_type=leaf.source_type,
                    license=leaf.license,
                    reviewed_by="fixture-source-owner",
                    mappings=(
                        HostSemanticMapping(
                            endpoint_name=method,
                            expected_endpoint_fingerprint=(
                                leaf.endpoint(method).fingerprint
                            ),
                            member_kind="input_parameter",
                            member_name="key",
                            semantic_id="crm.customer_id",
                        ),
                        HostSemanticMapping(
                            endpoint_name=method,
                            expected_endpoint_fingerprint=(
                                leaf.endpoint(method).fingerprint
                            ),
                            member_kind="output_field",
                            member_name=field,
                            semantic_id=semantic,
                        ),
                    ),
                ),
            )
        leaves.append(leaf)

    router = SchemaRouter(authorization_policy=AuthorizationPolicy(
        default_effect="deny",
        rules=(AuthorizationRule(
            effect="allow", operation="*.*", roles_any=("reader",),
        ),),
    ))
    router.add_tool(root)
    for leaf in leaves:
        router.add_tool(leaf)
    idx = _index(router)
    out = idx.lookup_shared_root_forks(
        router, ALIASES[0], group=GROUP, principal=ACTOR,
    )
    if approve_owner_semantics:
        assert out.status == "complete"
        (fork,) = out.candidates
        assert fork.root_route_id == "contacts_openapi.read_contact"
        assert fork.branch_route_ids == (
            "status_mcp.read_status", "owner_mcp.read_owner",
        )
        assert fork.root_identifier_field == "customer_id"
        assert fork.branch_input_parameters == ("key", "key")
        assert not out.executable_authority
    else:
        assert out.status == "no_proven_hit"
        assert out.candidates == ()
