from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "generate_decision_routing_quality_v4.py"
SEED = "operation-routing-quality-v4-development-2026-09-27"


def _module():
    spec = importlib.util.spec_from_file_location(
        "generate_decision_routing_quality_v4",
        SCRIPT,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load v4 routing development generator")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_v4_development_generator_is_deterministic_and_balanced() -> None:
    module = _module()
    first = module._build(SEED)
    second = module._build(SEED)

    assert first == second
    module._validate(first)
    assert len(first) == 1800
    assert sum(case["expected"] is not None for case in first) == 1152
    assert sum(
        case["category"] == "near_domain_unsupported_operation"
        for case in first
    ) == 576
    assert sum(case["category"] == "out_of_domain" for case in first) == 72

    for language in module.LANGUAGES:
        assert sum(case["language"] == language for case in first) == 300


def test_v4_development_route_and_unsupported_family_balance() -> None:
    module = _module()
    cases = module._build(SEED)

    route_counts: dict[str, int] = {}
    family_counts: dict[str, int] = {}
    for case in cases:
        expected = case["expected"]
        if expected is not None:
            route_counts[str(expected)] = route_counts.get(str(expected), 0) + 1
        family = case.get("unsupported_family")
        if family is not None:
            family_counts[str(family)] = family_counts.get(str(family), 0) + 1

    assert len(route_counts) == 16
    assert set(route_counts.values()) == {72}
    assert len(family_counts) == 32
    assert set(family_counts.values()) == {18}


def test_v4_development_has_zero_exact_overlap_with_consumed_corpora() -> None:
    module = _module()
    cases = module._build(SEED)
    normalized = {module._normalize(str(case["query"])) for case in cases}

    assert normalized.isdisjoint(module._prior_normalized_queries())


def test_v4_development_has_no_label_revealing_routing_cues() -> None:
    module = _module()
    cases = module._build(SEED)

    assert not any(
        cue in str(case["query"]).casefold()
        for case in cases
        for cue in module.LABEL_REVEALING_CUES
    )


def test_v4_supported_and_unsupported_templates_cover_every_language() -> None:
    module = _module()

    assert len(module.SUPPORTED_VARIANTS) == 16
    for route in module.SUPPORTED_VARIANTS.values():
        assert set(route) == set(module.LANGUAGES)
        for variants in route.values():
            assert len(variants) == 2

    assert len(module.NEAR_DOMAIN_FAMILIES) == 8
    for families in module.NEAR_DOMAIN_FAMILIES.values():
        assert len(families) == 4
        for family in families:
            assert len(family["values"]) == 3
            assert set(family["templates"]) == set(module.LANGUAGES)
