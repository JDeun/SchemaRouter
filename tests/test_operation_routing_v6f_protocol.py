from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmarks.operation_routing_v6a_catalog import (
    CONFIRM_ROUTE_SPECS as V6A_CONFIRM,
    DEV_ROUTE_SPECS as V6A_DEV,
)
from benchmarks.operation_routing_v6b_catalog import (
    CONFIRM_ROUTE_SPECS as V6B_CONFIRM,
    DEV_ROUTE_SPECS as V6B_DEV,
)
from benchmarks.operation_routing_v6c_catalog import (
    CONFIRM_ROUTE_SPECS as V6C_CONFIRM,
    DEV_ROUTE_SPECS as V6C_DEV,
)
from benchmarks.operation_routing_v6d_catalog import (
    CONFIRM_ROUTE_SPECS as V6D_CONFIRM,
    DEV_ROUTE_SPECS as V6D_DEV,
)
from benchmarks.operation_routing_v6e_catalog import (
    CONFIRM_ROUTE_SPECS as V6E_CONFIRM,
    DEV_ROUTE_SPECS as V6E_DEV,
)
from benchmarks.operation_routing_v6f_catalog import (
    CONFIRM_ROUTE_SPECS,
    DEV_ROUTE_SPECS,
)
from benchmarks.schema_naturalistic_operation_probe import load_naturalistic_bank
from scripts.generate_operation_routing_v6a import build as build_v6a
from scripts.generate_operation_routing_v6b import build as build_v6b
from scripts.generate_operation_routing_v6c import build as build_v6c
from scripts.generate_operation_routing_v6d import build as build_v6d
from scripts.generate_operation_routing_v6e import build as build_v6e
from scripts.generate_operation_routing_v6f import build


def test_v6f_preregistration_is_bound_to_issue_404() -> None:
    data = json.loads(
        (
            ROOT
            / "benchmarks"
            / "operation-routing-v6f-naturalistic-probe-preregistration.json"
        ).read_text(encoding="utf-8")
    )
    assert data["issue"] == 404
    assert data["experiment"] == (
        "naturalistic-generic-operation-linear-probe-membership-v1"
    )
    assert data["semantic_encoder"]["revision"] == (
        "e8f8c211226b894fcb81acc59f3b34ba3efd5f42"
    )
    assert data["probes"]["C"] == 1.0
    assert data["probes"]["solver"] == "lbfgs"
    assert data["probes"]["probability_threshold"] is None
    assert data["probes"]["margin_threshold"] is None
    assert data["route_authority"]["positive_rerank"] is False
    assert data["route_authority"]["endpoint_switch"] is False


def test_v6f_route_identities_are_disjoint_from_v6a_through_v6e() -> None:
    current = {spec.route_id for spec in (*DEV_ROUTE_SPECS, *CONFIRM_ROUTE_SPECS)}
    assert len(current) == 38
    for prior_specs in (
        (*V6A_DEV, *V6A_CONFIRM),
        (*V6B_DEV, *V6B_CONFIRM),
        (*V6C_DEV, *V6C_CONFIRM),
        (*V6D_DEV, *V6D_CONFIRM),
        (*V6E_DEV, *V6E_CONFIRM),
    ):
        assert current.isdisjoint({spec.route_id for spec in prior_specs})


def test_v6f_dev_and_confirmation_counts_and_bank_disjointness() -> None:
    bank = load_naturalistic_bank()
    training = {*bank.operation_texts, *bank.background_texts}
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
        assert manifest["synthetic_positives_per_route"] == 18
        assert manifest["probe_operation_examples"] == 432
        assert manifest["probe_background_examples"] == 384
        assert len(manifest["probe_bank_sha256"]) == 64
        assert set(manifest["adapters"]) == {"native", "openapi", "mcp"}
        assert manifest["corpus_sha256"]
        assert training.isdisjoint({str(row["query"]) for row in rows})

    assert {row["query"] for row in dev}.isdisjoint(
        {row["query"] for row in confirm}
    )


def test_v6f_query_identities_are_disjoint_from_v6a_through_v6e() -> None:
    current: set[str] = set()
    for role in ("development", "confirmation"):
        rows, _ = build(role)
        current.update(str(row["query"]) for row in rows)

    for builder in (build_v6a, build_v6b, build_v6c, build_v6d, build_v6e):
        prior: set[str] = set()
        for role in ("development", "confirmation"):
            rows, _ = builder(role)
            prior.update(str(row["query"]) for row in rows)
        assert current.isdisjoint(prior)


def test_v6f_expected_routes_match_frozen_specs() -> None:
    for role, specs in (
        ("development", DEV_ROUTE_SPECS),
        ("confirmation", CONFIRM_ROUTE_SPECS),
    ):
        rows, _ = build(role)
        expected_routes = {
            row["expected"] for row in rows if row["expected"] is not None
        }
        assert expected_routes == {spec.route_id for spec in specs}
