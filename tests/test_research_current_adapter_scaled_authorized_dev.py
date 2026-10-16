"""Contract tests for 100/250/500 actual current-adapter authorized DEV."""
from __future__ import annotations

import pytest

from benchmarks.current_adapter_field_scope_dev_v1 import principal
from benchmarks.current_adapter_scaled_authorized_dev_v1 import (
    DENIED_VIEWER,
    SIZES,
    WIDTHS,
    authored_tasks,
    build_fixture,
)
from scripts.research_current_adapter_scaled_authorized_dev import (
    _measure,
    _tasks,
    _validate_retrieval,
    assess,
)
from scripts.research_v1_v2_paired_cpu_dev import frozen_genomes


def test_scaled_current_adapters_have_distinct_real_registered_routes() -> None:
    for size in SIZES:
        router, policy = build_fixture(size)
        items = [
            (tool, endpoint)
            for tool in router.registry.tools() for endpoint in tool.endpoints
        ]
        keys = {f"{tool.key}.{endpoint.name}" for tool, endpoint in items}
        assert len(items) == len(keys) == size
        adapters = {
            tool.execution_metadata.get("adapter")
            for tool, _ in items
        }
        providers = {tool.provider for tool, _ in items}
        assert {"openapi", "mcp"} <= adapters
        assert {"database", "vector", "graph"} <= providers
        viewer, editor = principal("viewer"), principal("editor")
        seen = {
            route: (tool, endpoint)
            for (tool, endpoint), route in (
                (item, f"{item[0].key}.{item[1].name}") for item in items
            )
        }
        for route in DENIED_VIEWER:
            tool, endpoint = seen[route]
            assert not policy.visible(viewer, tool, endpoint)
            assert policy.visible(editor, tool, endpoint)
        assert sum(policy.visible(viewer, t, e) for t, e in items) == size - 5


def test_query_gold_authoring_and_size_limits() -> None:
    tasks = _tasks()
    assert tasks == authored_tasks()
    assert len(tasks) == 27
    assert {t["language"] for t in tasks} == {"en", "ko", "ja"}
    for bad in (0, 10, 24, 99, 101, 1000, True, "500"):
        with pytest.raises(ValueError):
            build_fixture(bad)
    for bad in ((), (24,), (100, 100), (500, 99), (True,), (100, 500, 250, 100)):
        with pytest.raises(ValueError):
            assess(sizes=bad)


def test_authorized_fields_are_projected_before_ranker() -> None:
    router, policy = build_fixture(100)
    viewer, editor = principal("viewer"), principal("editor")
    catalog = {
        f"{t.key}.{e.name}": (t, e)
        for t in router.registry.tools() for e in t.endpoints
    }
    for role, who in (("viewer", viewer), ("editor", editor)):
        allowed = {
            route for route, (tool, endpoint) in catalog.items()
            if policy.visible(who, tool, endpoint)
        }
        _, proposed, _ = frozen_genomes()
        result = _measure(
            router, "synthetic parcel ledger audit_tag", who, allowed,
            width=64, weights=proposed["weights"],
        )
        assert len(result["all_candidate_ids"]) <= 64
        _validate_retrieval(
            router.retrieve_authorized(
                "synthetic parcel ledger audit_tag", principal=who, k=64,
            ).candidates,
            allowed, 64, role,
        )
        assert not (set(result["all_candidate_ids"]) - allowed)


def test_real_current_retrieve_authorized_paired_top5_dev() -> None:
    result = assess(sizes=(100,))
    assert result["registered_sizes"] == [100]
    assert result["candidate_widths"] == list(WIDTHS)
    assert len(result["cases"]) == 27
    assert result["actual_authorized_router_calls"] == 27 * 7
    assert result["required_router_calls_expected"] == 27 * 7
    assert result["scope"]["independent_confirmation"] is False
    assert result["scope"]["may_release"] is False
    assert result["scope"]["model_or_external_tools_executed"] is False
    assert len(result["by_scale_language_role"]) == 6
    for label, metrics in result["overall"].items():
        assert label in ("v1_k24", *(f"v3_k{k}" for k in WIDTHS))
        assert metrics["cases"] == 27
        assert metrics["unauthorized_candidate_count"] == 0
        assert metrics["required_routes_found"] <= metrics["supported"]
        assert 0 <= metrics["required_fields_found"] <= metrics["required_fields_total"]
        assert metrics["p95_retrieval_rerank_ms"] >= 0


def test_ranker_cannot_bypass_authorized_principal_scope() -> None:
    with pytest.raises(ValueError):
        _validate_retrieval(
            [type("Candidate", (), {"route_id": "billing.payInvoice"})()],
            {"billing.payInvoice"}, 5, "viewer",
        )
