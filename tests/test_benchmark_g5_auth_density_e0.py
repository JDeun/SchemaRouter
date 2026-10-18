"""Paired G5 density metrics: one registry/index, no gold in selectors."""
from __future__ import annotations

import json

import pytest

from scripts.benchmark_g5_auth_density_e0 import (
    DENIED_TYPED_DISTRACTORS,
    SCENARIOS,
    _build_shared_density_source,
    benchmark_density_matrix,
)
from schemarouter import PrincipalContext
from schemarouter.native_graph_index import NativeSchemaGraphIndex
from schemarouter.native_semantic_index import NativeSchemaPostingIndex
from scripts.benchmark_indexed_native_graph_g5_cpu_e0 import GROUP, QUERY


def test_shared_index_authorizes_zero_one_five_six_without_leaking_denied_routes():
    router = _build_shared_density_source(13)
    idx = NativeSchemaGraphIndex.build(
        NativeSchemaPostingIndex.build(router.registry),
    )
    assert idx.field_index.indexed_route_count == 44
    assert idx.native_root_count == 1
    assert idx.native_consumer_count == 30
    for role, expected in SCENARIOS:
        result = idx.lookup(
            router, QUERY, group=GROUP,
            principal=PrincipalContext(subject="synthetic", roles=(role,)),
        )
        assert result.qualified_path_count == expected
        assert result.requested_k == 5
        assert result.status == (
            "no_proven_hit" if expected == 0
            else "over_k_unranked" if expected == 6 else "complete"
        )
        assert len(result.candidates) == (0 if expected == 6 else expected)
        assert all(not x.consumer_route_id.startswith("denied_")
                   for x in result.candidates)


def test_scenario_aggregation_has_bounded_telemetry_without_route_or_gold():
    report = benchmark_density_matrix(noise_routes=12, iterations=12)
    assert report["independent_e2_qualified"] is False
    assert report["frozen_query_and_source"] is True
    assert report["one_index_shared_across_principals"] is True
    assert report["synthetic_registered_routes"] == 43
    assert report["typed_denied_distractors"] == DENIED_TYPED_DISTRACTORS
    assert report["measured_queries_per_scenario"] == 12
    assert report["strict_k"] == 5
    assert report["index_build_wall_ms"] >= 0
    assert report["peak_process_rss_kib"] > 0
    for role, expected in SCENARIOS:
        row = report["scenario_metrics"][role]
        assert row["expected_and_verified_authorized_paths"] == expected
        assert row["visible_candidates"] == (0 if expected == 6 else expected)
        assert row["typed_denied_distractors"] == DENIED_TYPED_DISTRACTORS
        for key in ("query_wall_ms", "query_process_cpu_ms"):
            timing = row[key]
            assert 0 <= timing["p50"] <= timing["p95"] <= timing["p99"]
    text = json.dumps(report, ensure_ascii=False)
    for canary in (
        "denied_00", "eligible_00", "case_service.read",
        "contact_directory", "customer_id", "required_routes",
    ):
        assert canary not in text


@pytest.mark.parametrize("noise,runs", (
    (-1, 10), (10001, 10), (True, 10),
    (0, 0), (0, 9), (0, 201), (0, 12.0),
))
def test_reject_unbounded_or_invalid_density_benchmark(noise, runs):
    with pytest.raises(ValueError, match="bounded native graph density"):
        benchmark_density_matrix(noise_routes=noise, iterations=runs)


def test_all_principals_share_exact_graph_source_snapshot_and_query():
    router = _build_shared_density_source(10)
    graph = NativeSchemaGraphIndex.build(
        NativeSchemaPostingIndex.build(router.registry),
    )
    snapshot = graph.field_index.snapshot_id
    for role, _ in SCENARIOS:
        _ = graph.lookup(
            router, QUERY, group=GROUP,
            principal=PrincipalContext(subject="synthetic", roles=(role,)),
        )
        assert graph.field_index.snapshot_id == snapshot
