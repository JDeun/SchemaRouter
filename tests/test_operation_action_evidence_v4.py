from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "benchmark_operation_action_evidence_v4.py"


def _module():
    spec = importlib.util.spec_from_file_location(
        "benchmark_operation_action_evidence_v4",
        SCRIPT,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load action evidence diagnostic")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_action_catalog_uses_only_endpoint_name_and_trusted_aliases() -> None:
    module = _module()
    benchmark = module._load_benchmark_module()
    catalog = dict(module._action_catalog(benchmark.reference_registry()))

    assert catalog["support.create_ticket"] == (
        "create ticket\n"
        "create support ticket\n"
        "open support case\n"
        "file support request"
    )
    assert "customer support ticket" not in catalog["support.create_ticket"]
    assert "status" not in catalog["support.create_ticket"]


def test_fast_accept_grid_counts_wrong_and_no_route_accepts() -> None:
    module = _module()
    rows = [
        {
            "expected": "tool.a",
            "top_route": "tool.a",
            "top_similarity": 0.60,
            "top_margin": 0.12,
        },
        {
            "expected": "tool.b",
            "top_route": "tool.a",
            "top_similarity": 0.60,
            "top_margin": 0.12,
        },
        {
            "expected": None,
            "top_route": "tool.a",
            "top_similarity": 0.60,
            "top_margin": 0.12,
        },
        {
            "expected": "tool.a",
            "top_route": "tool.a",
            "top_similarity": 0.10,
            "top_margin": 0.01,
        },
    ]

    grid = module._fast_accept_grid(rows)
    point = next(
        item
        for item in grid
        if item["min_similarity"] == 0.50
        and item["min_margin"] == 0.10
    )

    assert point["accepted"] == 3
    assert point["correct_supported"] == 1
    assert point["wrong_supported"] == 1
    assert point["false_routes"] == 1
    assert point["precision"] == 1 / 3


def test_cosine_is_bounded_and_exact_for_identical_vectors() -> None:
    module = _module()

    assert module._cosine([1.0, 0.0], [1.0, 0.0]) == 1.0
    assert module._cosine([1.0, 0.0], [-1.0, 0.0]) == -1.0
