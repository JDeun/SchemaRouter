"""#1771: user-owned schema routing, without any provider data execution."""
from __future__ import annotations

import pytest

from schemarouter import (
    AuthorizationPolicy,
    AuthorizationRule,
    EndpointSpec,
    InMemoryRegistry,
    NativeConceptCatalog,
    NativeDeclaredConcept,
    NativeSchemaGraphIndex,
    NativeSchemaPostingIndex,
    SchemaFieldRoutingSession,
    SchemaRouter,
    SQLiteRegistry,
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


def _revised_catalog() -> NativeConceptCatalog:
    return NativeConceptCatalog(concepts=(NativeDeclaredConcept(
        concept_id="crm.customer_fields",
        aliases=("account owner", "계정 담당자", "アカウント担当者"),
        required_fields=GROUP.required_fields,
        source_type=GROUP.source_type,
        license=GROUP.license,
    ),))


def test_revise_catalog_reuses_attested_graph_without_rebuild_or_provider_io(
    monkeypatch,
):
    router = build_fixture(500)
    session = router.prepare_field_routing(catalog=_catalog())
    new_catalog = _revised_catalog()
    original_catalog_id = session.catalog_revision_id

    def forbidden(*args, **kwargs):
        pytest.fail("catalog-only revision must not rescan schemas or query providers")

    with monkeypatch.context() as scope:
        scope.setattr(NativeSchemaPostingIndex, "build", forbidden)
        scope.setattr(NativeSchemaGraphIndex, "build", forbidden)
        scope.setattr(router.registry, "tools", forbidden)
        scope.setattr(router.registry, "keys", forbidden)
        scope.setattr(router.executor, "execute", forbidden)
        scope.setattr(router.executor, "execute_call", forbidden)
        revised = session.revise_catalog(catalog=new_catalog)
        for query in new_catalog.concepts[0].aliases:
            assert revised.discover(query, principal=ACTOR).status == "complete"
            assert {call.route_id for call in revised.compile(
                query, principal=ACTOR,
            ).calls} == {ROOT, LEFT, RIGHT}

    assert revised is not session
    assert revised._index is session._index
    assert revised._index.approved_host_roots == frozenset()
    assert revised.snapshot_id == session.snapshot_id
    assert revised.catalog_revision_id != original_catalog_id
    assert revised.catalog_revision_id == session.revise_catalog(
        catalog=_revised_catalog(),
    ).catalog_revision_id
    assert session.discover(ALIASES[0], principal=ACTOR).status == "complete"
    with pytest.raises(ValueError, match="no declared concept"):
        revised.discover(ALIASES[0], principal=ACTOR)


def test_revise_catalog_detaches_new_caller_owned_catalog():
    router = build_fixture(500)
    session = router.prepare_field_routing(catalog=_catalog())
    amended = _revised_catalog()
    revised = session.revise_catalog(catalog=amended)
    amended.concepts = _catalog().concepts
    assert revised.discover("account owner", principal=ACTOR).status == "complete"
    assert revised.catalog_revision_id != session.catalog_revision_id


def test_revise_catalog_keeps_explicit_approved_host_roots():
    router = build_fixture(500)
    session = router.prepare_field_routing(
        catalog=_catalog(), approved_host_roots=frozenset({RIGHT}),
    )
    revised = session.revise_catalog(catalog=_revised_catalog())
    assert revised._index is session._index
    assert revised._index.approved_host_roots == frozenset({RIGHT})


def test_revise_catalog_revision_digest_ignores_qualifier_dict_insertion_order():
    owner_payload = _revised_catalog().model_dump(mode="python")
    first = NativeConceptCatalog.model_validate(owner_payload, strict=True)
    reordered = NativeConceptCatalog.model_validate(owner_payload, strict=True)
    first.concepts[0].required_fields[0].qualifiers = {
        "region": "KR", "tier": "standard",
    }
    reordered.concepts[0].required_fields[0].qualifiers = {
        "tier": "standard", "region": "KR",
    }
    router = build_fixture(500)
    prepared = router.prepare_field_routing(catalog=first)
    revised = prepared.revise_catalog(catalog=reordered)
    assert revised.catalog_revision_id == prepared.catalog_revision_id


def test_revise_catalog_rejects_unreviewed_inputs_and_stale_sources():
    router = build_fixture(500)
    session = router.prepare_field_routing(catalog=_catalog())
    with pytest.raises(ValueError, match="catalog"):
        session.revise_catalog(catalog={"concepts": []})

    malformed = _revised_catalog()
    object.__setattr__(malformed, "concepts", ())
    with pytest.raises(ValueError, match="catalog|concept"):
        session.revise_catalog(catalog=malformed)

    router.add_tool(ToolSpec(
        name="new_empty_tool", endpoints=[EndpointSpec(name="noop")],
    ))
    with pytest.raises(PolicyViolationError, match="stale|changed|source"):
        session.revise_catalog(catalog=_revised_catalog())


def test_revise_catalog_rejects_inflight_nested_policy_mutation(monkeypatch):
    router = build_fixture(500)
    session = router.prepare_field_routing(catalog=_catalog())
    policy = router.authorization_policy
    assert policy is not None
    amended = _revised_catalog()
    real_dump = NativeConceptCatalog.model_dump

    def mutate_policy_during_copy(self, *args, **kwargs):
        data = real_dump(self, *args, **kwargs)
        if self is amended:
            policy._rule_index.partitions[("synthetic", None, None)] = (0,)
        return data

    monkeypatch.setattr(NativeConceptCatalog, "model_dump", mutate_policy_during_copy)
    with pytest.raises(PolicyViolationError, match="policy|authorization"):
        session.revise_catalog(catalog=amended)


def test_revise_catalog_rejects_inflight_schema_revision(monkeypatch):
    router = build_fixture(500)
    session = router.prepare_field_routing(catalog=_catalog())
    amended = _revised_catalog()
    real_dump = NativeConceptCatalog.model_dump

    def change_registry_during_copy(self, *args, **kwargs):
        data = real_dump(self, *args, **kwargs)
        if self is amended:
            router.add_tool(ToolSpec(
                name="mid_copy_tool", endpoints=[EndpointSpec(name="noop")],
            ))
        return data

    monkeypatch.setattr(NativeConceptCatalog, "model_dump", change_registry_during_copy)
    with pytest.raises(PolicyViolationError, match="stale|changed|source"):
        session.revise_catalog(catalog=amended)


def test_revise_catalog_rejects_inflight_policy_identity_swap(monkeypatch):
    router = build_fixture(500)
    session = router.prepare_field_routing(catalog=_catalog())
    amended = _revised_catalog()
    real_dump = NativeConceptCatalog.model_dump

    def change_policy_during_copy(self, *args, **kwargs):
        data = real_dump(self, *args, **kwargs)
        if self is amended:
            router.authorization_policy = AuthorizationPolicy(default_effect="deny")
        return data

    monkeypatch.setattr(NativeConceptCatalog, "model_dump", change_policy_during_copy)
    with pytest.raises(PolicyViolationError, match="policy|authorization"):
        session.revise_catalog(catalog=amended)


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


def test_prepared_session_journal_refresh_preserves_original_and_matches_rebuild(
    monkeypatch,
):
    router = build_fixture(500, mixed_scope=True)
    session = router.prepare_field_routing(catalog=_catalog())
    original_snapshot = session.snapshot_id
    router.add_tool(ToolSpec(
        name="new_empty_tool", endpoints=[EndpointSpec(name="noop")],
    ))
    reference = router.prepare_field_routing(catalog=_catalog())

    def forbidden(*args, **kwargs):
        pytest.fail("journal session refresh must not rebuild or execute providers")

    with monkeypatch.context() as scope:
        scope.setattr(NativeSchemaPostingIndex, "build", forbidden)
        scope.setattr(NativeSchemaGraphIndex, "build", forbidden)
        scope.setattr(router.registry, "tools", forbidden)
        scope.setattr(router.registry, "keys", forbidden)
        scope.setattr(router.executor, "execute", forbidden)
        scope.setattr(router.executor, "execute_call", forbidden)
        refreshed = session.refresh()
        for query in ALIASES:
            assert refreshed.discover(query, principal=ACTOR) == reference.discover(
                query, principal=ACTOR,
            )
            assert refreshed.compile(query, principal=ACTOR) == reference.compile(
                query, principal=ACTOR,
            )

    assert refreshed is not session
    assert refreshed.snapshot_id == reference.snapshot_id != original_snapshot
    assert refreshed.indexed_route_count == 501
    with pytest.raises(PolicyViolationError, match="stale|changed|source"):
        session.discover(ALIASES[0], principal=ACTOR)


def test_prepared_session_verified_hint_refresh_rejects_omissions():
    router = build_fixture(500)
    session = router.prepare_field_routing(catalog=_catalog())
    with pytest.raises(PolicyViolationError, match="newer|changed|source"):
        session.refresh()
    router.add_tool(ToolSpec(
        name="new_empty_tool", endpoints=[EndpointSpec(name="noop")],
    ))
    with pytest.raises((ValueError, PolicyViolationError)):
        session.refresh(changed_tool_keys=())
    with pytest.raises(PolicyViolationError, match="changed|unknown|verify"):
        session.refresh(changed_tool_keys=("fork_origin",))
    refreshed = session.refresh(changed_tool_keys=("new_empty_tool",))
    assert refreshed.snapshot_id == router.prepare_field_routing(
        catalog=_catalog(),
    ).snapshot_id
    assert refreshed.discover(ALIASES[0], principal=ACTOR).status == "complete"


def test_prepared_session_refresh_refuses_inflight_authorization_policy_swap(
    monkeypatch,
):
    router = build_fixture(500)
    session = router.prepare_field_routing(catalog=_catalog())
    router.add_tool(ToolSpec(
        name="new_empty_tool", endpoints=[EndpointSpec(name="noop")],
    ))
    real_refresh = NativeSchemaGraphIndex.refresh_from_inmemory_journal.__func__

    def swap_policy(cls, previous, registry):
        updated = real_refresh(cls, previous, registry)
        router.authorization_policy = AuthorizationPolicy(default_effect="deny")
        return updated

    monkeypatch.setattr(
        NativeSchemaGraphIndex, "refresh_from_inmemory_journal",
        classmethod(swap_policy),
    )
    with pytest.raises(PolicyViolationError, match="policy|authorization"):
        session.refresh()


def test_prepared_session_refresh_refuses_same_policy_nested_index_mutation(
    monkeypatch,
):
    router = build_fixture(500)
    session = router.prepare_field_routing(catalog=_catalog())
    policy = router.authorization_policy
    assert policy is not None
    router.add_tool(ToolSpec(
        name="new_empty_tool", endpoints=[EndpointSpec(name="noop")],
    ))
    original = NativeSchemaGraphIndex.refresh_from_inmemory_journal.__func__

    def mutate_nested_index(cls, previous, registry):
        updated = original(cls, previous, registry)
        policy._rule_index.partitions[("synthetic", None, None)] = (0,)
        return updated

    monkeypatch.setattr(
        NativeSchemaGraphIndex, "refresh_from_inmemory_journal",
        classmethod(mutate_nested_index),
    )
    with pytest.raises(PolicyViolationError, match="policy|authorization"):
        session.refresh()


def test_prepared_session_custom_registry_requires_verified_explicit_delta():
    class CustomInMemoryRegistry(InMemoryRegistry):
        pass

    fixture = build_fixture(500)
    registry = CustomInMemoryRegistry()
    router = SchemaRouter(
        registry=registry, authorization_policy=fixture.authorization_policy,
    )
    for name in ("fork_origin", "fork_status", "fork_owner"):
        router.add_tool(fixture.registry.get(name))
    session = router.prepare_field_routing(catalog=_catalog())
    router.add_tool(ToolSpec(
        name="new_empty_tool", endpoints=[EndpointSpec(name="noop")],
    ))
    with pytest.raises(PolicyViolationError, match="custom registry"):
        session.refresh()
    new_session = session.refresh(changed_tool_keys=("new_empty_tool",))
    oracle = router.prepare_field_routing(catalog=_catalog())
    assert new_session.snapshot_id == oracle.snapshot_id
    assert new_session.discover(ALIASES[0], principal=ACTOR) == oracle.discover(
        ALIASES[0], principal=ACTOR,
    )


def test_prepared_session_refresh_wires_exact_sqlite_journal():
    fixture = build_fixture(500)
    with SQLiteRegistry(":memory:") as sqlite:
        router = SchemaRouter(
            registry=sqlite, authorization_policy=fixture.authorization_policy,
        )
        for name in ("fork_origin", "fork_status", "fork_owner"):
            router.add_tool(fixture.registry.get(name))
        original = router.prepare_field_routing(catalog=_catalog())
        owner = sqlite.get("fork_owner")
        owner.endpoint("read").output_fields[0].semantic_id = "crm.unrelated"
        sqlite.register(owner, replace=True)
        refreshed = original.refresh()
        oracle = router.prepare_field_routing(catalog=_catalog())
        assert refreshed.snapshot_id == oracle.snapshot_id
        assert refreshed.discover(ALIASES[0], principal=ACTOR) == oracle.discover(
            ALIASES[0], principal=ACTOR,
        )
        assert refreshed._index.graph.edges == oracle._index.graph.edges
        assert refreshed._index.field_index.postings == oracle._index.field_index.postings


def test_prepared_session_real_producer_delete_and_restore_refresh_graph():
    router = build_fixture(500)
    assert isinstance(router.registry, InMemoryRegistry)
    original_owner = router.registry.get("fork_owner")
    initial = router.prepare_field_routing(catalog=_catalog())
    assert initial.discover(ALIASES[0], principal=ACTOR).status == "complete"

    router.registry.unregister("fork_owner")
    removed = initial.refresh()
    missing_oracle = router.prepare_field_routing(catalog=_catalog())
    for query in ALIASES:
        assert removed.discover(query, principal=ACTOR) == missing_oracle.discover(
            query, principal=ACTOR,
        )
    assert removed._index.graph.edges == missing_oracle._index.graph.edges
    assert removed._index.field_index.postings == missing_oracle._index.field_index.postings
    assert removed.discover(ALIASES[0], principal=ACTOR).status != "complete"

    router.add_tool(original_owner)
    restored = removed.refresh()
    restored_oracle = router.prepare_field_routing(catalog=_catalog())
    for query in ALIASES:
        assert restored.discover(query, principal=ACTOR) == restored_oracle.discover(
            query, principal=ACTOR,
        )
        assert restored.compile(query, principal=ACTOR) == restored_oracle.compile(
            query, principal=ACTOR,
        )
    assert restored._index.graph.edges == restored_oracle._index.graph.edges
    assert restored._index.field_index.postings == restored_oracle._index.field_index.postings


def test_prepared_session_refresh_rejects_removed_approved_host_root():
    router = build_fixture(500)
    assert isinstance(router.registry, InMemoryRegistry)
    session = router.prepare_field_routing(
        catalog=_catalog(), approved_host_roots=frozenset({RIGHT}),
    )
    router.registry.unregister("fork_owner")
    with pytest.raises((ValueError, PolicyViolationError), match="host|approved"):
        session.refresh()


def test_prepared_session_refresh_refuses_unbounded_native_journal():
    router = build_fixture(500)
    session = router.prepare_field_routing(catalog=_catalog())
    for n in range(65):
        router.add_tool(ToolSpec(
            name=f"added_{n}", endpoints=[EndpointSpec(name="noop")],
        ))
    with pytest.raises(PolicyViolationError, match="delta|version|history|journal"):
        session.refresh()


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
