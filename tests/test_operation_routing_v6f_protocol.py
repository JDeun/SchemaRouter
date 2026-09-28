from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmarks.operation_routing_v6a_catalog import (  # noqa: E402
    CONFIRM_ROUTE_SPECS as V6A_CONFIRM_ROUTE_SPECS,
)
from benchmarks.operation_routing_v6a_catalog import (  # noqa: E402
    DEV_ROUTE_SPECS as V6A_DEV_ROUTE_SPECS,
)
from benchmarks.operation_routing_v6b_catalog import (  # noqa: E402
    CONFIRM_ROUTE_SPECS as V6B_CONFIRM_ROUTE_SPECS,
)
from benchmarks.operation_routing_v6b_catalog import (  # noqa: E402
    DEV_ROUTE_SPECS as V6B_DEV_ROUTE_SPECS,
)
from benchmarks.operation_routing_v6c_catalog import (  # noqa: E402
    CONFIRM_ROUTE_SPECS as V6C_CONFIRM_ROUTE_SPECS,
)
from benchmarks.operation_routing_v6c_catalog import (  # noqa: E402
    DEV_ROUTE_SPECS as V6C_DEV_ROUTE_SPECS,
)
from benchmarks.operation_routing_v6d_catalog import (  # noqa: E402
    CONFIRM_ROUTE_SPECS as V6D_CONFIRM_ROUTE_SPECS,
)
from benchmarks.operation_routing_v6d_catalog import (  # noqa: E402
    DEV_ROUTE_SPECS as V6D_DEV_ROUTE_SPECS,
)
from benchmarks.operation_routing_v6e_catalog import (  # noqa: E402
    CONFIRM_ROUTE_SPECS as V6E_CONFIRM_ROUTE_SPECS,
)
from benchmarks.operation_routing_v6e_catalog import (  # noqa: E402
    DEV_ROUTE_SPECS as V6E_DEV_ROUTE_SPECS,
)
from benchmarks.operation_routing_v6f_catalog import (  # noqa: E402
    CONFIRM_ROUTE_SPECS,
    DEV_ROUTE_SPECS,
)
from scripts.generate_operation_routing_v6a import build as build_v6a  # noqa: E402
from scripts.generate_operation_routing_v6b import build as build_v6b  # noqa: E402
from scripts.generate_operation_routing_v6c import build as build_v6c  # noqa: E402
from scripts.generate_operation_routing_v6d import build as build_v6d  # noqa: E402
from scripts.generate_operation_routing_v6e import build as build_v6e  # noqa: E402
from scripts.generate_operation_routing_v6f import build  # noqa: E402


def test_v6f_preregistration_is_bound_to_issue_406() -> None:
    data = json.loads(
        (
            ROOT
            / "benchmarks"
            / "operation-routing-v6f-tool-specialized-retriever-preregistration.json"
        ).read_text(encoding="utf-8")
    )
    assert data["issue"] == 406
    assert data["experiment"] == "tool-specialized-pretrained-route-retriever-v1"
    selector = data["positive_selector"]
    assert selector["model"] == "Lux1997/Tool-Embed-0.6B"
    assert selector["revision"] == "103d16d3593dec6c6f2217be620febb846932f6a"
    assert selector["pooling"] == "last_token"
    assert selector["authority"] == "sole positive route selector in V6F"
    assert selector["bge_fusion"] is False
    assert selector["reranker"] is False
    assert selector["abstention"] is False


def test_v6f_route_identities_are_disjoint_from_v6a_through_v6e() -> None:
    v6f = {spec.route_id for spec in (*DEV_ROUTE_SPECS, *CONFIRM_ROUTE_SPECS)}
    for prior_specs in (
        (*V6A_DEV_ROUTE_SPECS, *V6A_CONFIRM_ROUTE_SPECS),
        (*V6B_DEV_ROUTE_SPECS, *V6B_CONFIRM_ROUTE_SPECS),
        (*V6C_DEV_ROUTE_SPECS, *V6C_CONFIRM_ROUTE_SPECS),
        (*V6D_DEV_ROUTE_SPECS, *V6D_CONFIRM_ROUTE_SPECS),
        (*V6E_DEV_ROUTE_SPECS, *V6E_CONFIRM_ROUTE_SPECS),
    ):
        assert v6f.isdisjoint({spec.route_id for spec in prior_specs})


def test_v6f_supported_only_counts_and_identities() -> None:
    dev, dev_manifest = build("development")
    confirm, confirm_manifest = build("confirmation")

    for rows, manifest in ((dev, dev_manifest), (confirm, confirm_manifest)):
        assert len(rows) == 228
        assert manifest["supported_cases"] == 228
        assert manifest["near_domain_cases"] == 0
        assert manifest["out_of_domain_cases"] == 0
        assert manifest["route_count"] == 19
        assert manifest["tool_count"] == 7
        assert manifest["endpoint_counts"] == [2, 2, 3, 3, 3, 3, 3]
        assert set(manifest["adapters"]) == {"native", "openapi", "mcp"}
        assert all(row["expected"] is not None for row in rows)
        assert all(row["category"] == "supported" for row in rows)
        assert manifest["corpus_sha256"]

    assert {row["query"] for row in dev}.isdisjoint(
        {row["query"] for row in confirm}
    )


def test_v6f_query_identities_are_disjoint_from_v6a_through_v6e() -> None:
    v6f_queries: set[str] = set()
    for role in ("development", "confirmation"):
        rows, _ = build(role)
        v6f_queries.update(str(row["query"]) for row in rows)

    for builder in (build_v6a, build_v6b, build_v6c, build_v6d, build_v6e):
        prior_queries: set[str] = set()
        for role in ("development", "confirmation"):
            rows, _ = builder(role)
            prior_queries.update(str(row["query"]) for row in rows)
        assert v6f_queries.isdisjoint(prior_queries)


def test_v6f_expected_routes_match_frozen_specs() -> None:
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
