from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "analyze_negative_capability_prototypes_v4.py"


def _module():
    spec = importlib.util.spec_from_file_location(
        "analyze_negative_capability_prototypes_v4",
        SCRIPT,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load negative-capability diagnostic")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _row(
    *,
    expected: str | None,
    route: str,
    category: str,
    domain_score: float,
    domain_agree: bool,
    negative_score: float,
    negative_advantage: float,
) -> dict[str, object]:
    return {
        "expected": expected,
        "raw_top_route": route,
        "raw_correct": expected == route,
        "category": category,
        "language": "en",
        "unsupported_family": (
            "weather.family_1"
            if category == "near_domain_unsupported_operation"
            else None
        ),
        "winner_domain_score": domain_score,
        "top_domain_agrees_with_winner": domain_agree,
        "max_negative_score": negative_score,
        "negative_advantage": negative_advantage,
    }


def test_taxonomy_is_frozen_and_balanced() -> None:
    module = _module()
    assert set(module.DOMAIN_ANCHORS) == set(
        module.NEGATIVE_CAPABILITY_PROTOTYPES
    )
    assert len(module.DOMAIN_ANCHORS) == 8
    assert all(
        len(values) == 4
        for values in module.NEGATIVE_CAPABILITY_PROTOTYPES.values()
    )
    all_prototypes = [
        text
        for values in module.NEGATIVE_CAPABILITY_PROTOTYPES.values()
        for text in values
    ]
    assert len(all_prototypes) == 32
    forbidden = ("unsupported", "reject", "schema", "endpoint")
    assert not any(
        cue in text.casefold()
        for text in all_prototypes
        for cue in forbidden
    )


def test_preregistered_grid_has_588_rules() -> None:
    module = _module()
    count = (
        len(module.DOMAIN_MIN_THRESHOLDS)
        * len(module.DOMAIN_AGREEMENT_MODES)
        * len(module.NEGATIVE_MIN_THRESHOLDS)
        * len(module.NEGATIVE_ADVANTAGE_THRESHOLDS)
    )
    assert count == 588


def test_negative_evidence_can_only_veto_raw_winner() -> None:
    module = _module()
    row = _row(
        expected="weather.current",
        route="weather.current",
        category="v4_supported_natural",
        domain_score=0.8,
        domain_agree=True,
        negative_score=0.7,
        negative_advantage=0.2,
    )
    result = module._apply_rule(
        row,
        domain_min=0.3,
        require_domain_agreement=False,
        negative_min=0.5,
        negative_advantage_min=0.1,
    )
    assert result["veto"] is True
    assert result["predicted"] is None

    safe = {
        **row,
        "max_negative_score": 0.2,
        "negative_advantage": -0.2,
    }
    result = module._apply_rule(
        safe,
        domain_min=0.3,
        require_domain_agreement=False,
        negative_min=0.5,
        negative_advantage_min=0.1,
    )
    assert result["veto"] is False
    assert result["predicted"] == "weather.current"


def test_domain_evidence_can_reject_ood_without_switching_route() -> None:
    module = _module()
    row = _row(
        expected=None,
        route="weather.current",
        category="out_of_domain",
        domain_score=0.1,
        domain_agree=False,
        negative_score=0.1,
        negative_advantage=-0.2,
    )
    result = module._apply_rule(
        row,
        domain_min=0.3,
        require_domain_agreement=True,
        negative_min=0.5,
        negative_advantage_min=0.0,
    )
    assert result["domain_veto"] is True
    assert result["predicted"] is None


def test_rule_metrics_keep_complete_population_denominators() -> None:
    module = _module()
    rows = [
        _row(
            expected="weather.current",
            route="weather.current",
            category="v4_supported_natural",
            domain_score=0.8,
            domain_agree=True,
            negative_score=0.1,
            negative_advantage=-0.2,
        ),
        _row(
            expected="weather.current",
            route="weather.current",
            category="v4_supported_natural",
            domain_score=0.1,
            domain_agree=False,
            negative_score=0.1,
            negative_advantage=-0.2,
        ),
        _row(
            expected=None,
            route="weather.current",
            category="near_domain_unsupported_operation",
            domain_score=0.8,
            domain_agree=True,
            negative_score=0.8,
            negative_advantage=0.3,
        ),
        _row(
            expected=None,
            route="weather.current",
            category="out_of_domain",
            domain_score=0.1,
            domain_agree=False,
            negative_score=0.1,
            negative_advantage=-0.2,
        ),
    ]
    metrics = module._evaluate_rule(
        rows,
        domain_min=0.3,
        require_domain_agreement=True,
        negative_min=0.5,
        negative_advantage_min=0.1,
    )
    assert metrics["supported_exact_route_accuracy"] == 0.5
    assert metrics["near_domain_unsupported_rejection"] == 1.0
    assert metrics["out_of_domain_rejection"] == 1.0
    assert metrics["false_routes"] == 0
