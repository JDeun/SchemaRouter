"""B1 E0: nonempty 1/2-hop mixed-source graph churn acceptance tests."""

from __future__ import annotations

import pytest

from schemarouter import capability_graph, native_graph_index
from scripts.benchmark_native_heterogeneous_graph_churn_e0 import (
    EVIDENCE,
    _graph_source_fixture,
    _structural_witness,
    audit_heterogeneous_graph_churn,
)


@pytest.mark.parametrize("routes", (500, 5000))
def test_graph_churn_has_real_edges_and_exact_source_witnesses(routes: int) -> None:
    report = audit_heterogeneous_graph_churn(routes)
    assert report["evidence_tier"] == EVIDENCE
    assert report["registered_source_routes"] == routes
    assert report["source_type_count"] == 4
    assert report["graph_edge_counts"] == [3, 2, 3, 1, 3]
    assert report["source_snapshot_count"] == 5
    assert report["registry_version_count"] == 5
    assert report["stale_index_rejections"] == 4
    assert report["journal_and_full_rebuild_exact_parity"] is True
    assert report["independent_edge_oracle_checked"] is True
    assert report["authorized_path_oracle_checked"] is True
    assert report["one_hop_checks"] == 180
    assert report["two_hop_checks"] == 180
    assert report["same_predicate_health_flip_checks"] == 4
    assert report["independent_e2_qualified"] is False
    assert report["source_gold_verified"] is False
    assert report["default_routing_changed"] is False
    assert all(report["query_wall_ms"][key] >= 0 for key in ("p50", "p95", "p99"))


def test_source_fixture_proves_three_nonempty_typed_edges() -> None:
    router = _graph_source_fixture(500)
    assert len(router.registry.tools()) == 500
    assert _structural_witness(router) == (
        ("unrelated_00000.read", "unrelated_00001.read"),
        ("unrelated_00000.read", "unrelated_00003.read"),
        ("unrelated_00001.read", "unrelated_00002.read"),
    )


def test_common_mode_empty_graph_rebuild_cannot_fake_source_oracle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Even two identically wrong graph builds must fail the source-only oracle."""
    original = capability_graph.build_capability_dependency_graph

    def forged_empty_graph(contracts: object):
        built = original(contracts)  # type: ignore[arg-type]
        return built.model_copy(update={"edges": ()})

    monkeypatch.setattr(
        native_graph_index, "build_capability_dependency_graph", forged_empty_graph,
    )
    with pytest.raises(AssertionError, match="source edge oracle"):
        audit_heterogeneous_graph_churn(500)


@pytest.mark.parametrize("routes", (0, 499, 501, 5001, True))
def test_graph_churn_rejects_out_of_scope_route_count(routes: object) -> None:
    with pytest.raises(ValueError, match="500/5000"):
        audit_heterogeneous_graph_churn(routes)  # type: ignore[arg-type]
