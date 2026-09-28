from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.generate_operation_routing_v5b import build  # noqa: E402


def test_v5b_corpora_are_deterministic_and_disjoint() -> None:
    dev_a, dev_manifest_a = build("development")
    dev_b, dev_manifest_b = build("development")
    confirm, confirm_manifest = build("confirmation")

    assert dev_a == dev_b
    assert dev_manifest_a == dev_manifest_b
    assert len(dev_manifest_a["corpus_sha256"]) == 64
    assert len(confirm_manifest["corpus_sha256"]) == 64

    dev_routes = {row["expected"] for row in dev_a if row["expected"] is not None}
    confirm_routes = {
        row["expected"] for row in confirm
        if row["expected"] is not None
    }
    assert dev_routes.isdisjoint(confirm_routes)


def test_v5b_corpora_cover_required_surfaces() -> None:
    for role in ("development", "confirmation"):
        rows, manifest = build(role)

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
        assert manifest["adapters"] == ["mcp", "native", "openapi"]
        assert manifest["supported_cases"] > 0
        assert manifest["near_domain_cases"] > 0
        assert manifest["out_of_domain_cases"] == 72
        assert len({row["id"] for row in rows}) == len(rows)


def test_v5b_does_not_reuse_0_11_or_347_routes() -> None:
    forbidden = {
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
        "documents_ops.d1",
        "alerts.list",
        "subscriptions.retrieve",
        "jobs.list",
        "analytics.current",
    }

    for role in ("development", "confirmation"):
        rows, _ = build(role)
        routes = {row["expected"] for row in rows if row["expected"] is not None}
        assert routes.isdisjoint(forbidden)
