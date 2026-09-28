from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.generate_operation_routing_v5h import build  # noqa: E402


def test_v5h_corpora_are_deterministic() -> None:
    dev_a, manifest_a = build("development")
    dev_b, manifest_b = build("development")
    assert dev_a == dev_b
    assert manifest_a == manifest_b
    assert len(manifest_a["corpus_sha256"]) == 64


def test_v5h_expected_counts_and_surfaces() -> None:
    for role in ("development", "confirmation"):
        rows, manifest = build(role)
        assert manifest["case_count"] == 552
        assert manifest["supported_cases"] == 228
        assert manifest["near_domain_cases"] == 252
        assert manifest["out_of_domain_cases"] == 72
        assert manifest["route_count"] == 19
        assert manifest["tool_count"] == 7
        assert manifest["endpoint_counts"] == [2, 2, 3, 3, 3, 3, 3]
        assert manifest["adapters"] == ["mcp", "native", "openapi"]
        assert {row["category"] for row in rows} == {
            "supported",
            "near_domain_unsupported_operation",
            "out_of_domain",
        }
        assert {row["language"] for row in rows} == {
            "en",
            "ko",
            "es",
            "ja",
            "de",
            "mixed",
        }
        assert len({row["id"] for row in rows}) == len(rows)


def test_v5h_development_and_confirmation_routes_are_disjoint() -> None:
    dev, _ = build("development")
    confirm, _ = build("confirmation")
    dev_routes = {row["expected"] for row in dev if row["expected"] is not None}
    confirm_routes = {
        row["expected"]
        for row in confirm
        if row["expected"] is not None
    }
    assert dev_routes.isdisjoint(confirm_routes)


def test_v5h_does_not_reuse_prior_research_route_identities() -> None:
    forbidden = {
        "weather.current",
        "materials.search",
        "shipments.status",
        "contacts_api.alpha_17",
        "profiles_api.r17",
        "cases_api.c17",
        "license_records_api.l17",
        "knowledge_corpus_ops.c17",
        "registration_records_api.r17",
        "archive_catalog_ops.a17",
        "permits_api.p17",
        "applications_api.a17",
    }
    for role in ("development", "confirmation"):
        rows, _ = build(role)
        routes = {row["expected"] for row in rows if row["expected"] is not None}
        assert routes.isdisjoint(forbidden)
