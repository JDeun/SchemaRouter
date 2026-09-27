from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "generate_operation_routing_v4_dev.py"


def _module():
    spec = importlib.util.spec_from_file_location(
        "generate_operation_routing_v4_dev",
        SCRIPT,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load v4 development generator")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_v4_development_generator_is_deterministic_and_balanced() -> None:
    module = _module()
    first = module._build("operation-routing-v4-dev-2026-09-27")
    second = module._build("operation-routing-v4-dev-2026-09-27")

    assert first == second
    module._validate(first)
    assert len(first) == 1440
    assert sum(case["expected"] is not None for case in first) == 960
    assert sum(
        case["category"] == "near_domain_unsupported_operation"
        for case in first
    ) == 384
    assert sum(case["category"] == "out_of_domain" for case in first) == 96

    assert sum(case["split"] == "tune" for case in first) == 816
    assert sum(case["split"] == "dev_holdout" for case in first) == 624

    for language in module.LANGUAGES:
        assert sum(case["language"] == language for case in first) == 240


def test_v4_supported_routes_are_balanced() -> None:
    module = _module()
    cases = module._build("operation-routing-v4-dev-2026-09-27")
    counts: dict[str, int] = {}
    for case in cases:
        if case["expected"] is None:
            continue
        route = str(case["expected"])
        counts[route] = counts.get(route, 0) + 1

    assert len(counts) == 16
    assert set(counts.values()) == {60}


def test_v4_unsupported_families_are_disjoint_across_dev_splits() -> None:
    module = _module()
    cases = module._build("operation-routing-v4-dev-2026-09-27")
    families = {"tune": set(), "dev_holdout": set()}

    for case in cases:
        if case["category"] != "near_domain_unsupported_operation":
            continue
        families[str(case["split"])].add(str(case["family_id"]))

    assert len(families["tune"]) == 32
    assert len(families["dev_holdout"]) == 32
    assert families["tune"].isdisjoint(families["dev_holdout"])


def test_v4_has_zero_exact_overlap_with_consumed_corpora() -> None:
    module = _module()
    cases = module._build("operation-routing-v4-dev-2026-09-27")
    normalized = {module._normalize(str(case["query"])) for case in cases}

    assert normalized.isdisjoint(module._prior_normalized_queries())


def test_v4_contains_no_label_revealing_routing_cues() -> None:
    module = _module()
    cases = module._build("operation-routing-v4-dev-2026-09-27")

    assert not any(
        cue in str(case["query"]).casefold()
        for case in cases
        for cue in module.LABEL_REVEALING_CUES
    )
