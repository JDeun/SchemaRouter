from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "scripts" / "generate_decision_routing_graph_v1.py"


def _module():
    spec = importlib.util.spec_from_file_location(
        "generate_decision_routing_graph_v1",
        GENERATOR,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load graph-v1 generator")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_graph_v1_development_shape_and_overlap_guard() -> None:
    module = _module()
    cases = module._build("graph-v1-test-seed")
    module._validate(cases)

    assert len(cases) == 1200
    assert sum(case["expected"] is not None for case in cases) == 768
    assert sum(
        case["category"] == "near_domain_unsupported_operation"
        for case in cases
    ) == 384
    assert sum(case["category"] == "out_of_domain" for case in cases) == 48
    assert {case["split"] for case in cases} == {"dev"}


def test_graph_v1_generation_is_seed_deterministic() -> None:
    module = _module()

    first = module._build("same-seed")
    second = module._build("same-seed")
    different = module._build("different-seed")

    assert first == second
    assert first != different


def test_graph_v1_balances_languages_and_supported_routes() -> None:
    module = _module()
    cases = module._build("balance-seed")

    for language in module.LANGUAGES:
        assert sum(case["language"] == language for case in cases) == 200

    route_counts: dict[str, int] = {}
    for case in cases:
        expected = case["expected"]
        if expected is not None:
            route_counts[str(expected)] = route_counts.get(str(expected), 0) + 1

    assert len(route_counts) == 16
    assert set(route_counts.values()) == {48}
