from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "analyze_route_local_stable_fusion_v4.py"


def _module():
    spec = importlib.util.spec_from_file_location(
        "analyze_route_local_stable_fusion_v4",
        SCRIPT,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load route-local stable fusion analyzer")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_route_weight_map_is_frozen() -> None:
    module = _module()
    assert module.ROUTE_SCHEMA_WEIGHTS["inventory.search"] == 0.35
    assert module.ROUTE_SCHEMA_WEIGHTS["papers.search"] == 0.30
    assert module.ROUTE_SCHEMA_WEIGHTS["finance.history"] == 0.60
    assert len(module.ROUTE_SCHEMA_WEIGHTS) == 16


def test_midpoint_thresholds_never_reuse_observed_scores() -> None:
    module = _module()
    values = [0.1, 0.2, 0.4]
    thresholds = module._midpoint_thresholds(values)
    assert thresholds == [-1.0, 0.15, 0.30000000000000004, 1.000001]
    assert not any(value in thresholds for value in values)


def test_round_up_is_conservative() -> None:
    module = _module()
    rounded = module._round_up(0.4630872644672503)
    assert rounded == 0.463088
    assert rounded >= 0.4630872644672503


def test_projection_perturbs_supported_and_unsupported_adversarially() -> None:
    module = _module()
    rows = [
        {
            "expected": "tool.a",
            "category": "supported",
            "selected_route": "tool.a",
            "top_score": 0.5000015,
            "top_margin": 0.1,
        },
        {
            "expected": None,
            "category": "near_domain_unsupported_operation",
            "selected_route": "tool.a",
            "top_score": 0.4999995,
            "top_margin": 0.1,
        },
        {
            "expected": None,
            "category": "out_of_domain",
            "selected_route": "tool.a",
            "top_score": 0.1,
            "top_margin": 0.1,
        },
    ]
    thresholds = {
        "tool.a": {
            "min_score": 0.5,
            "min_score_unrounded": 0.5,
            "min_margin": 0.0,
        }
    }
    nominal = module._project(
        rows,
        thresholds=thresholds,
        perturbation_epsilon=0.0,
    )
    stressed = module._project(
        rows,
        thresholds=thresholds,
        perturbation_epsilon=1e-6,
    )
    assert nominal["supported_correct"] == 1
    assert nominal["false_routes"] == 0
    assert stressed["supported_correct"] == 1
    assert stressed["false_routes"] == 1
