"""B1 regression: immutable, deterministic catalog review cursor accelerators.

These structural checks are intentionally authorization-neutral. Authorization
and DataScope are enforced when a current-scoped review is requested.
"""
from __future__ import annotations

import pytest

from schemarouter.native_semantic_index import (
    _native_review_cursor,
    _native_review_views,
    NativeSchemaPostingIndex,
    _indexable_semantic_field,
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
