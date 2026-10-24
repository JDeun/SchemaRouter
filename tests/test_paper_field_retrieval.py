"""#1535 original-paper required-field AND: source-visible BEFORE K5.

These cover genuine index/graph/registry paths, never fake selected gold.
"""
from __future__ import annotations

import pytest

from schemarouter import (
    AuthorizationPolicy,
    AuthorizationRule,
    CapabilityFieldContract,
    EndpointSpec,
    FieldSpec,
    NativeConceptCatalog,
    NativeDeclaredConcept,
    NativeSchemaGraphIndex,
    NativeSchemaPostingIndex,
    SchemaRouter,
    ToolSpec,
    retrieve_paper_field_coverage,
)
from schemarouter.errors import PolicyViolationError
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
    return NativeSchemaGraphIndex.build(
        NativeSchemaPostingIndex.build(router.registry)
    )


def _catalog():
    return NativeConceptCatalog(concepts=(NativeDeclaredConcept(
        concept_id="crm.customer_fields",
        aliases=ALIASES,
        required_fields=GROUP.required_fields,
        source_type=GROUP.source_type,
        license=GROUP.license,
    ),))


@pytest.mark.parametrize("mixed", [False, True])
@pytest.mark.parametrize("query", ALIASES)
def test_paper_union_of_two_split_fields_requires_original_typed_shared_root(
    mixed, query,
):
    router = build_fixture(500, mixed_scope=mixed)
    result = retrieve_paper_field_coverage(
        router, query, principal=ACTOR, catalog=_catalog(), index=_index(router),
    )
    assert result.status == "complete"
    assert result.requested_k == 5
    assert result.executable_authority is False
    assert result.independent_quality_evidence is False
    assert len(result.alternatives) == 1
    alt = result.alternatives[0]
    assert set(alt.required_semantic_ids) == {
        "crm.fork_status", "crm.fork_owner",
    }
    assert {r.route_id for r in alt.routes} == {ROOT, LEFT, RIGHT}
    assert len(alt.routes) == 3
    assert sum(bool(r.covered_semantic_ids) for r in alt.routes) == 2
    per_route = {route.route_id: route for route in alt.routes}
    assert per_route[ROOT].output_fields == ("customer_id",)
    assert per_route[LEFT].output_fields == ("status",)
    assert per_route[RIGHT].output_fields == ("owner",)
    assert per_route[LEFT].input_bindings == (
        ("customer_id", ROOT, "customer_id"),
    )
    assert per_route[RIGHT].input_bindings == (
        ("customer_id", ROOT, "customer_id"),
    )
    assert all(route.tool_fingerprint and route.endpoint_fingerprint
               for route in alt.routes)


def test_default_route_ranking_remains_byte_identical_before_and_after_optin():
    router = build_fixture(500, mixed_scope=False)
    before = router.retrieve_authorized(ALIASES[0], principal=ACTOR, k=5)
    retrieve_paper_field_coverage(
        router, ALIASES[0], principal=ACTOR, catalog=_catalog(),
        index=_index(router),
    )
    after = router.retrieve_authorized(ALIASES[0], principal=ACTOR, k=5)
    assert before == after


@pytest.mark.parametrize("indexed", [False, True])
def test_missing_source_consumer_abstains_without_partial_field_menu(indexed):
    router = build_fixture(500, mixed_scope=True)
    router.planner.availability_predicate = (
        lambda tool, ep: tool.key != "fork_owner"
    )
    result = retrieve_paper_field_coverage(
        router, ALIASES[0], principal=ACTOR,
        catalog=_catalog(), index=_index(router),
        experimental_indexed_direct=indexed,
    )
    assert result.status == "no_proven_hit"
    assert result.alternatives == ()


def test_unsupported_language_alias_refused_without_guessing_translation():
    router = build_fixture(500)
    with pytest.raises(ValueError, match="no declared concept"):
        retrieve_paper_field_coverage(
            router, "unknown paraphrase here", principal=ACTOR,
            catalog=_catalog(), index=_index(router),
        )


@pytest.mark.parametrize("k", [1, 4, 6, True, 5.0])
def test_never_silently_changes_public_k(k):
    router = build_fixture(500)
    with pytest.raises(ValueError, match="exact K5"):
        retrieve_paper_field_coverage(
            router, ALIASES[0], principal=ACTOR,
            catalog=_catalog(), index=_index(router), k=k,
        )


@pytest.mark.parametrize("invalid", [1, "true", None, 0.0])
def test_indexed_direct_requires_strict_bool_before_source_lookup(invalid):
    router = build_fixture(500)
    index = _index(router)
    with pytest.raises(ValueError, match="indexed direct mode must be boolean"):
        retrieve_paper_field_coverage(
            router, ALIASES[0], principal=ACTOR, catalog=_catalog(),
            index=index, experimental_indexed_direct=invalid,
        )


@pytest.mark.parametrize("indexed", [False, True])
def test_changed_registry_invalidates_attested_graph(indexed):
    router = build_fixture(500)
    index = _index(router)
    router.add_tool(ToolSpec(name="late", endpoints=[
        EndpointSpec(name="read", read_only=True),
    ]))
    with pytest.raises(PolicyViolationError):
        retrieve_paper_field_coverage(
            router, ALIASES[0], principal=ACTOR,
            catalog=_catalog(), index=index,
            experimental_indexed_direct=indexed,
        )


def test_shared_root_revoked_during_final_projection_cannot_be_published(monkeypatch):
    """A later leaf's health callback may revoke an earlier verified root."""
    router = build_fixture(500)
    index = _index(router)
    root_is_healthy = True
    fork_proof_finished = False
    original_lookup = NativeSchemaGraphIndex.lookup_shared_root_forks
    original_view = router._data_scope_endpoint_view

    def live_health(tool, _endpoint):
        return tool.name != "fork_origin" or root_is_healthy

    def observe_fork_proof(self, *args, **kwargs):
        nonlocal fork_proof_finished
        result = original_lookup(self, *args, **kwargs)
        fork_proof_finished = True
        return result

    def revoke_root_after_right_leaf(principal, tool, endpoint):
        nonlocal root_is_healthy
        scoped = original_view(principal, tool, endpoint)
        if fork_proof_finished and tool.name == "fork_owner":
            root_is_healthy = False
        return scoped

    router.planner.availability_predicate = live_health
    monkeypatch.setattr(
        NativeSchemaGraphIndex, "lookup_shared_root_forks", observe_fork_proof,
    )
    monkeypatch.setattr(router, "_data_scope_endpoint_view", revoke_root_after_right_leaf)

    with pytest.raises(PolicyViolationError, match="source eligibility changed"):
        retrieve_paper_field_coverage(
            router, ALIASES[0], principal=ACTOR,
            catalog=_catalog(), index=index,
        )
    assert fork_proof_finished
    assert not root_is_healthy


def test_one_route_covers_complete_field_group_before_k5():
    router = SchemaRouter(authorization_policy=AuthorizationPolicy(
        default_effect="deny", rules=(AuthorizationRule(
            effect="allow", operation="*.read", roles_any=("reader",),
        ),),
    ))
    for name, fields in (
        ("partial", [FieldSpec(
            name="status", semantic_id="crm.fork_status",
            json_schema={"type": "string"},
        )]),
        ("complete", [
            FieldSpec(name="status", semantic_id="crm.fork_status",
                      json_schema={"type": "string"}),
            FieldSpec(name="owner", semantic_id="crm.fork_owner",
                      json_schema={"type": "string"}),
            FieldSpec(name="request_id", semantic_id="crm.request_id",
                      json_schema={"type": "string"}, identifier=True),
            FieldSpec(name="irrelevant", semantic_id="crm.other",
                      json_schema={"type": "string"}),
        ]),
    ):
        router.add_tool(ToolSpec(
            name=name, source_type="crm", license="host-reviewed-synthetic",
            endpoints=[EndpointSpec(name="read", read_only=True,
                                    output_fields=fields)],
        ))
    result = retrieve_paper_field_coverage(
        router, ALIASES[0], principal=ACTOR, catalog=_catalog(), index=_index(router),
    )
    assert result.status == "complete"
    assert [alt.routes[0].route_id for alt in result.alternatives] == [
        "complete.read",
    ]
    assert result.alternatives[0].routes[0].output_fields == (
        "status", "owner", "request_id",
    )


def test_indexed_direct_proves_same_full_fields_before_k5():
    """An actual complete source survives the posting intersection; A-only does not."""
    router = SchemaRouter(authorization_policy=AuthorizationPolicy(
        default_effect="deny", rules=(AuthorizationRule(
            effect="allow", operation="*.read", roles_any=("reader",),
        ),),
    ))
    router.add_tool(ToolSpec(
        name="partial", source_type="crm", license="host-reviewed-synthetic",
        endpoints=[EndpointSpec(name="read", read_only=True, output_fields=[
            FieldSpec(name="status", semantic_id="crm.fork_status",
                      json_schema={"type": "string"}),
        ])],
    ))
    router.add_tool(ToolSpec(
        name="complete", source_type="crm", license="host-reviewed-synthetic",
        endpoints=[EndpointSpec(name="read", read_only=True, output_fields=[
            FieldSpec(name="request_id", semantic_id="crm.request_id",
                      json_schema={"type": "string"}, identifier=True),
            FieldSpec(name="status", semantic_id="crm.fork_status",
                      json_schema={"type": "string"}),
            FieldSpec(name="owner", semantic_id="crm.fork_owner",
                      json_schema={"type": "string"}),
        ])],
    ))
    index = _index(router)
    indexed = retrieve_paper_field_coverage(
        router, ALIASES[0], principal=ACTOR, catalog=_catalog(), index=index,
        experimental_indexed_direct=True,
    )
    baseline = retrieve_paper_field_coverage(
        router, ALIASES[0], principal=ACTOR, catalog=_catalog(), index=index,
    )
    assert indexed.status == baseline.status == "complete"
    assert len(indexed.alternatives) == len(baseline.alternatives) == 1
    assert indexed.alternatives[0].routes[0].route_id == "complete.read"
    assert indexed.alternatives[0].routes[0].output_fields == (
        "request_id", "status", "owner",
    )
    assert set(indexed.alternatives[0].required_semantic_ids) == {
        "crm.fork_status", "crm.fork_owner",
    }
    assert indexed.alternatives[0] == baseline.alternatives[0]


@pytest.mark.parametrize("query", ALIASES)
def test_indexed_direct_mode_preserves_proved_native_typed_fork(query):
    router = build_fixture(500, mixed_scope=True)
    index = _index(router)
    indexed = retrieve_paper_field_coverage(
        router, query, principal=ACTOR, catalog=_catalog(), index=index,
        experimental_indexed_direct=True,
    )
    baseline = retrieve_paper_field_coverage(
        router, query, principal=ACTOR, catalog=_catalog(), index=index,
    )
    assert indexed.status == baseline.status == "complete"
    assert indexed.alternatives == baseline.alternatives
    assert {route.route_id for route in indexed.alternatives[0].routes} == {
        ROOT, LEFT, RIGHT,
    }


@pytest.mark.parametrize("indexed", [False, True])
def test_wrong_type_semantic_field_refuses_incomplete_source(indexed):
    router = build_fixture(500, mixed_scope=True)
    mismatched = NativeConceptCatalog(concepts=(NativeDeclaredConcept(
        concept_id="crm.customer_fields",
        aliases=ALIASES,
        required_fields=(
            CapabilityFieldContract(
                semantic_id="crm.fork_status",
                json_schema={"type": "integer"},
            ),
            GROUP.required_fields[1],
        ),
        source_type="crm", license="host-reviewed-synthetic",
    ),))
    result = retrieve_paper_field_coverage(
        router, ALIASES[0], principal=ACTOR,
        catalog=mismatched, index=_index(router),
        experimental_indexed_direct=indexed,
    )
    assert result.status == "no_proven_hit"
    assert result.alternatives == ()


@pytest.mark.parametrize("indexed", [False, True])
def test_deny_entire_source_never_emits_a_private_candidate(indexed):
    router = build_fixture(500)
    router.authorization_policy = AuthorizationPolicy(default_effect="deny")
    result = retrieve_paper_field_coverage(
        router, ALIASES[0], principal=ACTOR,
        catalog=_catalog(), index=_index(router),
        experimental_indexed_direct=indexed,
    )
    assert result.status == "no_proven_hit"
    assert result.alternatives == ()


def test_not_an_agent_or_executor_even_on_full_field_union(monkeypatch):
    router = build_fixture(500)

    def forbidden(*_args, **_kwargs):
        raise AssertionError("opt-in discovery must not call or execute")

    monkeypatch.setattr(router, "execute", forbidden)
    result = retrieve_paper_field_coverage(
        router, ALIASES[0], principal=ACTOR,
        catalog=_catalog(), index=_index(router),
    )
    assert result.status == "complete"
