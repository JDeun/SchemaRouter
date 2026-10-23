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
    PrincipalContext,
    SchemaRouter,
    ToolSpec,
    retrieve_paper_field_coverage,
)
from schemarouter.errors import PolicyViolationError
from scripts.benchmark_native_fork_fieldgroup_e0 import (
    ACTOR,
    ALIASES,
    GROUP,
    ROOT,
    LEFT,
    RIGHT,
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
    assert alt.required_semantic_ids == (
        "crm.fork_status", "crm.fork_owner",
    )
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


def test_missing_source_consumer_abstains_without_partial_field_menu():
    router = build_fixture(500, mixed_scope=True)
    router.planner.availability_predicate = (
        lambda tool, ep: tool.key != "fork_owner"
    )
    result = retrieve_paper_field_coverage(
        router, ALIASES[0], principal=ACTOR,
        catalog=_catalog(), index=_index(router),
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


def test_changed_registry_invalidates_attested_graph():
    router = build_fixture(500)
    index = _index(router)
    router.add_tool(ToolSpec(name="late", endpoints=[
        EndpointSpec(name="read", read_only=True),
    ]))
    with pytest.raises(PolicyViolationError):
        retrieve_paper_field_coverage(
            router, ALIASES[0], principal=ACTOR,
            catalog=_catalog(), index=index,
        )


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


def test_wrong_type_semantic_field_refuses_incomplete_source():
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
    )
    assert result.status == "no_proven_hit"
    assert result.alternatives == ()


def test_deny_entire_source_never_emits_a_private_candidate():
    router = build_fixture(500)
    router.authorization_policy = AuthorizationPolicy(default_effect="deny")
    result = retrieve_paper_field_coverage(
        router, ALIASES[0], principal=ACTOR,
        catalog=_catalog(), index=_index(router),
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
