from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.generate_operation_routing_v5d import build  # noqa: E402


def test_v5d_corpora_are_deterministic_and_disjoint() -> None:
    dev_a, dev_manifest_a = build("development")
    dev_b, dev_manifest_b = build("development")
    confirm, confirm_manifest = build("confirmation")

    assert dev_a == dev_b
    assert dev_manifest_a == dev_manifest_b
    assert len(dev_manifest_a["corpus_sha256"]) == 64
    assert len(confirm_manifest["corpus_sha256"]) == 64

    dev_routes = {row["expected"] for row in dev_a if row["expected"] is not None}
    confirm_routes = {
        row["expected"]
        for row in confirm
        if row["expected"] is not None
    }
    assert dev_routes.isdisjoint(confirm_routes)


def test_v5d_corpora_cover_required_surfaces() -> None:
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


def test_v5d_does_not_reuse_prior_route_identities() -> None:
    forbidden = {
        "weather.current",
        "materials.search",
        "shipments.status",
        "contacts_api.alpha_17",
        "profiles_api.r17",
        "mailbox_ops.m11",
        "cases_api.c17",
        "catalog_ops.k11",
        "accounts_api.a17",
        "library_ops.l10",
    }
    for role in ("development", "confirmation"):
        rows, _ = build(role)
        used = {row["expected"] for row in rows if row["expected"] is not None}
        assert used.isdisjoint(forbidden)
