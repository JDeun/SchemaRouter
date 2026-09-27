from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "analyze_rank_vote_openworld_v4.py"


def _module():
    spec = importlib.util.spec_from_file_location(
        "analyze_rank_vote_openworld_v4",
        SCRIPT,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load rank-vote open-world diagnostic")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _row(
    *,
    expected: str | None,
    route: str,
    category: str,
    negative_votes: int,
    top_kind: str,
    top3: int,
    top5: int,
    top7: int,
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
        "negative_votes": negative_votes,
        "top_evidence_kind": top_kind,
        "background_votes_top3": top3,
        "background_votes_top5": top5,
        "background_votes_top7": top7,
    }


def test_preregistered_grid_has_72_rules() -> None:
    module = _module()
    assert len(list(module._iter_rules())) == 72


def test_vote_requirements_are_deterministic() -> None:
    module = _module()
    assert module._required_background_votes(3, "majority") == 2
    assert module._required_background_votes(5, "two_thirds") == 4
    assert module._required_background_votes(7, "unanimous") == 7


def test_negative_rank_vote_is_veto_only() -> None:
    module = _module()
    row = _row(
        expected="weather.current",
        route="weather.current",
        category="v4_supported_natural",
        negative_votes=2,
        top_kind="known",
        top3=0,
        top5=0,
        top7=0,
    )
    result = module._apply_rank_rule(
        row,
        negative_votes_min=2,
        top_k=3,
        background_requirement_mode="majority",
        require_top1_background=False,
    )
    assert result["negative_veto"] is True
    assert result["background_veto"] is False
    assert result["predicted"] is None


def test_background_rank_vote_can_require_background_top1() -> None:
    module = _module()
    row = _row(
        expected=None,
        route="weather.current",
        category="out_of_domain",
        negative_votes=0,
        top_kind="known",
        top3=3,
        top5=5,
        top7=7,
    )
    result = module._apply_rank_rule(
        row,
        negative_votes_min=4,
        top_k=3,
        background_requirement_mode="majority",
        require_top1_background=True,
    )
    assert result["background_veto"] is False
    assert result["predicted"] == "weather.current"


def test_rule_metrics_use_full_population_denominators() -> None:
    module = _module()
    rows = [
        _row(
            expected="weather.current",
            route="weather.current",
            category="v4_supported_natural",
            negative_votes=0,
            top_kind="known",
            top3=0,
            top5=0,
            top7=0,
        ),
        _row(
            expected="weather.current",
            route="weather.current",
            category="v4_supported_natural",
            negative_votes=2,
            top_kind="known",
            top3=0,
            top5=0,
            top7=0,
        ),
        _row(
            expected=None,
            route="weather.current",
            category="near_domain_unsupported_operation",
            negative_votes=3,
            top_kind="known",
            top3=0,
            top5=0,
            top7=0,
        ),
        _row(
            expected=None,
            route="weather.current",
            category="out_of_domain",
            negative_votes=0,
            top_kind="background",
            top3=2,
            top5=4,
            top7=5,
        ),
    ]
    metrics = module._evaluate_rule(
        rows,
        negative_votes_min=2,
        top_k=3,
        background_requirement_mode="majority",
        require_top1_background=True,
    )
    assert metrics["supported_exact_route_accuracy"] == 0.5
    assert metrics["near_domain_unsupported_rejection"] == 1.0
    assert metrics["out_of_domain_rejection"] == 1.0
    assert metrics["false_routes"] == 0
