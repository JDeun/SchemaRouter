"""#1560: original-source fork benchmark telemetry and oracle E0 contracts."""
from __future__ import annotations

import pytest

from schemarouter import AuthorizationPolicy, AuthorizationRule
from schemarouter.native_graph_index import NativeSchemaGraphIndex
from schemarouter.native_semantic_index import NativeSchemaPostingIndex
from scripts.benchmark_native_fork_fieldgroup_e0 import (
    ACTOR,
    ALIASES,
    EVIDENCE,
    GROUP,
    MIXED_DECOY_COUNT,
    benchmark,
    build_fixture,
    exhaustive_source_fork_reference,
)


def test_native_fork_500_source_index_matches_original_exhaustive_scan():
    router = build_fixture(500)
    assert router.registry.version == 500
    assert exhaustive_source_fork_reference(router) == (
        ("fork_origin.read", "fork_status.read", "fork_owner.read"),
    )


def test_native_fork_500_benchmark_reports_only_limited_e0_evidence():
    result = benchmark(registered_routes=500, iterations=10)
    assert result["evidence_tier"] == EVIDENCE
    assert result["independent_e2_qualified"] is False
    assert result["registered_native_routes"] == 500
    assert result["exhaustive_original_source_forks"] == 1
    assert result["verified_source_pinned_forks"] == 1
    assert result["en_ko_ja_exact_fieldgroup_parity"] is True
    assert result["same_snapshot_health_revocation_refused"] is True
    assert result["schema_execution_authority"] is False
    assert result["strict_k"] == 5
    assert result["sample_count"] == 10
    for label in ("query_wall_ms", "query_process_cpu_ms"):
        for key in ("p50", "p95", "p99"):
            assert result[label][key] >= 0
    assert result["peak_process_rss_kib"] > 0
    assert result["limitations"]


@pytest.mark.parametrize("size", (500, 5000))
def test_native_fork_mixed_scope_source_decoys_match_original_oracle(size):
    router = build_fixture(size, mixed_scope=True)
    assert router.registry.version == size
    assert exhaustive_source_fork_reference(router) == (
        ("fork_origin.read", "fork_status.read", "fork_owner.read"),
    )
    denied = router.registry.get("fork_status_denied")
    hidden = router.registry.get("fork_owner_hidden")
    assert not router._authorization_predicate(ACTOR)(denied, denied.endpoint("read"))
    visible = router._data_scope_endpoint_view(ACTOR, hidden, hidden.endpoint("read"))
    assert visible is None  # Entire scoped route disappears with its sole hidden field.
    index = NativeSchemaGraphIndex.build(NativeSchemaPostingIndex.build(router.registry))
    for query in ALIASES:
        found = index.lookup_shared_root_forks(
            router, query, group=GROUP, principal=ACTOR,
        )
        assert found.status == "complete"
        assert found.qualified_fork_count == 1
        assert found.candidates[0].branch_route_ids == (
            "fork_status.read", "fork_owner.read",
        )
    # A policy flip on the SAME built index must remove the public fork.
    router.authorization_policy = AuthorizationPolicy(
        default_effect="deny",
        rules=(AuthorizationRule(
            effect="allow", operation="fork_status.read", roles_any=("reader",),
        ),),
    )
    refused = index.lookup_shared_root_forks(
        router, ALIASES[0], group=GROUP, principal=ACTOR,
    )
    assert refused.status == "no_proven_hit" and refused.candidates == ()


def test_mixed_scope_cpu_telemetry_stays_explicitly_synthetic():
    measured = benchmark(registered_routes=500, iterations=10, mixed_scope=True)
    assert measured["adversarial_mixed_scope"] is True
    assert measured["confusable_source_routes"] == MIXED_DECOY_COUNT
    assert measured["registered_native_routes"] == 500
    assert measured["verified_source_pinned_forks"] == 1
    assert measured["independent_e2_qualified"] is False


@pytest.mark.parametrize("size", (0, 499, 501, 5001, True))
def test_native_fork_benchmark_rejects_non_preregistered_catalogs(size):
    with pytest.raises(ValueError, match="500/5000"):
        build_fixture(size)


@pytest.mark.parametrize("count", (0, 9, 101, True, 10.5))
def test_native_fork_benchmark_rejects_invalid_sample_count(count):
    with pytest.raises(ValueError, match="bounded E0"):
        benchmark(registered_routes=500, iterations=count)


def test_native_fork_fixture_rejects_non_boolean_mixed_scope():
    with pytest.raises(ValueError, match="mixed-scope"):
        build_fixture(500, mixed_scope="true")
