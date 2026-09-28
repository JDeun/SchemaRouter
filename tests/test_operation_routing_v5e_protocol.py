from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.generate_operation_routing_v5e import build  # noqa: E402


def test_v5e_corpora_are_deterministic() -> None:
    dev_a, manifest_a = build("development")
    dev_b, manifest_b = build("development")

    assert dev_a == dev_b
    assert manifest_a == manifest_b
    assert len(manifest_a["corpus_sha256"]) == 64


def test_v5e_required_surfaces_and_adapters() -> None:
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
        assert manifest["supported_cases"] == 228
        assert manifest["near_domain_cases"] == 252
        assert manifest["out_of_domain_cases"] == 72
        assert manifest["case_count"] == 552
        assert manifest["route_count"] == 19
        assert manifest["tool_count"] == 7
        assert manifest["endpoint_counts"] == [2, 2, 3, 3, 3, 3, 3]
        assert len({row["id"] for row in rows}) == len(rows)


def test_v5e_development_and_confirmation_are_identity_disjoint() -> None:
    dev, _ = build("development")
    confirm, _ = build("confirmation")

    dev_routes = {row["expected"] for row in dev if row["expected"] is not None}
    confirm_routes = {
        row["expected"]
        for row in confirm
        if row["expected"] is not None
    }
    assert dev_routes.isdisjoint(confirm_routes)


def test_v5e_does_not_reuse_recent_evaluated_route_identities() -> None:
    forbidden = {
        "incidents_api.i17",
        "repository_ops.r11",
        "handoff.send",
        "artifact_ops.export",
        "processes.restart",
        "enrollments.create",
        "traffic.current",
        "records_api.z17",
        "inventory_ops.v11",
        "collaboration.send",
        "content_pipeline.export",
        "runtime_jobs.restart",
        "warranties.retrieve",
        "load.current",
        "cases_api.c17",
        "catalog_ops.k11",
        "deliveries.send",
        "document_ops.export",
        "workers.restart",
        "membership.create",
        "demand.current",
        "profiles_api.r17",
        "mailbox_ops.m11",
        "bookings_api.b17",
        "archive_ops.a01",
        "weather.current",
        "materials.search",
        "contacts_api.alpha_17",
        "media_ops.x17",
    }

    for role in ("development", "confirmation"):
        rows, _ = build(role)
        routes = {row["expected"] for row in rows if row["expected"] is not None}
        assert routes.isdisjoint(forbidden)
