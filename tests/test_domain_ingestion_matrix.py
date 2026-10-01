from __future__ import annotations

import json
from pathlib import Path

from schemarouter import SchemaRouter


FIXTURE = Path(__file__).parent / "fixtures" / "domain_ingestion_matrix.json"


def _matrix() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_required_real_world_services_are_covered() -> None:
    services = {item["id"]: item for item in _matrix()["services"]}

    assert {
        "materials_project",
        "duckduckgo",
        "tavily",
        "brave_search",
        "yahoo_finance",
        "arxiv",
        "crossref",
        "github_rest",
        "graphql_business_api",
        "odata_enterprise_api",
        "jsonrpc_service",
    } <= set(services)


def test_matrix_spans_non_materials_domains() -> None:
    domains = {item["domain"] for item in _matrix()["services"]}

    assert {
        "materials_science",
        "web_search",
        "finance",
        "scholarly_search",
        "scholarly_metadata",
        "developer_platform",
        "business_application",
        "enterprise_data",
        "rpc_service",
    } <= domains


def test_every_declared_mode_maps_to_a_real_public_ingestion_surface() -> None:
    matrix = _matrix()
    router = SchemaRouter()
    built_in_kinds = set(router.adapter_registry.kinds())

    for mode in matrix["universal_modes"]:
        api = mode["api"].removeprefix("SchemaRouter.")
        assert hasattr(SchemaRouter, api), mode
        kind = mode["kind"]
        if kind is not None:
            assert kind in built_in_kinds, mode


def test_every_service_uses_only_supported_universal_modes() -> None:
    matrix = _matrix()
    supported = {item["id"] for item in matrix["universal_modes"]}

    for service in matrix["services"]:
        assert service["preferred_mode"] in supported
        assert set(service["access_modes"]) <= supported
        assert service["preferred_mode"] in service["access_modes"]


def test_multi_access_services_are_explicit_same_provider_fallback_candidates() -> None:
    for service in _matrix()["services"]:
        if len(service["access_modes"]) > 1:
            assert service["same_provider_fallback"] is True


def test_materials_project_covers_multiple_native_access_paths() -> None:
    service = next(
        item
        for item in _matrix()["services"]
        if item["id"] == "materials_project"
    )

    assert {
        "openapi",
        "optimade",
        "python_callable",
        "bound_tool",
    } <= set(service["access_modes"])


def test_web_search_is_not_bound_to_one_vendor_or_protocol() -> None:
    search = [
        item
        for item in _matrix()["services"]
        if item["domain"] == "web_search"
    ]

    assert {item["provider"] for item in search} == {
        "duckduckgo",
        "tavily",
        "brave",
    }
    modes = {
        mode
        for service in search
        for mode in service["access_modes"]
    }
    assert {
        "langchain_tool",
        "http_json",
        "python_callable",
        "bound_tool",
    } <= modes


def test_scholarly_coverage_includes_tool_openapi_http_and_sdk_paths() -> None:
    scholarly = {
        item["id"]: set(item["access_modes"])
        for item in _matrix()["services"]
        if item["domain"].startswith("scholarly")
    }

    assert "langchain_tool" in scholarly["arxiv"]
    assert "bound_tool" in scholarly["arxiv"]
    assert {"openapi", "http_json", "bound_tool"} <= scholarly["crossref"]


def test_protocol_specific_server_projection_paths_are_represented() -> None:
    services = {item["id"]: item for item in _matrix()["services"]}

    assert services["graphql_business_api"]["preferred_mode"] == "graphql"
    assert services["odata_enterprise_api"]["preferred_mode"] == "odata"
    assert services["jsonrpc_service"]["preferred_mode"] == "openrpc"


def test_every_service_records_required_operational_contract_dimensions() -> None:
    required = {
        "input_contract",
        "output_contract",
        "provider",
        "access_modes",
        "auth_boundary",
        "schema_drift",
        "semantic_metadata",
    }

    for service in _matrix()["services"]:
        assert required <= set(service), service["id"]


def test_common_contract_boundary_is_explicit() -> None:
    assert set(_matrix()["common_contract"]) == {
        "input_schema",
        "parameters",
        "output_schema",
        "output_fields",
        "provider",
        "access_mode",
        "execution_authority",
        "secret_boundary",
        "schema_drift",
    }
