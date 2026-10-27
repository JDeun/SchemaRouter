"""Provider-neutral B1 review benchmark checks actual public page receipts."""
from __future__ import annotations

from scripts.benchmark_native_fork_fieldgroup_e0 import ACTOR, build_fixture
from scripts.benchmark_native_review_pagination_b1 import benchmark_review_pages


def test_b1_review_benchmark_counts_unique_bounded_pages_and_measures_bytes():
    router = build_fixture(500)
    session = router.prepare_field_routing()
    report = benchmark_review_pages(
        session, principal=ACTOR, limit=32,
    )
    assert report["source_route_count"] == 500
    assert report["requested_page_size"] == 32
    assert report["page_count"] >= 2
    assert report["reviewed_route_count"] > 32
    assert report["serialized_page_bytes"] > report["reviewed_route_count"]
    assert report["page_latency_ms"]["p50"] > 0
    assert report["page_latency_ms"]["p50"] <= report["page_latency_ms"]["p95"]
    assert report["page_latency_ms"]["p95"] <= report["page_latency_ms"]["p99"]
    assert report["provenance"] == "SOURCE_OWNED_SYNTHETIC_REVIEW_B1_DEV"
