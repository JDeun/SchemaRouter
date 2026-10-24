"""#1560 opt-in E0: one source-owned flat ID branches into two leaf fields."""
from __future__ import annotations

import asyncio

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
    # Original-paper P1 must reuse exactly these real, host-attested
    # OpenAPI and MCP original source contracts, not a separate mock
    # catalog or inferred remote semantic/authorization declarations.
    from schemarouter import (
        NativeConceptCatalog,
        NativeDeclaredConcept,
        retrieve_paper_field_coverage,
    )

    catalog = NativeConceptCatalog(concepts=(NativeDeclaredConcept(
        concept_id="crm.attested_fields",
        aliases=ALIASES,
        required_fields=GROUP.required_fields,
        source_type=GROUP.source_type,
        license=GROUP.license,
    ),))
    for language_query in ALIASES:
        paper = retrieve_paper_field_coverage(
            router, language_query,
            catalog=catalog, principal=ACTOR, index=idx,
        )
        assert not paper.executable_authority
        if approve_owner_semantics:
            assert paper.status == "complete"
            assert len(paper.alternatives) == 1
            alternative = paper.alternatives[0]
            assert set(alternative.required_semantic_ids) == {
                "crm.status", "crm.owner",
            }
            assert {route.route_id for route in alternative.routes} == {
                "contacts_openapi.read_contact",
                "status_mcp.read_status",
                "owner_mcp.read_owner",
            }
            fields_by_route = {
                route.route_id: route for route in alternative.routes
            }
            assert fields_by_route["contacts_openapi.read_contact"].output_fields == (
                "customer_id",
            )
            assert fields_by_route["status_mcp.read_status"].output_fields == (
                "status",
            )
            assert fields_by_route["owner_mcp.read_owner"].output_fields == (
                "owner",
            )
            for consumer in ("status_mcp.read_status", "owner_mcp.read_owner"):
                assert fields_by_route[consumer].input_bindings == (
                    ("key", "contacts_openapi.read_contact", "customer_id"),
                )
        else:
            assert paper.status == "no_proven_hit"
            assert paper.alternatives == ()
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


        # P2 must preserve these *real converter-native* source routes
        # through a host-driven execution/binding cycle. The invokers are
        # synthetic local functions: this is not remote provider E2.
        from schemarouter import (
            ExecutionPlan,
            RunConfig,
            bind_paper_field_producer_result,
            compile_paper_field_toolcalls,
        )

        recipe = compile_paper_field_toolcalls(
            router, ALIASES[0], principal=ACTOR, catalog=catalog, index=idx,
        )
        assert recipe.status == "complete"
        calls = recipe.alternatives[0].calls
        assert (calls[0].tool, calls[0].endpoint) == (
            "contacts_openapi", "read_contact",
        )
        assert {(call.tool, call.endpoint) for call in calls[1:]} == {
            ("status_mcp", "read_status"), ("owner_mcp", "read_owner"),
        }
        invocations = []

        def contacts_invoker(endpoint_name, arguments):
            invocations.append(("contacts_openapi", endpoint_name, dict(arguments)))
            return {"customer_id": "customer-42"}

        def status_invoker(endpoint_name, arguments):
            invocations.append(("status_mcp", endpoint_name, dict(arguments)))
            return {"status": "active"}

        def owner_invoker(endpoint_name, arguments):
            invocations.append(("owner_mcp", endpoint_name, dict(arguments)))
            return {"owner": "Ada"}

        router.executor.bind("contacts_openapi", contacts_invoker)
        router.executor.bind("status_mcp", status_invoker)
        router.executor.bind("owner_mcp", owner_invoker)

        def execute_host_selected(selected_calls):
            return asyncio.run(router.execute(
                ExecutionPlan(
                    query=ALIASES[0], registry_version=recipe.registry_version,
                    calls=list(selected_calls),
                ), config=RunConfig(principal=ACTOR),
            ))

        observed = execute_host_selected(calls[:1])[0]
        assert invocations == [("contacts_openapi", "read_contact", {})]
        bound = bind_paper_field_producer_result(
            router, ALIASES[0], principal=ACTOR, catalog=catalog, index=idx,
            plan=recipe, alternative_index=0, producer_call_index=0,
            executed_call=calls[0], result=observed,
        )
        assert all(
            call.arguments == {"key": "customer-42"}
            for call in bound.alternatives[0].calls[1:]
        )
        assert invocations == [("contacts_openapi", "read_contact", {})]
        responses = execute_host_selected(bound.alternatives[0].calls[1:])
        assert {response.tool: response.data for response in responses} == {
            "status_mcp": {"status": "active"},
            "owner_mcp": {"owner": "Ada"},
        }
        assert sorted(invocations[-2:]) == [
            ("owner_mcp", "read_owner", {"key": "customer-42"}),
            ("status_mcp", "read_status", {"key": "customer-42"}),
        ]
        assert not bound.executable_authority
    else:
        assert out.status == "no_proven_hit"
        assert out.candidates == ()


@pytest.mark.parametrize("qualifier", ("source_type", "license"))
def test_shared_root_fork_refuses_cross_owner_join_without_group_qualifiers(
    qualifier,
):
    """Unconstrained host FieldGroup never implies cross-publisher consent."""
    router = _router()
    other = router.registry.get("right_0")
    if qualifier == "source_type":
        other.source_type = "external-crm"
    else:
        other.license = "different-owner"
    router.registry.register(other, replace=True)
    unconstrained = NativeDeclaredFieldGroup(
        aliases=ALIASES,
        required_fields=GROUP.required_fields,
    )
    idx = _index(router)
    for required in unconstrained.required_fields:
        single = NativeDeclaredFieldGroup(
            aliases=ALIASES, required_fields=(required,),
        )
        # Each branch is individually type-correct and allowed. Cross-owner
        # composition nonetheless lacks a reviewed source/legal agreement.
        assert idx.lookup(
            router, ALIASES[0], group=single, principal=ACTOR,
        ).status == "complete"
    result = idx.lookup_shared_root_forks(
        router, ALIASES[0], group=unconstrained, principal=ACTOR,
    )
    assert result.status == "no_proven_hit"
    assert result.qualified_fork_count == 0
    assert result.candidates == ()


@pytest.mark.parametrize("promoted_consumer", ("left", "right_0"))
def test_fork_rejects_different_consumer_contracts_despite_valid_one_hops(
    promoted_consumer,
):
    """Two valid one-hop compatible scalars are not one exact fork binding.

    The original identifier is an integer, so both an integer and a number
    input can independently consume it. The two leaves nevertheless claim
    nonidentical required scalar types for what a fork promises is one typed
    joint input contract. The fork must abstain conservatively.
    """
    router = _router()
    root = router.registry.get("origin")
    source_ep = root.endpoint("read")
    source_ep.output_fields[0].json_schema = {"type": "integer"}
    source_ep.output_schema["properties"]["customer_id"] = {"type": "integer"}
    router.registry.register(root, replace=True)
    for leaf_name in ("left", "right_0"):
        leaf = router.registry.get(leaf_name)
        endpoint = leaf.endpoint("read")
        # Both branches must be adapted from the fixture's old string ID.
        # Only one requests a wider numeric subtype.
        scalar_type = "number" if leaf_name == promoted_consumer else "integer"
        endpoint.parameters[0].json_schema = {"type": scalar_type}
        endpoint.input_schema["properties"]["key"] = {"type": scalar_type}
        router.registry.register(leaf, replace=True)
    index = _index(router)
    for required in GROUP.required_fields:
        leaf_group = NativeDeclaredFieldGroup(
            aliases=ALIASES, required_fields=(required,),
            source_type=GROUP.source_type, license=GROUP.license,
        )
        assert index.lookup(
            router, ALIASES[0], group=leaf_group, principal=ACTOR,
        ).status == "complete"
    out = index.lookup_shared_root_forks(
        router, ALIASES[0], group=GROUP, principal=ACTOR,
    )
    assert out.status == "no_proven_hit"
    assert out.qualified_fork_count == 0
    assert out.candidates == ()
    assert not out.executable_authority


def test_original_registry_rejects_duplicate_output_field_source_names():
    """Duplicate property-name ambiguity is already blocked at registration."""
    from schemarouter.errors import RegistrationError

    router = _router()
    before = router.registry.version
    root = router.registry.get("origin")
    root.endpoint("read").output_fields.append(FieldSpec(
        name="customer_id", semantic_id="crm.alternate_customer_id",
        identifier=True, json_schema={"type": "string"},
    ))
    with pytest.raises(RegistrationError, match="not a valid ToolSpec"):
        router.registry.register(root, replace=True)
    assert router.registry.version == before
    # The rejected original never enters the typed graph/index.
    index = _index(router)
    assert index.lookup_shared_root_forks(
        router, ALIASES[0], group=GROUP, principal=ACTOR,
    ).status == "complete"
