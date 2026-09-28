# ruff: noqa: E402, I001
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmarks.conformal_e5_membership import (  # noqa: E402
    CONFORMAL_ALPHA,
    build_e0_documents,
    conformal_accept,
    unsupported_conformal_p_value,
)
from benchmarks.operation_routing_v6a_catalog import (  # noqa: E402
    CONFIRM_ROUTE_SPECS as V6A_CONFIRM,
    DEV_ROUTE_SPECS as V6A_DEV,
)
from benchmarks.operation_routing_v6b_catalog import (  # noqa: E402
    CONFIRM_ROUTE_SPECS as V6B_CONFIRM,
    DEV_ROUTE_SPECS as V6B_DEV,
)
from benchmarks.operation_routing_v6c_catalog import (  # noqa: E402
    CONFIRM_ROUTE_SPECS as V6C_CONFIRM,
    DEV_ROUTE_SPECS as V6C_DEV,
)
from benchmarks.operation_routing_v6d_catalog import (  # noqa: E402
    CONFIRM_ROUTE_SPECS as V6D_CONFIRM,
    DEV_ROUTE_SPECS as V6D_DEV,
)
from benchmarks.operation_routing_v6e_catalog import (  # noqa: E402
    CONFIRM_ROUTE_SPECS as V6E_CONFIRM,
    DEV_ROUTE_SPECS as V6E_DEV,
)
from benchmarks.operation_routing_v6f_catalog import (  # noqa: E402
    CONFIRM_ROUTE_SPECS as V6F_CONFIRM,
    DEV_ROUTE_SPECS as V6F_DEV,
)
from benchmarks.operation_routing_v6g_catalog import (  # noqa: E402
    CALIBRATION_ROUTE_SPECS,
    CONFIRM_ROUTE_SPECS,
    DEV_ROUTE_SPECS,
    calibration_registry,
    confirmation_registry,
    development_registry,
)
from scripts.generate_operation_routing_v6a import build as build_v6a  # noqa: E402
from scripts.generate_operation_routing_v6b import build as build_v6b  # noqa: E402
from scripts.generate_operation_routing_v6c import build as build_v6c  # noqa: E402
from scripts.generate_operation_routing_v6d import build as build_v6d  # noqa: E402
from scripts.generate_operation_routing_v6e import build as build_v6e  # noqa: E402
from scripts.generate_operation_routing_v6f import build as build_v6f  # noqa: E402
from scripts.generate_operation_routing_v6g import build  # noqa: E402


def test_v6g_preregistration_is_frozen_to_issue_412() -> None:
    data = json.loads(
        (
            ROOT
            / "benchmarks"
            / "operation-routing-v6g-conformal-e5-preregistration.json"
        ).read_text(encoding="utf-8")
    )
    assert data["issue"] == 412
    assert data["experiment"] == "conformal-multilingual-e5-catalog-membership-v1"
    assert data["conformal_gate"]["alpha"] == 0.01
    assert data["conformal_gate"]["threshold_grid"] is False
    assert data["conformal_gate"]["alpha_sweep"] is False
    assert data["positive_selector"]["positive_rerank"] is False
    assert data["positive_selector"]["endpoint_switch"] is False


def test_v6g_e0_documents_are_deterministic_and_schema_only() -> None:
    registry = development_registry()
    first = build_e0_documents(registry)
    second = build_e0_documents(registry)
    assert first == second
    assert len(first) == 19
    assert len({row.route_id for row in first}) == 19
    assert all("limitations:" not in row.text for row in first)
    dielectric = next(
        row
        for row in first
        if row.route_id == "dielectric_constant.current"
    )
    assert "dielectric constant" in dielectric.text.casefold()
    assert "material.dielectric_constant" in dielectric.text
    assert "unit=" not in dielectric.text
    assert "statistic=" not in dielectric.text


def test_v6g_conformal_p_value_is_conservative_on_ties() -> None:
    calibration = [0.1, 0.2, 0.3, 0.4]
    assert unsupported_conformal_p_value(0.4, calibration) == 2 / 5
    assert unsupported_conformal_p_value(0.41, calibration) == 1 / 5
    accepted, p_value = conformal_accept(0.41, calibration, alpha=0.21)
    assert accepted is True
    assert p_value == 1 / 5
    accepted, _ = conformal_accept(0.4, calibration, alpha=0.21)
    assert accepted is False
    assert CONFORMAL_ALPHA == 0.01


def test_v6g_route_identities_are_disjoint_from_v6a_through_v6f() -> None:
    current = {
        spec.route_id
        for spec in (
            *CALIBRATION_ROUTE_SPECS,
            *DEV_ROUTE_SPECS,
            *CONFIRM_ROUTE_SPECS,
        )
    }
    for prior in (
        (*V6A_DEV, *V6A_CONFIRM),
        (*V6B_DEV, *V6B_CONFIRM),
        (*V6C_DEV, *V6C_CONFIRM),
        (*V6D_DEV, *V6D_CONFIRM),
        (*V6E_DEV, *V6E_CONFIRM),
        (*V6F_DEV, *V6F_CONFIRM),
    ):
        assert current.isdisjoint({spec.route_id for spec in prior})


def test_v6g_three_surface_counts_and_mutual_disjointness() -> None:
    built = {
        role: build(role)
        for role in ("calibration", "development", "confirmation")
    }
    query_sets: dict[str, set[str]] = {}
    for role, (rows, manifest) in built.items():
        assert len(rows) == 552
        assert manifest["supported_cases"] == 228
        assert manifest["near_domain_cases"] == 252
        assert manifest["out_of_domain_cases"] == 72
        assert manifest["unsupported_cases"] == 324
        assert manifest["route_count"] == 19
        assert manifest["tool_count"] == 7
        assert manifest["endpoint_counts"] == [2, 2, 3, 3, 3, 3, 3]
        assert manifest["e0_document_count"] == 19
        assert set(manifest["adapters"]) == {"native", "openapi", "mcp"}
        query_sets[role] = {str(row["query"]) for row in rows}

    assert query_sets["calibration"].isdisjoint(query_sets["development"])
    assert query_sets["calibration"].isdisjoint(query_sets["confirmation"])
    assert query_sets["development"].isdisjoint(query_sets["confirmation"])


def test_v6g_query_identities_are_disjoint_from_v6a_through_v6f() -> None:
    current: set[str] = set()
    for role in ("calibration", "development", "confirmation"):
        rows, _ = build(role)
        current.update(str(row["query"]) for row in rows)

    for builder in (
        build_v6a,
        build_v6b,
        build_v6c,
        build_v6d,
        build_v6e,
        build_v6f,
    ):
        prior: set[str] = set()
        for role in ("development", "confirmation"):
            rows, _ = builder(role)
            prior.update(str(row["query"]) for row in rows)
        assert current.isdisjoint(prior)


def test_v6g_expected_routes_match_registry_contracts() -> None:
    for role, registry_builder, specs in (
        ("calibration", calibration_registry, CALIBRATION_ROUTE_SPECS),
        ("development", development_registry, DEV_ROUTE_SPECS),
        ("confirmation", confirmation_registry, CONFIRM_ROUTE_SPECS),
    ):
        rows, _ = build(role)
        assert {
            row["expected"] for row in rows if row["expected"] is not None
        } == {spec.route_id for spec in specs}
        assert len(build_e0_documents(registry_builder())) == 19
