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
from benchmarks.operation_routing_v6g_catalog import (  # noqa: E402
    CONFIRM_ROUTE_SPECS,
    DEV_ROUTE_SPECS,
    confirmation_registry,
    development_registry,
)
from benchmarks.schema_cross_encoder_membership import (  # noqa: E402
    RERANKER_MAX_LENGTH,
    RERANKER_MODEL,
    RERANKER_REVISION,
)
from scripts.generate_operation_routing_v6a import build as build_v6a  # noqa: E402
from scripts.generate_operation_routing_v6b import build as build_v6b  # noqa: E402
from scripts.generate_operation_routing_v6c import build as build_v6c  # noqa: E402
from scripts.generate_operation_routing_v6d import build as build_v6d  # noqa: E402
from scripts.generate_operation_routing_v6e import build as build_v6e  # noqa: E402
from scripts.generate_operation_routing_v6g import build  # noqa: E402

V6F_ROUTE_IDS = {
    "mandates_api.m14",
    "mandates_api.m25",
    "mandates_api.m36",
    "catalyst_index.n14",
    "catalyst_index.n25",
    "catalyst_index.n36",
    "parcels.send",
    "parcels.share",
    "briefs.export",
    "briefs.summarize",
    "briefs.merge",
    "workcells.restart",
    "workcells.execute",
    "allocations.create",
    "allocations.cancel",
    "allocations.refund",
    "youngs_modulus.current",
    "youngs_modulus.history",
    "youngs_modulus.forecast",
    "grants_api.p14",
    "grants_api.p25",
    "grants_api.p36",
    "powder_catalog.q14",
    "powder_catalog.q25",
    "powder_catalog.q36",
    "shipments.send",
    "shipments.share",
    "transcripts.export",
    "transcripts.translate",
    "transcripts.compare",
    "reactors.restart",
    "reactors.execute",
    "agreements.retrieve",
    "agreements.cancel",
    "agreements.refund",
    "electrical_resistivity.current",
    "electrical_resistivity.history",
    "electrical_resistivity.forecast",
}

V6F_PREFIXES = (
    "Route this concrete request: ",
    "이 구체적 요청을 라우팅해줘: ",
    "Enruta esta solicitud concreta: ",
    "この具体的な依頼をルーティングして: ",
    "Route diese konkrete Anfrage: ",
    "이 concrete request를 route해줘: ",
)


def test_v6g_preregistration_is_bound_to_issue_408() -> None:
    data = json.loads(
        (
            ROOT
            / "benchmarks"
            / "operation-routing-v6g-relative-cross-encoder-preregistration.json"
        ).read_text(encoding="utf-8")
    )
    assert data["issue"] == 408
    assert data["experiment"] == (
        "relative-multilingual-cross-encoder-capability-gate-v1"
    )
    membership = data["membership_model"]
    assert membership["model"] == RERANKER_MODEL
    assert membership["revision"] == RERANKER_REVISION
    assert membership["max_pair_tokens"] == RERANKER_MAX_LENGTH
    assert membership["probability_threshold"] is None
    assert membership["margin_threshold"] is None
    assert data["decision"]["tie"] == "preserve raw BGE top-1"
    assert data["decision"]["positive_rerank"] is False


def test_v6g_route_identities_are_disjoint_from_v6a_through_v6f() -> None:
    v6g = {spec.route_id for spec in (*DEV_ROUTE_SPECS, *CONFIRM_ROUTE_SPECS)}
    for prior_specs in (
        (*V6A_DEV_ROUTE_SPECS, *V6A_CONFIRM_ROUTE_SPECS),
        (*V6B_DEV_ROUTE_SPECS, *V6B_CONFIRM_ROUTE_SPECS),
        (*V6C_DEV_ROUTE_SPECS, *V6C_CONFIRM_ROUTE_SPECS),
        (*V6D_DEV_ROUTE_SPECS, *V6D_CONFIRM_ROUTE_SPECS),
        (*V6E_DEV_ROUTE_SPECS, *V6E_CONFIRM_ROUTE_SPECS),
    ):
        assert v6g.isdisjoint({spec.route_id for spec in prior_specs})
    assert v6g.isdisjoint(V6F_ROUTE_IDS)


def test_v6g_counts_adapters_and_dev_confirmation_disjointness() -> None:
    dev, dev_manifest = build("development")
    confirm, confirm_manifest = build("confirmation")

    for rows, manifest in ((dev, dev_manifest), (confirm, confirm_manifest)):
        assert len(rows) == 552
        assert manifest["supported_cases"] == 228
        assert manifest["near_domain_cases"] == 252
        assert manifest["out_of_domain_cases"] == 72
        assert manifest["route_count"] == 19
        assert manifest["tool_count"] == 7
        assert manifest["endpoint_counts"] == [2, 2, 3, 3, 3, 3, 3]
        assert set(manifest["adapters"]) == {"native", "openapi", "mcp"}
        assert manifest["supported_document_count"] == 19
        assert manifest["background_document_count"] == 16
        assert manifest["complement_document_count"] > 0
        assert manifest["corpus_sha256"]

    assert {row["query"] for row in dev}.isdisjoint(
        {row["query"] for row in confirm}
    )


def test_v6g_query_identities_are_disjoint_from_v6a_through_v6f() -> None:
    v6g_queries: set[str] = set()
    for role in ("development", "confirmation"):
        rows, _ = build(role)
        v6g_queries.update(str(row["query"]) for row in rows)

    for builder in (build_v6a, build_v6b, build_v6c, build_v6d, build_v6e):
        prior_queries: set[str] = set()
        for role in ("development", "confirmation"):
            rows, _ = builder(role)
            prior_queries.update(str(row["query"]) for row in rows)
        assert v6g_queries.isdisjoint(prior_queries)

    assert all(
        not query.startswith(V6F_PREFIXES)
        for query in v6g_queries
    )


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


def test_v6g_typed_material_fixtures_are_preserved() -> None:
    dev = development_registry()
    confirm = confirmation_registry()

    dev_tool = next(tool for tool in dev.tools() if tool.key == "modulus_observatory")
    dev_field = dev_tool.endpoints[0].output_fields[0]
    assert dev_field.semantic_id == "material.youngs_modulus"
    assert dev_field.unit == "GPa"
    assert dev_field.unit_normalization is not None
    assert dev_field.unit_normalization.canonical_unit == "Pa"
    assert dev_field.unit_normalization.dimension == "elastic_modulus"
    assert dev_field.unit_normalization.scale == 1_000_000_000.0

    confirm_tool = next(
        tool for tool in confirm.tools()
        if tool.key == "resistivity_observatory"
    )
    confirm_field = confirm_tool.endpoints[0].output_fields[0]
    assert confirm_field.semantic_id == "material.electrical_resistivity"
    assert confirm_field.unit == "Ω·m"
    assert confirm_field.unit_normalization is not None
    assert confirm_field.unit_normalization.canonical_unit == "Ω·m"
    assert confirm_field.unit_normalization.dimension == "electrical_resistivity"
    assert confirm_field.unit_normalization.scale == 1.0
