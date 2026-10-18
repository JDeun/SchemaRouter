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
from schemarouter.errors import PolicyViolationError
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
