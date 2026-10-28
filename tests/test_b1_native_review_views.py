"""B1 regression: immutable, deterministic catalog review cursor accelerators.

These structural checks are intentionally authorization-neutral. Authorization
and DataScope are enforced when a current-scoped review is requested.
"""
from __future__ import annotations

import pytest

from schemarouter.native_semantic_index import (
    NativeSchemaPostingIndex,
    _indexable_semantic_field,
    _native_review_cursor,
    _native_review_views,
)


def test_review_views_snapshot_pinned_and_sorted() -> None:
    source = {"z/route": {"crm.status", "crm.id"}, "a/route": {"crm.id"}}
    inverse, ordered, anchors = _native_review_views(source, "snapshot-one")
    assert ordered == ("a/route", "z/route")
    assert inverse["z/route"] == frozenset({"crm.status", "crm.id"})
    assert anchors[_native_review_cursor("snapshot-one", "a/route")] == "a/route"
    assert anchors[_native_review_cursor("snapshot-one", "z/route")] == "z/route"
    source["z/route"].add("crm.secret")
    source["new/route"] = {"crm.id"}
    assert "crm.secret" not in inverse["z/route"]
    assert "new/route" not in inverse


def test_review_cursor_changes_with_snapshot_revision() -> None:
    old = _native_review_cursor("snapshot-one", "a/route")
    new = _native_review_cursor("snapshot-two", "a/route")
    assert old != new
    assert old.startswith("sr1:")
    assert old == _native_review_cursor("snapshot-one", "a/route")


def test_review_views_are_immutable_and_ignore_empty_semantics() -> None:
    inverse, ordered, anchors = _native_review_views(
        {"visible": {"crm.id"}, "empty": set()}, "snapshot-one",
    )
    assert ordered == ("visible",)
    assert "empty" not in inverse
    with pytest.raises(TypeError):
        inverse["injected"] = frozenset({"crm.id"})
    with pytest.raises(TypeError):
        anchors["injected"] = "visible"


def test_public_review_pages_cover_500_source_routes() -> None:
    """Exercise the public, scoped cursor path rather than only index helpers."""
    from scripts.benchmark_native_fork_fieldgroup_e0 import ACTOR, build_fixture
    from scripts.benchmark_native_review_pagination_b1 import benchmark_review_pages

    router = build_fixture(500)
    session = router.prepare_field_routing()
    report = benchmark_review_pages(
        session,
        principal=ACTOR,
        limit=64,
    )
    assert report["source_snapshot"] == session.snapshot_id
    assert report["source_route_count"] == session.indexed_route_count
    assert report["reviewed_route_count"] <= report["source_route_count"]
    assert report["reviewed_route_count"] > 0
    assert report["page_count"] >= 1
    assert report["serialized_page_bytes"] > 0
    assert report["page_latency_ms"]["p99"] >= report["page_latency_ms"]["p50"]
    assert report["page_cpu_ms"]["p99"] >= report["page_cpu_ms"]["p50"]
    if report["process_peak_rss_before_kib"] is not None:
        assert report["process_peak_rss_after_kib"] >= report["process_peak_rss_before_kib"]


@pytest.mark.parametrize("route_count", (500, 5000))
def test_review_reverse_index_matches_independent_registered_source_oracle(
    route_count: int,
) -> None:
    """Scan registered source schemas, not the index's own forward postings."""
    from scripts.benchmark_native_fork_fieldgroup_e0 import build_fixture

    router = build_fixture(route_count, mixed_scope=True)
    index = NativeSchemaPostingIndex.build(router.registry)
    expected: dict[str, frozenset[str]] = {}
    total_routes = 0
    for tool in router.registry.tools():
        for endpoint in tool.endpoints:
            total_routes += 1
            if not tool.source_type or not tool.license:
                continue
            semantic_ids = frozenset(
                field.semantic_id for field in endpoint.output_fields
                if field.semantic_id is not None
                and _indexable_semantic_field(field)
            )
            if semantic_ids:
                expected[f"{tool.key}.{endpoint.name}"] = semantic_ids
    assert total_routes == route_count
    assert index.indexed_route_count == total_routes
    assert dict(index.route_semantic_ids) == expected
    assert index.review_route_ids == tuple(sorted(expected))
    assert len(index.review_cursor_anchors) == len(expected)
    assert set(index.review_cursor_anchors.values()) == set(expected)
    assert all(
        index.review_cursor_anchors[_native_review_cursor(index.snapshot_id, route)]
        == route for route in expected
    )


@pytest.mark.parametrize("route_count", (500, 5000))
def test_indexed_conjunctive_candidates_match_live_authorized_source_scan(
    route_count: int,
) -> None:
    """Compare pre-TopK qualified counts against a source-only eligibility scan.

    This test deliberately never uses index.postings or index.route_semantic_ids
    to construct the oracle; it reads the registered endpoint contracts.
    """
    from schemarouter.field_group_retrieval import _complete_fields
    from scripts.benchmark_native_fork_fieldgroup_e0 import (
        ACTOR,
        ALIASES,
        GROUP,
        build_fixture,
    )

    router = build_fixture(route_count, mixed_scope=True)
    index = NativeSchemaPostingIndex.build(router.registry)
    permitted = router._authorization_predicate(ACTOR)
    assert permitted is not None

    def scan() -> set[str]:
        eligible: set[str] = set()
        for tool in router.registry.tools():
            for endpoint in tool.endpoints:
                if (
                    tool.source_type != GROUP.source_type
                    or tool.license != GROUP.license
                    or endpoint.read_only is not True
                    or endpoint.destructive is True
                    or not permitted(tool, endpoint)
                ):
                    continue
                availability = router.planner.availability_predicate
                if availability is not None and not availability(tool, endpoint):
                    continue
                visible = router._data_scope_endpoint_view(ACTOR, tool, endpoint)
                if visible is not None and _complete_fields(
                    visible.output_fields, GROUP.required_fields,
                ):
                    eligible.add(f"{tool.key}.{endpoint.name}")
        return eligible

    expected = scan()
    result = index.lookup(router, ALIASES[0], principal=ACTOR, group=GROUP)
    assert result.qualified_count == len(expected)
    if len(expected) <= 5:
        assert {candidate.route_id for candidate in result.candidates} == expected
    else:
        assert result.status == "over_k_unranked"
        assert result.candidates == ()

    # A live availability change must affect lookup without rebuilding postings.
    router.planner.availability_predicate = (
        lambda tool, endpoint: tool.key != "fork_status"
    )
    changed = scan()
    after = index.lookup(router, ALIASES[0], principal=ACTOR, group=GROUP)
    assert after.qualified_count == len(changed)
    if len(changed) <= 5:
        assert {candidate.route_id for candidate in after.candidates} == changed
    else:
        assert after.status == "over_k_unranked"


def test_live_policy_revocation_and_snapshot_rebuild_fail_closed() -> None:
    """Current authority is rechecked even when the source index is pinned."""
    from schemarouter import AuthorizationPolicy, PrincipalContext
    from schemarouter.errors import PolicyViolationError
    from scripts.benchmark_native_fork_fieldgroup_e0 import (
        ACTOR, GROUP, ALIASES, build_fixture,
    )

    router = build_fixture(500, mixed_scope=True)
    index = NativeSchemaPostingIndex.build(router.registry)
    initial = index.lookup(router, ALIASES[0], principal=ACTOR, group=GROUP)
    assert initial.registry_version == index.registry_version
    assert initial.index_snapshot_id == index.snapshot_id

    # The same immutable source snapshot cannot grant access after revocation.
    router.authorization_policy = AuthorizationPolicy(default_effect="deny")
    revoked = index.lookup(router, ALIASES[0], principal=ACTOR, group=GROUP)
    assert revoked.qualified_count == 0
    assert revoked.candidates == ()
    stranger = PrincipalContext(subject="unauthorized", roles=("outsider",))
    denied = index.lookup(router, ALIASES[0], principal=stranger, group=GROUP)
    assert denied.qualified_count == 0
    assert denied.candidates == ()

    # Registry mutations invalidate the old index, rather than silently
    # returning candidates from the stale snapshot.
    router.registry.unregister("fork_status")
    with pytest.raises(PolicyViolationError, match="stale"):
        index.lookup(router, ALIASES[0], principal=ACTOR, group=GROUP)
    rebuilt = NativeSchemaPostingIndex.build(router.registry)
    assert rebuilt.snapshot_id != index.snapshot_id
    assert "fork_status.read" not in rebuilt.route_locations
