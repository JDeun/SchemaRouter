from __future__ import annotations

from benchmarks.registry_capability_holdout import build_registry, cases, manifest
from schemarouter import InMemoryRegistry
from scripts.benchmark_decision_routing import reference_registry


def test_registration_holdout_routes_are_disjoint_from_canonical_registry() -> None:
    canonical = {
        f"{tool.key}.{endpoint.name}"
        for tool in reference_registry().tools()
        for endpoint in tool.endpoints
    }
    holdout_registry = build_registry()
    holdout = {
        f"{tool.key}.{endpoint.name}"
        for tool in holdout_registry.tools()
        for endpoint in tool.endpoints
    }

    assert canonical.isdisjoint(holdout)
    assert holdout


def test_registration_holdout_exercises_native_openapi_mcp_and_variable_width() -> None:
    data = manifest()
    assert data["tool_count"] == 4
    assert data["route_count"] == 12
    assert data["endpoint_counts"] == [1, 3, 3, 5]
    assert set(data["adapters"]) == {"mcp", "native", "openapi"}
    assert data["operation_aliases_required"] is False


def test_registration_holdout_has_supported_near_and_ood_in_six_languages() -> None:
    rows = cases()
    data = manifest()

    assert len(rows) == data["case_count"]
    assert data["supported_cases"] == 144
    assert data["near_domain_cases"] == 72
    assert data["out_of_domain_cases"] == 12
    assert data["languages"] == ["en", "ko", "es", "ja", "de", "mixed"]
    assert len({row["id"] for row in rows}) == len(rows)
    assert all(row["query"].strip() for row in rows)


def test_registration_registry_is_plain_in_memory_registry() -> None:
    registry = build_registry()
    assert isinstance(registry, InMemoryRegistry)
    assert all(tool.endpoints for tool in registry.tools())
