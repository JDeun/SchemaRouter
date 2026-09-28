from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.generate_operation_routing_v5 import build_rows  # noqa: E402


def test_v5_development_and_confirmation_are_disjoint_and_versioned() -> None:
    dev_rows, dev_manifest = build_rows("development")
    confirm_rows, confirm_manifest = build_rows("confirmation")

    dev_routes = {row["expected"] for row in dev_rows if row["expected"] is not None}
    confirm_routes = {
        row["expected"]
        for row in confirm_rows
        if row["expected"] is not None
    }

    assert dev_routes.isdisjoint(confirm_routes)
    assert dev_manifest["route_count"] == 18
    assert confirm_manifest["route_count"] == 21
    assert dev_manifest["adapters"] == ["mcp", "native", "openapi"]
    assert confirm_manifest["adapters"] == ["mcp", "native", "openapi"]


def test_v5_corpora_cover_all_required_categories_and_languages() -> None:
    for role in ("development", "confirmation"):
        rows, manifest = build_rows(role)
        categories = {row["category"] for row in rows}
        languages = {row["language"] for row in rows}

        assert categories == {
            "supported",
            "near_domain_unsupported_operation",
            "out_of_domain",
        }
        assert languages == {"en", "ko", "es", "ja", "de", "mixed"}
        assert manifest["supported_cases"] > 0
        assert manifest["near_domain_cases"] > 0
        assert manifest["out_of_domain_cases"] > 0
        assert len({row["id"] for row in rows}) == len(rows)


def test_v5_generator_is_deterministic() -> None:
    rows_a, manifest_a = build_rows("development")
    rows_b, manifest_b = build_rows("development")
    assert rows_a == rows_b
    assert manifest_a == manifest_b
    assert len(manifest_a["corpus_sha256"]) == 64


def test_v5_does_not_reuse_0_11_reference_route_names() -> None:
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
    }
    for role in ("development", "confirmation"):
        rows, _ = build_rows(role)
        used = {row["expected"] for row in rows if row["expected"] is not None}
        assert used.isdisjoint(forbidden)
