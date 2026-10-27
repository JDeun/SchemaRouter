"""#1771: user-owned schema routing, without any provider data execution."""
from __future__ import annotations

import pytest

from schemarouter import (
    AuthorizationPolicy,
    AuthorizationRule,
    NativeConceptCatalog,
    NativeDeclaredConcept,
    NativeSchemaGraphIndex,
    NativeSchemaPostingIndex,
    SchemaFieldRoutingSession,
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


def _catalog() -> NativeConceptCatalog:
    return NativeConceptCatalog(concepts=(NativeDeclaredConcept(
        concept_id="crm.customer_fields",
        aliases=ALIASES,
        required_fields=GROUP.required_fields,
        source_type=GROUP.source_type,
        license=GROUP.license,
    ),))


@pytest.mark.parametrize("query", ALIASES)
def test_prepared_session_discovers_complete_native_field_routes(query):
    router = build_fixture(500, mixed_scope=True)
    session = router.prepare_field_routing(catalog=_catalog())
    assert isinstance(session, SchemaFieldRoutingSession)
    assert session.indexed_route_count == 500
    assert "fork_origin" not in repr(session)
    assert "crm.customer_fields" not in repr(session)
    result = session.discover(query, principal=ACTOR)
    assert result.status == "complete"
    assert not result.executable_authority
    assert {route.route_id for route in result.alternatives[0].routes} == {
        ROOT, LEFT, RIGHT,
    }
    fields = {route.route_id: route.output_fields
              for route in result.alternatives[0].routes}
    assert fields == {
        ROOT: ("customer_id",), LEFT: ("status",), RIGHT: ("owner",),
    }


def test_prepared_session_reuses_compiled_index_and_exposes_field_metadata(
    monkeypatch,
):
    router = build_fixture(500)
    builds = []
    from schemarouter import native_semantic_index

    original = native_semantic_index.NativeSchemaPostingIndex.build.__func__

    def tracked(cls, registry):
        builds.append(registry.version)
        return original(cls, registry)

    monkeypatch.setattr(
        native_semantic_index.NativeSchemaPostingIndex,
        "build", classmethod(tracked),
    )
    session = router.prepare_field_routing(catalog=_catalog())
    before = router.retrieve_authorized(ALIASES[0], principal=ACTOR)
    assert all(session.discover(q, principal=ACTOR).status == "complete"
               for q in ALIASES)
    typed = session.compile(ALIASES[1], principal=ACTOR)
    assert typed.status == "requires_observation"
    assert not typed.executable_authority
    assert {item.route_id for item in typed.calls} == {ROOT, LEFT, RIGHT}
    assert {(item.route_id, meta.name, meta.source_type, meta.license)
            for item in typed.calls for meta in item.fields_meta} == {
        (ROOT, "customer_id", "crm", "host-reviewed-synthetic"),
        (LEFT, "status", "crm", "host-reviewed-synthetic"),
        (RIGHT, "owner", "crm", "host-reviewed-synthetic"),
    }
    assert {(typed.calls[b.consumer_call_index].route_id, b.parameter,
             typed.calls[b.producer_call_index].route_id, b.producer_field)
            for b in typed.bindings} == {
        (LEFT, "customer_id", ROOT, "customer_id"),
        (RIGHT, "customer_id", ROOT, "customer_id"),
    }
    assert builds == [router.registry.version]
    assert router.retrieve_authorized(ALIASES[0], principal=ACTOR) == before


def test_prepared_session_never_calls_provider_executors(monkeypatch):
    router = build_fixture(500)
    session = router.prepare_field_routing(catalog=_catalog())

    def forbidden(*args, **kwargs):
        raise AssertionError("field discovery must not execute data calls")

    monkeypatch.setattr(router.executor, "execute", forbidden)
    monkeypatch.setattr(router.executor, "execute_call", forbidden)
    assert session.discover(ALIASES[0], principal=ACTOR).status == "complete"
    assert session.compile(ALIASES[0], principal=ACTOR).calls


def test_prepared_session_does_not_rebuild_authorized_full_catalog_per_query(
    monkeypatch,
):
    router = build_fixture(500)
    session = router.prepare_field_routing(catalog=_catalog())

    def forbidden(*args, **kwargs):
        raise AssertionError("prepared field routing must reuse indexed candidates")

    monkeypatch.setattr(router, "_scoped_analysis_registry", forbidden)
    for query in ALIASES:
        assert session.discover(query, principal=ACTOR).status == "complete"
    assert session.compile(ALIASES[0], principal=ACTOR).calls


@pytest.mark.parametrize("route_count,mixed", [(500, True), (5000, False)])
def test_indexed_session_matches_preexisting_field_proof_across_catalog_sizes(
    route_count, mixed,
):
    router = build_fixture(route_count, mixed_scope=mixed)
    catalog = _catalog()
    session = router.prepare_field_routing(catalog=catalog)
    legacy_index = NativeSchemaGraphIndex.build(
        NativeSchemaPostingIndex.build(router.registry),
    )
    for query in ALIASES:
        expected = retrieve_paper_field_coverage(
            router, query, principal=ACTOR, catalog=catalog, index=legacy_index,
        )
        assert session.discover(query, principal=ACTOR) == expected


def test_prepared_session_is_not_affected_by_callers_mutable_catalog():
    router = build_fixture(500)
    catalog = _catalog()
    session = router.prepare_field_routing(catalog=catalog)
    catalog.concepts = (NativeDeclaredConcept(
        concept_id="crm.customer_fields", aliases=("unrelated customer query",),
        required_fields=GROUP.required_fields, source_type=GROUP.source_type,
        license=GROUP.license,
    ),)
    assert session.discover(ALIASES[0], principal=ACTOR).status == "complete"


def test_prepared_session_fails_closed_when_registry_changes():
    router = build_fixture(500)
    session = router.prepare_field_routing(catalog=_catalog())
    from schemarouter import EndpointSpec

    router.add_tool(ToolSpec(
        name="new_empty_tool", endpoints=[EndpointSpec(name="noop")],
    ))
    with pytest.raises(PolicyViolationError, match="stale|changed|source"):
        session.discover(ALIASES[0], principal=ACTOR)
    with pytest.raises(PolicyViolationError, match="stale|changed|source"):
        session.compile(ALIASES[0], principal=ACTOR)
    assert router.prepare_field_routing(catalog=_catalog()).discover(
        ALIASES[0], principal=ACTOR,
    ).status == "complete"


def test_prepared_session_honors_current_source_policy_revocation():
    router = build_fixture(500)
    session = router.prepare_field_routing(catalog=_catalog())
    router.authorization_policy = AuthorizationPolicy(
        default_effect="deny",
        rules=(AuthorizationRule(
            effect="deny", operation="*.read", roles_any=("reader",),
        ),),
    )
    receipt = session.discover(ALIASES[0], principal=ACTOR)
    assert receipt.status == "no_proven_hit"
    assert receipt.alternatives == ()


def test_prepared_session_rejects_unknown_alias_without_guessing_fields():
    session = build_fixture(500).prepare_field_routing(catalog=_catalog())
    with pytest.raises(ValueError, match="no declared concept"):
        session.discover("unsupported customer request", principal=ACTOR)
    with pytest.raises(ValueError, match="no declared concept"):
        session.compile("unsupported customer request", principal=ACTOR)


@pytest.mark.parametrize("bad_k", [0, 4, 6, True, 5.0])
def test_prepared_session_preserves_original_exact_k5(bad_k):
    session = build_fixture(500).prepare_field_routing(catalog=_catalog())
    with pytest.raises(ValueError, match="K5"):
        session.discover(ALIASES[0], principal=ACTOR, k=bad_k)


def test_prepared_session_rejects_unreviewed_catalog_and_root_inputs():
    router = build_fixture(500)
    with pytest.raises(ValueError):
        router.prepare_field_routing(catalog={"concepts": []})
    with pytest.raises(ValueError):
        router.prepare_field_routing(catalog=_catalog(), approved_host_roots={ROOT})


def test_prepared_session_does_not_exist_as_a_default_retrieval_mode():
    router: SchemaRouter = build_fixture(500)
    before = router.retrieve_authorized(ALIASES[0], principal=ACTOR)
    _ = router.prepare_field_routing(catalog=_catalog())
    after = router.retrieve_authorized(ALIASES[0], principal=ACTOR)
    assert after == before
