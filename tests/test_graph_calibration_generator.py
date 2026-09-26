from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "scripts" / "generate_decision_routing_graph_v1_calibration.py"


def _module():
    spec = importlib.util.spec_from_file_location(
        "generate_decision_routing_graph_v1_calibration",
        GENERATOR,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load graph-v1 calibration generator")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_graph_v1_calibration_shape_and_isolation() -> None:
    module = _module()
    cases = module._build("graph-calibration-test-seed")
    module._validate(cases)

    assert len(cases) == 600
    assert sum(case["expected"] is not None for case in cases) == 384
    assert sum(
        case["category"] == "near_domain_unsupported_operation"
        for case in cases
    ) == 192
    assert sum(case["category"] == "out_of_domain" for case in cases) == 24
    assert {case["split"] for case in cases} == {"calibration"}

    normalized = {module._normalize(str(case["query"])) for case in cases}
    assert not normalized.intersection(module._development_normalized_queries())
    assert not normalized.intersection(module._dev._prior_normalized_queries())


def test_graph_v1_calibration_is_seed_deterministic() -> None:
    module = _module()

    first = module._build("same-calibration-seed")
    second = module._build("same-calibration-seed")
    different = module._build("different-calibration-seed")

    assert first == second
    assert first != different


def test_graph_v1_calibration_balances_languages_and_routes() -> None:
    module = _module()
    cases = module._build("calibration-balance-seed")

    for language in module.LANGUAGES:
        assert sum(case["language"] == language for case in cases) == 100

    route_counts: dict[str, int] = {}
    for case in cases:
        expected = case["expected"]
        if expected is not None:
            route_counts[str(expected)] = route_counts.get(str(expected), 0) + 1

    assert len(route_counts) == 16
    assert set(route_counts.values()) == {24}
