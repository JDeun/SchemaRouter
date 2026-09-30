from __future__ import annotations

import json
from pathlib import Path


FIXTURE = Path(__file__).parent / "fixtures" / "domain_ingestion_matrix.json"


def _matrix() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_domain_ingestion_matrix_covers_required_real_world_services() -> None:
    matrix = _matrix()
    services = {item["id"]: item for item in matrix["services"]}

    assert {
        "materials_project",
        "duckduckgo",
        "tavily",
        "brave_search",
        "yahoo_finance",
        "arxiv",
        "crossref",
        "github_rest",
    } <= set(services)


def test_domain_ingestion_matrix_spans_multiple_domains() -> None:
    matrix = _matrix()
    domains = {item["domain"] for item in matrix["services"]}

    assert {
        "materials_science",
        "web_search",
        "finance",
        "scholarly_search",
        "scholarly_metadata",
        "developer_platform",
    } <= domains


def test_every_service_uses_only_supported_universal_ingestion_modes() -> None:
    matrix = _matrix()
    supported = set(matrix["universal_modes"])

    for service in matrix["services"]:
        assert service["primary_mode"] in supported
        assert set(service["access_modes"]) <= supported
        assert service["primary_mode"] in service["access_modes"]


def test_multi_access_services_are_marked_for_same_provider_fallback() -> None:
    matrix = _matrix()

    for service in matrix["services"]:
        if len(service["access_modes"]) > 1:
            assert service["same_provider_fallback"] is True


def test_materials_project_exercises_three_distinct_access_modes() -> None:
    matrix = _matrix()
    service = next(
        item
        for item in matrix["services"]
        if item["id"] == "materials_project"
    )

    assert {"openapi", "optimade", "python_callable"} <= set(
        service["access_modes"]
    )


def test_web_search_is_not_tied_to_one_vendor_or_ingestion_mode() -> None:
    matrix = _matrix()
    search_services = [
        item
        for item in matrix["services"]
        if item["domain"] == "web_search"
    ]

    assert {item["provider"] for item in search_services} == {
        "duckduckgo",
        "tavily",
        "brave",
    }
    modes = {
        mode
        for item in search_services
        for mode in item["access_modes"]
    }
    assert {"langchain_tool", "http_json", "python_callable"} <= modes


def test_scholarly_services_cover_agent_tool_openapi_and_http_paths() -> None:
    matrix = _matrix()
    scholarly = {
        item["id"]: set(item["access_modes"])
        for item in matrix["services"]
        if item["domain"].startswith("scholarly")
    }

    assert "langchain_tool" in scholarly["arxiv"]
    assert {"openapi", "http_json"} <= scholarly["crossref"]


def test_matrix_requires_common_canonical_contract_boundaries() -> None:
    matrix = _matrix()

    assert set(matrix["required_contract"]) == {
        "input_schema",
        "parameters",
        "output_schema",
        "output_fields",
        "provider",
        "access_mode",
        "execution_authority",
        "secret_boundary",
    }
