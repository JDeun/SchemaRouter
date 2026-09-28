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
    CONFIRM_ROUTE_SPECS as V6F_CONFIRM_ROUTE_SPECS,
)
from benchmarks.operation_routing_v6f_catalog import (  # noqa: E402
    DEV_ROUTE_SPECS as V6F_DEV_ROUTE_SPECS,
)
from benchmarks.operation_routing_v6g_catalog import (  # noqa: E402
    CONFIRM_ROUTE_SPECS,
    DEV_ROUTE_SPECS,
)
from scripts.generate_operation_routing_v6a import build as build_v6a  # noqa: E402
from scripts.generate_operation_routing_v6b import build as build_v6b  # noqa: E402
from scripts.generate_operation_routing_v6c import build as build_v6c  # noqa: E402
from scripts.generate_operation_routing_v6d import build as build_v6d  # noqa: E402
from scripts.generate_operation_routing_v6e import build as build_v6e  # noqa: E402
from scripts.generate_operation_routing_v6f import build as build_v6f  # noqa: E402
from scripts.generate_operation_routing_v6g import build  # noqa: E402


def test_v6g_preregistration_is_bound_to_issue_409() -> None:
    data = json.loads(
        (
            ROOT
            / "benchmarks"
            / "operation-routing-v6g-gte-positive-retriever-preregistration.json"
        ).read_text(encoding="utf-8")
    )
    assert data["issue"] == 409
    assert data["experiment"] == "frozen-gte-multilingual-positive-route-selector-v1"
    selector = data["positive_selector"]
    assert selector["model"] == "Alibaba-NLP/gte-multilingual-base"
    assert selector["revision"] == "087a024525fd6e2fe749cb4679d218d8bcc95bdd"
    assert selector["schema_weight"] == 0.25
    assert selector["action_weight"] == 0.75
    assert selector["authority"] == "sole positive route selector in V6G"
    assert selector["bge_fusion"] is False
    assert selector["bge_consensus"] is False
    assert selector["reranker"] is False
    assert selector["abstention"] is False


def test_v6g_route_identities_are_disjoint_from_v6a_through_v6f() -> None:
    v6g = {spec.route_id for spec in (*DEV_ROUTE_SPECS, *CONFIRM_ROUTE_SPECS)}
    for prior_specs in (
        (*V6A_DEV_ROUTE_SPECS, *V6A_CONFIRM_ROUTE_SPECS),
        (*V6B_DEV_ROUTE_SPECS, *V6B_CONFIRM_ROUTE_SPECS),
        (*V6C_DEV_ROUTE_SPECS, *V6C_CONFIRM_ROUTE_SPECS),
        (*V6D_DEV_ROUTE_SPECS, *V6D_CONFIRM_ROUTE_SPECS),
        (*V6E_DEV_ROUTE_SPECS, *V6E_CONFIRM_ROUTE_SPECS),
        (*V6F_DEV_ROUTE_SPECS, *V6F_CONFIRM_ROUTE_SPECS),
    ):
        assert v6g.isdisjoint({spec.route_id for spec in prior_specs})


def test_v6g_supported_only_counts_and_identities() -> None:
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


def test_v6g_query_identities_are_disjoint_from_v6a_through_v6f() -> None:
    v6g_queries: set[str] = set()
    for role in ("development", "confirmation"):
        rows, _ = build(role)
        v6g_queries.update(str(row["query"]) for row in rows)

    for builder in (
        build_v6a,
        build_v6b,
        build_v6c,
        build_v6d,
        build_v6e,
        build_v6f,
    ):
        prior_queries: set[str] = set()
        for role in ("development", "confirmation"):
            rows, _ = builder(role)
            prior_queries.update(str(row["query"]) for row in rows)
        assert v6g_queries.isdisjoint(prior_queries)


def test_v6g_expected_routes_match_frozen_specs() -> None:
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
