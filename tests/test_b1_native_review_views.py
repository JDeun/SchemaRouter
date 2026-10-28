"""B1 regression: immutable, deterministic catalog review cursor accelerators.

These structural checks are intentionally authorization-neutral. Authorization
and DataScope are enforced when a current-scoped review is requested.
"""
from __future__ import annotations

import pytest

from schemarouter.native_semantic_index import (
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
    from schemarouter import PrincipalContext
    from scripts.benchmark_native_fork_fieldgroup_e0 import build_fixture
    from scripts.benchmark_native_review_pagination_b1 import benchmark_review_pages

    router = build_fixture(500)
    session = router.prepare_field_routing()
    report = benchmark_review_pages(
        session,
        principal=PrincipalContext(subject="researcher", roles=("analyst",)),
        limit=64,
    )
    assert report["source_snapshot"] == session.snapshot_id
    assert report["source_route_count"] == session.indexed_route_count
    assert report["reviewed_route_count"] <= report["source_route_count"]
    assert report["reviewed_route_count"] > 0
    assert report["page_count"] >= 1
    assert report["serialized_page_bytes"] > 0
