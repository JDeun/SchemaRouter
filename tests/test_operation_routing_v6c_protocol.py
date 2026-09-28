from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmarks.operation_routing_v6b_catalog import (  # noqa: E402
    CONFIRM_ROUTE_SPECS as V6B_CONFIRM_ROUTE_SPECS,
)
from benchmarks.operation_routing_v6b_catalog import (  # noqa: E402
    DEV_ROUTE_SPECS as V6B_DEV_ROUTE_SPECS,
)
from benchmarks.operation_routing_v6c_catalog import (  # noqa: E402
    CONFIRM_ROUTE_SPECS,
    DEV_ROUTE_SPECS,
)
from scripts.generate_operation_routing_v6a import build as build_v6a  # noqa: E402
from scripts.generate_operation_routing_v6b import build as build_v6b  # noqa: E402
from scripts.generate_operation_routing_v6c import build  # noqa: E402


def test_v6c_preregistration_is_bound_to_issue_397() -> None:
    data = json.loads(
        (ROOT / "benchmarks" / "operation-routing-v6c-density-ratio-preregistration.json")
        .read_text(encoding="utf-8")
    )
    assert data["issue"] == 397
    assert data["experiment"] == "schema-derived-tied-diagonal-gaussian-density-ratio-v1"
    assert data["density_model"]["decision_threshold"] == 0.0
    assert data["density_model"]["variance_floor"] == 1e-6
    assert data["density_model"]["projection"] is None
    assert data["authority"]["positive_rerank"] is False
    assert data["authority"]["endpoint_switch"] is False


def test_v6c_route_identities_are_disjoint_from_v6b() -> None:
    v6c = {spec.route_id for spec in (*DEV_ROUTE_SPECS, *CONFIRM_ROUTE_SPECS)}
    v6b = {
        spec.route_id
        for spec in (*V6B_DEV_ROUTE_SPECS, *V6B_CONFIRM_ROUTE_SPECS)
    }
    assert v6c.isdisjoint(v6b)


def test_v6c_dev_and_confirmation_counts_and_query_identities() -> None:
    dev, dev_manifest = build("development")
    confirm, confirm_manifest = build("confirmation")

    for rows, manifest in ((dev, dev_manifest), (confirm, confirm_manifest)):
        assert len(rows) == 552
        assert manifest["supported_cases"] == 228
        assert manifest["near_domain_cases"] == 252
        assert manifest["out_of_domain_cases"] == 72
        assert manifest["route_count"] == 19
        assert manifest["tool_count"] == 7
        assert manifest["synthetic_positives_per_route"] == 18
        assert set(manifest["adapters"]) == {"native", "openapi", "mcp"}
        assert manifest["corpus_sha256"]

    dev_queries = {row["query"] for row in dev}
    confirm_queries = {row["query"] for row in confirm}
    assert dev_queries.isdisjoint(confirm_queries)


def test_v6c_query_identities_are_disjoint_from_v6a_and_v6b() -> None:
    v6c_queries: set[str] = set()
    for role in ("development", "confirmation"):
        rows, _ = build(role)
        v6c_queries.update(str(row["query"]) for row in rows)

    for builder in (build_v6a, build_v6b):
        prior_queries: set[str] = set()
        for role in ("development", "confirmation"):
            rows, _ = builder(role)
            prior_queries.update(str(row["query"]) for row in rows)
        assert v6c_queries.isdisjoint(prior_queries)


def test_v6c_expected_routes_match_frozen_specs() -> None:
    for role, specs in (
        ("development", DEV_ROUTE_SPECS),
        ("confirmation", CONFIRM_ROUTE_SPECS),
    ):
        rows, _ = build(role)
        expected_routes = {
            row["expected"]
            for row in rows
            if row["expected"] is not None
        }
        assert expected_routes == {spec.route_id for spec in specs}
