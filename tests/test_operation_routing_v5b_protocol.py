from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.generate_operation_routing_v5b import build  # noqa: E402

PREREG = (
    ROOT
    / "benchmarks"
    / "operation-routing-v5b-semantic-ontology-preregistration.json"
)
ONTOLOGY = ROOT / "benchmarks" / "semantic_action_ontology.py"

OLD_ROUTE_IDS = {
    "weather.current",
    "weather.forecast",
    "materials.search",
    "materials.structure",
    "papers.search",
    "papers.citations",
    "finance.quote",
    "finance.history",
    "calendar.list",
    "calendar.create",
    "support.search",
    "support.create_ticket",
    "inventory.search",
    "inventory.update",
    "users.lookup",
    "users.update",
    "shipments.status",
    "shipments.eta",
    "contacts_api.alpha_17",
    "contacts_api.beta_23",
    "contacts_api.gamma_41",
    "media_ops.x17",
    "media_ops.q9",
    "media_ops.r2",
    "media_ops.z8",
    "media_ops.m4",
    "reports.list",
    "reports.export",
    "orders.lookup",
    "orders.update",
    "orders.cancel",
    "orders.refund",
    "devices.status",
    "devices.restart",
    "parcels_api.p11",
    "parcels_api.p22",
    "parcels_api.p33",
    "documents_ops.d1",
    "documents_ops.d2",
    "documents_ops.d3",
    "documents_ops.d4",
    "documents_ops.d5",
    "alerts.list",
    "alerts.create",
    "alerts.update",
    "alerts.delete",
    "subscriptions.retrieve",
    "subscriptions.update",
    "subscriptions.cancel",
    "jobs.list",
    "jobs.restart",
    "jobs.cancel",
    "analytics.current",
    "analytics.history",
    "analytics.forecast",
}


def test_preregistration_is_semantic_only_and_threshold_free() -> None:
    data = json.loads(PREREG.read_text(encoding="utf-8"))

    assert data["issue"] == 349
    ontology = data["action_ontology"]
    assert ontology["selection"] == "single argmax class"
    assert ontology["threshold"] is None
    assert ontology["margin_threshold"] is None
    assert ontology["learned_head"] is False
    authority = data["route_authority"]
    assert authority["cross_tool_fallback"] is False
    assert authority["pseudo_route"] is False
    assert authority["route_specific_thresholds"] is False


def test_new_corpora_are_disjoint_from_prior_route_identities() -> None:
    for role in ("development", "confirmation"):
        rows, _ = build(role)
        routes = {
            row["expected"]
            for row in rows
            if row["expected"] is not None
        }
        assert routes.isdisjoint(OLD_ROUTE_IDS)


def test_new_development_and_confirmation_are_mutually_disjoint() -> None:
    dev_rows, dev_manifest = build("development")
    confirm_rows, confirm_manifest = build("confirmation")

    dev_routes = {
        row["expected"]
        for row in dev_rows
        if row["expected"] is not None
    }
    confirm_routes = {
        row["expected"]
        for row in confirm_rows
        if row["expected"] is not None
    }

    assert dev_routes.isdisjoint(confirm_routes)
    assert dev_manifest["route_count"] == 18
    assert confirm_manifest["route_count"] == 22
    assert dev_manifest["adapters"] == ["mcp", "native", "openapi"]
    assert confirm_manifest["adapters"] == ["mcp", "native", "openapi"]


def test_v5b_corpus_sizes_and_categories_are_frozen_by_generator() -> None:
    expected = {
        "development": {
            "case_count": 720,
            "supported_cases": 216,
            "near_domain_cases": 432,
            "out_of_domain_cases": 72,
        },
        "confirmation": {
            "case_count": 768,
            "supported_cases": 264,
            "near_domain_cases": 432,
            "out_of_domain_cases": 72,
        },
    }
    for role, counts in expected.items():
        rows, manifest = build(role)
        assert len(rows) == counts["case_count"]
        for key, value in counts.items():
            assert manifest[key] == value
        assert {row["language"] for row in rows} == {
            "en",
            "ko",
            "es",
            "ja",
            "de",
            "mixed",
        }
        assert {row["category"] for row in rows} == {
            "supported",
            "near_domain_unsupported_operation",
            "out_of_domain",
        }
        assert len({row["id"] for row in rows}) == len(rows)
        assert len(manifest["corpus_sha256"]) == 64


def test_v5b_generator_is_deterministic() -> None:
    first_rows, first_manifest = build("development")
    second_rows, second_manifest = build("development")
    assert first_rows == second_rows
    assert first_manifest == second_manifest


def test_ontology_source_contains_no_registered_route_ids() -> None:
    source = ONTOLOGY.read_text(encoding="utf-8")
    for route_id in OLD_ROUTE_IDS:
        assert route_id not in source
