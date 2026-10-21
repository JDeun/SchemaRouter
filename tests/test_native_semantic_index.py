"""E0: whole registry semantic postings with live principal-scoped verification."""
from __future__ import annotations

import pytest

from schemarouter import (
    AuthorizationPolicy,
    AuthorizationRule,
    CapabilityFieldContract,
    DataScopeRule,
    EndpointSpec,
    FieldSpec,
    NativeConceptCatalog,
    NativeDeclaredConcept,
    NativeDeclaredFieldGroup,
    PrincipalContext,
    SchemaRouter,
    ToolSpec,
)
from schemarouter.errors import PolicyViolationError, RegistrationError
from schemarouter.native_semantic_index import NativeSchemaPostingIndex

ANALYST = PrincipalContext(subject="researcher", roles=("analyst",))
VIEWER = PrincipalContext(subject="viewer", roles=("viewer",))
ALIASES = ("case status priority", "문의 상태 우선순위", "問い合わせ状態 優先度")
STATUS = CapabilityFieldContract(
    semantic_id="crm.status", json_schema={"type": "string"},
)
PRIORITY = CapabilityFieldContract(
    semantic_id="crm.priority", json_schema={"type": "string"},
)
GROUP = NativeDeclaredFieldGroup(
    aliases=ALIASES,
    required_fields=(STATUS, PRIORITY),
    source_type="crm", license="reviewed",
)
CATALOG = NativeConceptCatalog(concepts=(
    NativeDeclaredConcept(
        concept_id="crm.status",
        aliases=("case status", "문의 상태", "問い合わせ状態"),
        required_fields=(STATUS,),
        source_type="crm", license="reviewed",
    ),
    NativeDeclaredConcept(
        concept_id="crm.priority",
        aliases=("priority", "우선순위", "優先度"),
        required_fields=(PRIORITY,),
        source_type="crm", license="reviewed",
    ),
))


def _field(name: str, sid: str, *, typ="string", unit=None):
    return FieldSpec(name=name, semantic_id=sid,
                     json_schema={"type": typ}, unit=unit)


def _tool(name, fields, *, source="crm", license_id="reviewed", safe=True):
    return ToolSpec(
        name=name, source_type=source, license=license_id,
        endpoints=[EndpointSpec(
            name="read", read_only=safe, destructive=not safe,
            description="case status priority", output_fields=fields,
        )],
    )


def _router(*, many_partial=0, many_complete=0):
    router = SchemaRouter(authorization_policy=AuthorizationPolicy(
        default_effect="deny",
        rules=(
            AuthorizationRule(
                effect="deny", operation="denied.read",
                roles_any=("analyst", "viewer"),
            ),
            AuthorizationRule(
                effect="allow", operation="*.read",
                roles_any=("analyst", "viewer"),
            ),
        ),
        data_rules=(DataScopeRule(
            operation="complete.read", roles_any=("viewer",),
            hidden_fields=("priority",),
        ),),
    ))
    for name, fields, source, license_id, safe in (
        ("complete", [_field("status", "crm.status"),
                      _field("priority", "crm.priority")], "crm", "reviewed", True),
        ("partial", [_field("status", "crm.status")], "crm", "reviewed", True),
        ("wrong_type", [_field("status", "crm.status"),
                        _field("priority", "crm.priority", typ="integer")],
         "crm", "reviewed", True),
        ("wrong_unit", [_field("status", "crm.status"),
                        _field("priority", "crm.priority", typ="number", unit="kg")],
         "crm", "reviewed", True),
        ("wrong_source", [_field("status", "crm.status"),
                          _field("priority", "crm.priority")],
         "other", "reviewed", True),
        ("denied", [_field("status", "crm.status"),
                    _field("priority", "crm.priority")], "crm", "reviewed", True),
        ("unsafe", [_field("status", "crm.status"),
                    _field("priority", "crm.priority")], "crm", "reviewed", False),
    ):
        router.add_tool(_tool(name, fields, source=source,
                              license_id=license_id, safe=safe))
    for i in range(many_partial):
        router.add_tool(_tool(
            f"noise_{i}", [_field("status", "crm.status")],
        ))
    for i in range(many_complete):
        router.add_tool(_tool(
            f"full_{i}", [_field("status", "crm.status"),
                         _field("priority", "crm.priority")],
        ))
    return router


@pytest.mark.parametrize("query", ALIASES)
def test_native_postings_resolve_complete_fields_before_k_with_live_policy(query):
    router = _router(many_partial=120)
    old = router.retrieve_authorized(query, principal=ANALYST, k=5)
    index = NativeSchemaPostingIndex.build(router.registry)
    assert index.indexed_route_count == 127
    assert "complete.read" in index.postings["crm.priority"]
    assert "partial.read" not in index.postings["crm.priority"]
    assert len(index.route_fingerprints) == 127
    result = index.lookup(router, query, principal=ANALYST, group=GROUP)
    assert result.status == "complete"
    assert result.requested_k == 5
    assert result.qualified_count == 1
    assert [x.route_id for x in result.candidates] == ["complete.read"]
    assert result.candidates[0].required_output_fields == ("priority", "status")
    assert result.candidates[0].tool_fingerprint
    assert result.candidates[0].endpoint_fingerprint
    assert router.retrieve_authorized(query, principal=ANALYST, k=5) == old


@pytest.mark.parametrize("query", (
    "show case status and priority", "문의 상태와 우선순위를 조회",
    "問い合わせ状態と優先度を教えて",
))
def test_indexed_concept_resolution_in_longer_natural_sentences(query):
    router = _router()
    index = NativeSchemaPostingIndex.build(router.registry)
    actual = index.lookup_concepts(
        router, query, principal=ANALYST, catalog=CATALOG,
    )
    assert actual.status == "complete"
    assert [candidate.route_id for candidate in actual.candidates] == [
        "complete.read",
    ]


def test_hidden_required_field_is_not_leaked_or_satisfied():
    router = _router()
    index = NativeSchemaPostingIndex.build(router.registry)
    outcome = index.lookup(router, ALIASES[0], principal=VIEWER, group=GROUP)
    assert outcome.status == "no_proven_hit"
    assert outcome.candidates == ()
    assert outcome.qualified_count == 0
    assert "complete.read" in index.postings["crm.status"]


def test_stale_registry_fails_closed_and_rebuild_changes_snapshot():
    router = _router()
    index = NativeSchemaPostingIndex.build(router.registry)
    original = index.snapshot_id
    router.add_tool(_tool(
        "new", [_field("status", "crm.status"),
                _field("priority", "crm.priority")],
    ))
    with pytest.raises(PolicyViolationError, match="source revision is stale"):
        index.lookup(router, ALIASES[0], principal=ANALYST, group=GROUP)
    changed = NativeSchemaPostingIndex.build(router.registry)
    assert changed.snapshot_id != original
    assert changed.registry_version != index.registry_version
    assert changed.lookup(
        router, ALIASES[0], principal=ANALYST, group=GROUP,
    ).qualified_count == 2


def test_over_k_is_explicit_unranked_and_does_not_publish_arbitrary_five():
    router = _router(many_complete=6)
    index = NativeSchemaPostingIndex.build(router.registry)
    outcome = index.lookup(router, ALIASES[0], principal=ANALYST, group=GROUP)
    assert outcome.status == "over_k_unranked"
    assert outcome.qualified_count == 7
    assert outcome.candidates == ()


def test_index_itself_is_immutable_and_cannot_add_a_route():
    router = _router()
    index = NativeSchemaPostingIndex.build(router.registry)
    with pytest.raises(TypeError):
        index.postings["crm.status"] = ("forged.read",)
    with pytest.raises(TypeError):
        index.route_locations["forged.read"] = ("forged", "read")


def test_unknown_alias_or_unreviewed_partial_source_never_promoted():
    router = _router()
    index = NativeSchemaPostingIndex.build(router.registry)
    with pytest.raises(ValueError, match="host-approved"):
        index.lookup(router, "unknown", principal=ANALYST, group=GROUP)
    router.add_tool(_tool(
        "no_license", [_field("status", "crm.status"),
                       _field("priority", "crm.priority")],
        license_id=None,
    ))
    rebuilt = NativeSchemaPostingIndex.build(router.registry)
    assert "no_license.read" not in rebuilt.postings["crm.status"]


def test_no_agent_or_executor_required_for_schema_posting_lookup(monkeypatch):
    router = _router()
    monkeypatch.setattr(router, "execute", lambda *_a, **_k: pytest.fail("executed"))
    monkeypatch.setattr(router, "plan", lambda *_a, **_k: pytest.fail("planned"))
    index = NativeSchemaPostingIndex.build(router.registry)
    assert index.lookup(router, ALIASES[0], principal=ANALYST, group=GROUP).candidates


def test_strict_fixed_k_and_wrong_registry_reference_rejected():
    router = _router()
    index = NativeSchemaPostingIndex.build(router.registry)
    for invalid in (0, 3, 6, True, 5.0):
        with pytest.raises(ValueError, match="exact K5"):
            index.lookup(router, ALIASES[0], principal=ANALYST,
                         group=GROUP, k=invalid)
    second = _router()
    with pytest.raises(PolicyViolationError, match="source revision is stale"):
        index.lookup(second, ALIASES[0], principal=ANALYST, group=GROUP)


def test_query_does_not_walk_entire_registry_after_posting_intersection(monkeypatch):
    router = _router(many_partial=400)
    index = NativeSchemaPostingIndex.build(router.registry)
    seen = []
    get_original = router.registry.get

    def recorded(key):
        seen.append(key)
        if len(seen) > 8:
            pytest.fail("lookup performed a global native registry scan")
        return get_original(key)

    monkeypatch.setattr(router.registry, "get", recorded)
    outcome = index.lookup(router, ALIASES[0], principal=ANALYST, group=GROUP)
    assert outcome.qualified_count == 1
    assert set(seen) == {
        "complete", "denied", "unsafe",
        "wrong_source", "wrong_type", "wrong_unit",
    }
    assert all(not name.startswith("noise_") for name in seen)


def test_index_builds_over_five_thousand_registered_heterogeneous_routes():
    """Scale/boundary DEV: source indexes 5k+ tools, no latency SLO claimed."""
    router = _router(many_partial=5120)
    index = NativeSchemaPostingIndex.build(router.registry)
    assert index.indexed_route_count == 5127
    assert len(index.route_locations) == 5127
    assert len(index.snapshot_id) == 64
    result = index.lookup(router, ALIASES[0], principal=ANALYST, group=GROUP)
    assert result.qualified_count == 1
    assert [x.route_id for x in result.candidates] == ["complete.read"]


def test_index_rechecks_current_policy_and_availability_at_query_time():
    router = _router()
    index = NativeSchemaPostingIndex.build(router.registry)
    assert index.lookup(
        router, ALIASES[0], principal=ANALYST, group=GROUP,
    ).qualified_count == 1

    router.planner.availability_predicate = (
        lambda tool, endpoint: tool.key != "complete"
    )
    unavailable = index.lookup(
        router, ALIASES[0], principal=ANALYST, group=GROUP,
    )
    assert unavailable.status == "no_proven_hit"
    assert unavailable.candidates == ()

    router.planner.availability_predicate = None
    router.authorization_policy = AuthorizationPolicy(default_effect="deny")
    denied = index.lookup(
        router, ALIASES[0], principal=ANALYST, group=GROUP,
    )
    assert denied.status == "no_proven_hit"
    assert denied.candidates == ()


def test_replacing_availability_predicate_mid_field_lookup_fails_closed():
    router = _router()
    index = NativeSchemaPostingIndex.build(router.registry)
    consulted = False

    def replace_during_check(tool, endpoint):
        nonlocal consulted
        if not consulted:
            consulted = True
            router.planner.availability_predicate = lambda _tool, _ep: False
        return True

    router.planner.availability_predicate = replace_during_check
    with pytest.raises(PolicyViolationError, match="retrieval authority changed"):
        index.lookup(router, ALIASES[0], principal=ANALYST, group=GROUP)
    assert consulted


def _assert_refreshed_posting_oracle_equivalence(router, index):
    rebuilt = NativeSchemaPostingIndex.build(router.registry)
    assert index.registry_ref is router.registry
    assert index.registry_version == rebuilt.registry_version
    assert index.snapshot_id == rebuilt.snapshot_id
    assert index.indexed_route_count == rebuilt.indexed_route_count
    assert dict(index.postings) == dict(rebuilt.postings)
    assert dict(index.route_fingerprints) == dict(rebuilt.route_fingerprints)
    assert dict(index.route_locations) == dict(rebuilt.route_locations)
    assert dict(index.tool_fingerprints) == dict(rebuilt.tool_fingerprints)
    for principal in (ANALYST, VIEWER):
        for query in ALIASES:
            assert index.lookup(
                router, query, principal=principal, group=GROUP,
            ) == rebuilt.lookup(
                router, query, principal=principal, group=GROUP,
            )


@pytest.mark.parametrize("mutation", ("new", "replace", "remove", "batch"))
def test_native_posting_refresh_matches_exhaustive_rebuild(mutation):
    router = _router(many_partial=18)
    original = NativeSchemaPostingIndex.build(router.registry)
    if mutation == "new":
        router.add_tool(_tool(
            "added", [_field("status", "crm.status"),
                      _field("priority", "crm.priority")],
        ))
        touched = ("added",)
    elif mutation == "replace":
        router.registry.register(_tool(
            "complete", [_field("status", "crm.status"),
                         _field("priority", "crm.alternate")],
        ), replace=True)
        touched = ("complete",)
    elif mutation == "remove":
        router.registry.unregister("complete")
        touched = ("complete",)
    else:
        changed = _tool(
            "complete", [_field("status", "crm.status")],
        )
        added = _tool(
            "added", [_field("status", "crm.status"),
                      _field("priority", "crm.priority")],
        )
        router.registry.update_many(
            [changed, added], replace=True,
        )
        touched = ("complete", "added")

    with pytest.raises(PolicyViolationError, match="source revision is stale"):
        original.lookup(router, ALIASES[0], principal=ANALYST, group=GROUP)
    refreshed = NativeSchemaPostingIndex.refresh(
        original, router.registry, changed_tool_keys=touched,
    )
    _assert_refreshed_posting_oracle_equivalence(router, refreshed)
    assert original.registry_version < refreshed.registry_version


def test_native_posting_refresh_rejects_omitted_concurrent_tool_revision():
    router = _router()
    original = NativeSchemaPostingIndex.build(router.registry)
    router.registry.register(_tool(
        "complete", [_field("status", "crm.status")],
    ), replace=True)
    router.add_tool(_tool(
        "added", [_field("status", "crm.status")],
    ))
    with pytest.raises(PolicyViolationError, match="cannot verify source"):
        NativeSchemaPostingIndex.refresh(
            original, router.registry, changed_tool_keys=("added",),
        )
    updated = NativeSchemaPostingIndex.refresh(
        original, router.registry, changed_tool_keys=("complete", "added"),
    )
    _assert_refreshed_posting_oracle_equivalence(router, updated)


@pytest.mark.parametrize("bad", [
    (), ("",), ("complete", "complete"), ["complete"], ("absent",),
    ("complete",) * 65,
])
def test_native_posting_refresh_does_not_trust_malformed_or_extra_hints(bad):
    router = _router()
    original = NativeSchemaPostingIndex.build(router.registry)
    router.registry.register(_tool(
        "complete", [_field("status", "crm.status")],
    ), replace=True)
    malformed = bad != ("absent",)
    error = ValueError if malformed else PolicyViolationError
    with pytest.raises(error):
        NativeSchemaPostingIndex.refresh(
            original, router.registry, changed_tool_keys=bad,
        )


def test_native_posting_refresh_rejects_wrong_registry_and_stale_version():
    router = _router()
    original = NativeSchemaPostingIndex.build(router.registry)
    with pytest.raises(PolicyViolationError, match="newer source"):
        NativeSchemaPostingIndex.refresh(
            original, router.registry, changed_tool_keys=("complete",),
        )
    other = _router()
    other.add_tool(_tool("added", [_field("status", "crm.status")]))
    with pytest.raises(PolicyViolationError, match="source mismatch"):
        NativeSchemaPostingIndex.refresh(
            original, other.registry, changed_tool_keys=("added",),
        )


def test_native_posting_refresh_fails_closed_on_mid_manifest_source_drift(
    monkeypatch,
):
    router = _router()
    original = NativeSchemaPostingIndex.build(router.registry)
    router.add_tool(_tool("added", [_field("status", "crm.status")]))
    base_get = router.registry.get
    fired = False

    def racing_get(key):
        nonlocal fired
        if not fired:
            fired = True
            router.registry.register(
                _tool("partial", [_field("priority", "crm.priority")]),
                replace=True,
            )
        return base_get(key)

    monkeypatch.setattr(router.registry, "get", racing_get)
    with pytest.raises(PolicyViolationError, match="cannot verify source"):
        NativeSchemaPostingIndex.refresh(
            original, router.registry, changed_tool_keys=("added",),
        )
    assert fired


def test_native_posting_refresh_does_not_call_full_catalog_tools(monkeypatch):
    router = _router(many_partial=125)
    original = NativeSchemaPostingIndex.build(router.registry)
    router.add_tool(_tool(
        "added", [_field("status", "crm.status"),
                  _field("priority", "crm.priority")],
    ))

    def banned():
        pytest.fail("semantic posting refresh must not rebuild all fields")

    monkeypatch.setattr(router.registry, "tools", banned)
    refreshed = NativeSchemaPostingIndex.refresh(
        original, router.registry, changed_tool_keys=("added",),
    )
    assert refreshed.lookup(
        router, ALIASES[0], principal=ANALYST, group=GROUP,
    ).qualified_count == 2
    assert len(refreshed.tool_fingerprints) == 133


@pytest.mark.parametrize("change", (
    "add", "replace", "remove", "batch", "transient",
))
def test_registry_journal_refresh_is_exactly_equal_to_full_build(change):
    router = _router(many_partial=16)
    previous = NativeSchemaPostingIndex.build(router.registry)
    if change == "add":
        router.add_tool(_tool(
            "added", [_field("status", "crm.status"),
                      _field("priority", "crm.priority")],
        ))
    elif change == "replace":
        router.registry.register(_tool(
            "complete", [_field("status", "crm.status")],
        ), replace=True)
    elif change == "remove":
        router.registry.unregister("complete")
    elif change == "batch":
        router.registry.update_many((
            _tool("complete", [_field("priority", "crm.priority")]),
            _tool("added", [_field("status", "crm.status"),
                           _field("priority", "crm.priority")]),
        ), replace=True)
    else:
        # A transient tool can be added and removed BETWEEN source
        # snapshots. It is journalled although absent from both manifests.
        router.add_tool(_tool(
            "transient", [_field("status", "crm.status")],
        ))
        router.registry.unregister("transient")
    actual = NativeSchemaPostingIndex.refresh_from_inmemory_journal(
        previous, router.registry,
    )
    oracle = NativeSchemaPostingIndex.build(router.registry)
    assert actual.snapshot_id == oracle.snapshot_id
    assert actual.registry_version == oracle.registry_version
    assert actual.indexed_route_count == oracle.indexed_route_count
    assert dict(actual.postings) == dict(oracle.postings)
    assert dict(actual.route_fingerprints) == dict(oracle.route_fingerprints)
    assert dict(actual.route_locations) == dict(oracle.route_locations)
    assert dict(actual.tool_fingerprints) == dict(oracle.tool_fingerprints)
    for actor in (ANALYST, VIEWER):
        for query in ALIASES:
            assert actual.lookup(
                router, query, principal=actor, group=GROUP,
            ) == oracle.lookup(
                router, query, principal=actor, group=GROUP,
            )


def test_registry_journal_refresh_does_not_read_unmodified_tools_or_scan_keys(
    monkeypatch,
):
    router = _router(many_partial=215)
    previous = NativeSchemaPostingIndex.build(router.registry)
    router.add_tool(_tool(
        "added", [_field("status", "crm.status"),
                  _field("priority", "crm.priority")],
    ))
    read_get = router.registry.get

    def changed_only(key):
        if key != "added":
            pytest.fail("journal refresh read unchanged native source")
        return read_get(key)

    with monkeypatch.context() as scoped:
        scoped.setattr(router.registry, "get", changed_only)
        scoped.setattr(
            router.registry, "tools",
            lambda: pytest.fail("journal refresh scanned whole native catalog"),
        )
        scoped.setattr(
            router.registry, "keys",
            lambda: pytest.fail("journal refresh walked global native manifest"),
        )
        refreshed = NativeSchemaPostingIndex.refresh_from_inmemory_journal(
            previous, router.registry,
        )
    assert refreshed.indexed_route_count == previous.indexed_route_count + 1
    assert refreshed.lookup(
        router, ALIASES[0], principal=ANALYST, group=GROUP,
    ).qualified_count == 2


def test_registry_journal_refresh_rejects_stale_wrong_source_and_no_change():
    router = _router()
    previous = NativeSchemaPostingIndex.build(router.registry)
    with pytest.raises(PolicyViolationError, match="invalid delta"):
        NativeSchemaPostingIndex.refresh_from_inmemory_journal(
            previous, router.registry,
        )
    foreign = _router()
    foreign.add_tool(_tool("added", [_field("status", "crm.status")]))
    with pytest.raises(PolicyViolationError, match="source mismatch"):
        NativeSchemaPostingIndex.refresh_from_inmemory_journal(
            previous, foreign.registry,
        )


def test_registry_journal_refresh_fails_closed_on_concurrent_native_mutation(
    monkeypatch,
):
    router = _router()
    previous = NativeSchemaPostingIndex.build(router.registry)
    router.add_tool(_tool("added", [_field("status", "crm.status")]))
    read_get = router.registry.get
    changed = False

    def concurrent_get(key):
        nonlocal changed
        if not changed:
            changed = True
            router.add_tool(_tool("later", [_field("status", "crm.status")]))
        return read_get(key)

    monkeypatch.setattr(router.registry, "get", concurrent_get)
    with pytest.raises(PolicyViolationError, match="cannot verify"):
        NativeSchemaPostingIndex.refresh_from_inmemory_journal(
            previous, router.registry,
        )


def test_registry_journal_refresh_fails_when_receipt_expired(monkeypatch):
    router = _router()
    previous = NativeSchemaPostingIndex.build(router.registry)
    monkeypatch.setattr(
        router.registry, "changed_tool_keys_since",
        lambda _version: (_ for _ in ()).throw(
            RegistrationError("registry mutation history expired")
        ),
    )
    with pytest.raises(PolicyViolationError, match="full rebuild required"):
        NativeSchemaPostingIndex.refresh_from_inmemory_journal(
            previous, router.registry,
        )


@pytest.mark.parametrize("count", (1, 6))
def test_default_native_postings_same_callable_health_revocation_fails_closed(
    count,
):
    """A later complete field candidate may withdraw an earlier one's health.

    Must guard both complete K5 responses and over-K count-only answers.
    """
    router = _router(many_complete=count)
    index = NativeSchemaPostingIndex.build(router.registry)
    disabled: set[str] = set()
    saw_later = False

    def health(tool, _endpoint):
        nonlocal saw_later
        if tool.key == f"full_{count - 1}" and not saw_later:
            saw_later = True
            disabled.add("complete")
        return tool.key not in disabled

    router.planner.availability_predicate = health
    with pytest.raises(
        PolicyViolationError,
        match="indexed candidate eligibility changed during lookup",
    ):
        index.lookup(router, ALIASES[0], principal=ANALYST, group=GROUP)
    assert saw_later
    assert router.planner.availability_predicate is health
    assert router.registry.version == index.registry_version


def test_default_native_postings_stable_health_keeps_complete_field_group():
    router = _router(many_complete=1)
    index = NativeSchemaPostingIndex.build(router.registry)
    router.planner.availability_predicate = lambda _tool, _ep: True
    result = index.lookup(
        router, ALIASES[0], principal=ANALYST, group=GROUP,
    )
    assert result.status == "complete"
    assert result.qualified_count == 2
    assert {candidate.route_id for candidate in result.candidates} == {
        "complete.read", "full_0.read",
    }


@pytest.mark.parametrize("failure_mode", ("callback", "truthiness"))
def test_native_postings_first_availability_failure_redacts_private_error(
    failure_mode,
):
    """A failing *initial* health probe must not disclose provider details."""
    router = _router(many_complete=1)
    index = NativeSchemaPostingIndex.build(router.registry)
    private_marker = "provider-secret-native-posting-9361"
    calls: list[str] = []

    class BadAvailability:
        def __bool__(self):
            raise RuntimeError(private_marker)

    def health(tool, _endpoint):
        calls.append(tool.key)
        if failure_mode == "callback":
            raise RuntimeError(private_marker)
        return BadAvailability()

    router.planner.availability_predicate = health
    with pytest.raises(
        PolicyViolationError,
        match="indexed availability check failed during lookup",
    ) as caught:
        index.lookup(router, ALIASES[0], principal=ANALYST, group=GROUP)
    assert calls
    assert private_marker not in str(caught.value)
    assert caught.value.__suppress_context__
    assert router.registry.version == index.registry_version
