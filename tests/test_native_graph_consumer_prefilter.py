"""Guard structural posting prefilter before native source materialization."""
from __future__ import annotations

import pytest

from schemarouter.native_graph_index import NativeSchemaGraphIndex
from schemarouter.native_semantic_index import NativeSchemaPostingIndex
from scripts.benchmark_indexed_g5_selectivity_e0 import (
    BROAD_GROUP,
    BROAD_QUERY,
    benchmark_selectivity,
)
from scripts.benchmark_indexed_native_graph_g5_cpu_e0 import (
    GROUP,
    PRINCIPAL,
    QUERY,
    _synthetic_router,
)


def test_broad_semantic_output_without_canonical_consumer_makes_no_tool_get(
    monkeypatch,
):
    router = _synthetic_router(350)
    idx = NativeSchemaGraphIndex.build(
        NativeSchemaPostingIndex.build(router.registry),
    )
    assert len(idx.field_index.postings["research.label"]) == 350
    assert idx.native_consumer_count == 1
    assert idx.edge_consumer_routes == frozenset({"case_service.read"})
    assert all(
        route_id not in idx.edge_consumer_routes
        for route_id in idx.field_index.postings["research.label"]
    )

    def forbidden(key):
        pytest.fail(f"nonconsumer registry materialized: {key}")

    monkeypatch.setattr(router.registry, "get", forbidden)
    result = idx.lookup(
        router, BROAD_QUERY, group=BROAD_GROUP, principal=PRINCIPAL,
    )
    assert result.status == "no_proven_hit"
    assert result.qualified_path_count == 0
    assert result.candidates == ()


def test_canonical_target_and_root_still_verified_in_original_registry(
    monkeypatch,
):
    router = _synthetic_router(200)
    idx = NativeSchemaGraphIndex.build(
        NativeSchemaPostingIndex.build(router.registry),
    )
    fetched: list[str] = []
    original = router.registry.get

    def recorded(key):
        fetched.append(key)
        return original(key)

    monkeypatch.setattr(router.registry, "get", recorded)
    result = idx.lookup(router, QUERY, group=GROUP, principal=PRINCIPAL)
    assert result.status == "complete"
    assert result.qualified_path_count == 1
    assert [(x.producer_route_id, x.consumer_route_id)
            for x in result.candidates] == [
        ("contact_directory.read", "case_service.read"),
    ]
    assert fetched == ["case_service", "contact_directory"]


def test_paired_selectivity_matrix_preserves_one_five_overflow_and_denials():
    sample = benchmark_selectivity(
        noise_routes=50, iterations=10, broad_iterations=2,
    )
    scenarios = sample["scenarios"]
    assert scenarios["one_authorized"]["verified_path_count"] == 1
    assert scenarios["five_authorized"]["verified_path_count"] == 5
    assert scenarios["seven_eligible_overflow"]["status"] == "over_k_unranked"
    assert scenarios["seven_eligible_overflow"]["returned_path_count"] == 0
    assert scenarios["root_denied"]["verified_path_count"] == 0
    assert scenarios["root_identifier_hidden"]["verified_path_count"] == 0
    assert scenarios["two_consumers_unavailable"]["verified_path_count"] == 5
    assert scenarios["broad_semantic_no_path"]["verified_path_count"] == 0
