"""#1560 source-native indexed/direct parity measured separately from E2."""
from __future__ import annotations

import pytest

import scripts.benchmark_paper_indexed_direct_e0 as benchmark_module
from scripts.benchmark_paper_indexed_direct_e0 import benchmark


def test_paper_indexed_direct_benchmark_reports_verified_source_parity():
    result = benchmark(registered_routes=500, iterations=10)
    assert result["evidence"] == "E0_SYNTHETIC_INDEXED_PAPER_DIRECT_NOT_E2"
    assert result["registered_routes"] == 500
    assert result["status"] == "complete"
    assert result["route_ids"] == ["paper_complete.read"]
    assert result["output_fields"] == ["request_id", "status", "owner"]
    assert set(result["required_semantic_ids"]) == {
        "crm.fork_status", "crm.fork_owner",
    }
    assert result["index_build_ms"] > 0
    assert result["warm_ms"]["baseline"]["p50"] > 0
    assert result["warm_ms"]["indexed"]["p50"] > 0
    assert result["warm_ms"]["baseline"]["p95"] >= result["warm_ms"]["baseline"]["p50"]
    assert result["warm_ms"]["indexed"]["p95"] >= result["warm_ms"]["indexed"]["p50"]
    assert result["external_e2"] is False
    assert "answer_quality" not in result
    assert "token_savings" not in result


@pytest.mark.parametrize("size,iterations", [(499, 10), (500, 1), (500, True)])
def test_paper_indexed_direct_benchmark_refuses_unbounded_measurements(size, iterations):
    with pytest.raises(ValueError, match="500/5000 routes and 10-50 iterations"):
        benchmark(registered_routes=size, iterations=iterations)


def test_paper_indexed_direct_benchmark_rejects_non_linux_rss_units(monkeypatch):
    monkeypatch.setattr(benchmark_module.platform, "system", lambda: "Darwin")
    with pytest.raises(RuntimeError, match="Linux-only"):
        benchmark(registered_routes=500, iterations=10)


def test_paper_indexed_direct_fork_benchmark_preserves_original_three_route_join():
    result = benchmark(registered_routes=500, iterations=10, scenario="fork")
    assert result["scenario"] == "fork"
    assert result["status"] == "complete"
    assert set(result["route_ids"]) == {
        "fork_origin.read", "fork_status.read", "fork_owner.read",
    }
    assert result["field_projection_by_route"] == {
        "fork_origin.read": ["customer_id"],
        "fork_status.read": ["status"],
        "fork_owner.read": ["owner"],
    }
    assert result["warm_ms"]["indexed"]["p50"] > 0
    assert result["external_e2"] is False


def test_paper_indexed_direct_benchmark_refuses_unknown_scenario():
    with pytest.raises(ValueError, match="direct or fork"):
        benchmark(registered_routes=500, iterations=10, scenario="autonomous-agent")
