from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "generate_decision_routing_graph_calibration_v1.py"


def _module():
    spec = importlib.util.spec_from_file_location(
        "generate_decision_routing_graph_calibration_v1",
        SCRIPT,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load graph calibration generator")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_graph_calibration_generator_is_deterministic_and_balanced() -> None:
    module = _module()
    first = module._build("graph-v1-calibration-2026-09-27")
    second = module._build("graph-v1-calibration-2026-09-27")

    assert first == second
    module._validate(first)
    assert len(first) == 600
    assert sum(case["expected"] is not None for case in first) == 384
    assert sum(
        case["category"] == "near_domain_unsupported_operation"
        for case in first
    ) == 192
    assert sum(case["category"] == "out_of_domain" for case in first) == 24

    for language in module.LANGUAGES:
        assert sum(case["language"] == language for case in first) == 100

    route_counts: dict[str, int] = {}
    for case in first:
        expected = case["expected"]
        if expected is not None:
            route_counts[str(expected)] = route_counts.get(str(expected), 0) + 1
    assert len(route_counts) == 16
    assert set(route_counts.values()) == {24}


def test_graph_calibration_has_zero_exact_overlap_with_prior_and_dev() -> None:
    module = _module()
    cases = module._build("graph-v1-calibration-2026-09-27")
    normalized = {module._normalize(str(case["query"])) for case in cases}

    assert normalized.isdisjoint(module._prior_and_dev_normalized_queries())


def test_graph_calibration_near_domain_has_no_label_revealing_cues() -> None:
    module = _module()
    cases = module._build("graph-v1-calibration-2026-09-27")
    near = [
        str(case["query"]).casefold()
        for case in cases
        if case["category"] == "near_domain_unsupported_operation"
    ]

    assert len(near) == 192
    assert not any(
        cue in query
        for query in near
        for cue in module.LABEL_REVEALING_CUES
    )


def test_graph_calibration_uses_four_distinct_unsupported_families_per_domain() -> None:
    module = _module()

    assert set(module.NEAR_DOMAIN_FAMILIES) == {
        "weather",
        "materials",
        "papers",
        "finance",
        "calendar",
        "support",
        "inventory",
        "users",
    }
    for domain in module.NEAR_DOMAIN_FAMILIES.values():
        for language in module.LANGUAGES:
            assert len(domain[language]) == 4
            assert len(set(domain[language])) == 4


def test_graph_calibration_holds_out_dev_unsupported_core_families() -> None:
    module = _module()

    for first, _second in module._graph_dev.ROUTE_PAIRS:
        domain = first.split(".", 1)[0]
        for language in module.LANGUAGES:
            dev_core = module._normalize(
                module._graph_dev.NEAR_DOMAIN[domain][language]
            )
            calibration_families = {
                module._normalize(query)
                for query in module.NEAR_DOMAIN_FAMILIES[domain][language]
            }
            assert dev_core not in calibration_families
