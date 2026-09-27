from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "analyze_bge_m3_abstention_geometry_v4.py"


def _module():
    spec = importlib.util.spec_from_file_location(
        "analyze_bge_m3_abstention_geometry_v4",
        SCRIPT,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load abstention geometry diagnostic")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _row(
    case_id: str,
    *,
    expected: str | None,
    route: str,
    accepted: bool,
    score_shortfall: float,
    margin_shortfall: float = 0.0,
    route_agree: bool = True,
    tool_agree: bool = True,
    schema_top1: bool = True,
    action_top1: bool = True,
    disagreement: float = 0.01,
    category: str = "v4_supported_natural",
) -> dict[str, object]:
    return {
        "case_id": case_id,
        "expected": expected,
        "top_route": route,
        "base_accepted": accepted,
        "score_shortfall": score_shortfall,
        "margin_shortfall": margin_shortfall,
        "schema_action_top_route_agree": route_agree,
        "schema_action_top_tool_agree": tool_agree,
        "fused_winner_schema_top1": schema_top1,
        "fused_winner_action_top1": action_top1,
        "winner_view_score_disagreement": disagreement,
        "category": category,
    }


def test_rule_grid_is_exactly_preregistered() -> None:
    module = _module()
    assert len(module.RULE_CONFIGS) == 240
    assert module.SCORE_SHORTFALL_GRID == (
        0.001,
        0.0025,
        0.005,
        0.01,
        0.02,
        0.04,
    )
    assert module.MARGIN_SHORTFALL_GRID == (
        0.0,
        0.0025,
        0.005,
        0.01,
        0.02,
    )
    assert module.DISAGREEMENT_GRID == (0.025, 0.05, 0.10, 0.20)


def test_proximity_rule_respects_shortfall_limits() -> None:
    module = _module()
    config = {
        "family": "proximity",
        "score_shortfall_max": 0.005,
        "margin_shortfall_max": 0.0025,
        "view_disagreement_max": None,
    }
    assert module._passes_rule(
        _row(
            "yes",
            expected="tool.a",
            route="tool.a",
            accepted=False,
            score_shortfall=0.004,
            margin_shortfall=0.002,
        ),
        config,
    )
    assert not module._passes_rule(
        _row(
            "no",
            expected="tool.a",
            route="tool.a",
            accepted=False,
            score_shortfall=0.006,
        ),
        config,
    )


def test_view_agreement_rules_are_additional_guards() -> None:
    module = _module()
    base = {
        "score_shortfall_max": 0.01,
        "margin_shortfall_max": 0.01,
        "view_disagreement_max": None,
    }
    row = _row(
        "case",
        expected="tool.a",
        route="tool.a",
        accepted=False,
        score_shortfall=0.001,
        route_agree=False,
        tool_agree=True,
    )
    assert module._passes_rule(
        row,
        {"family": "proximity_tool_agree", **base},
    )
    assert not module._passes_rule(
        row,
        {"family": "proximity_route_agree", **base},
    )


def test_route_local_optimizer_can_rescue_correct_with_zero_false() -> None:
    module = _module()
    rows = [
        _row(
            "correct",
            expected="tool.a",
            route="tool.a",
            accepted=False,
            score_shortfall=0.001,
        ),
        _row(
            "unsupported",
            expected=None,
            route="tool.a",
            accepted=False,
            score_shortfall=0.03,
            category="near_domain_unsupported_operation",
        ),
        _row(
            "base",
            expected="tool.b",
            route="tool.b",
            accepted=True,
            score_shortfall=0.0,
        ),
        _row(
            "ood",
            expected=None,
            route="tool.b",
            accepted=False,
            score_shortfall=0.03,
            category="out_of_domain",
        ),
    ]
    solution = module._route_local_frontier(
        rows,
        ["tool.a", "tool.b"],
        false_budget=0,
    )
    assert solution["additional_supported_correct"] == 1
    assert solution["additional_false_routes"] == 0

    metrics = module._compose(
        rows,
        route_rules=solution["rules"],
    )
    assert metrics["supported_exact_route_accuracy"] == 1.0
    assert metrics["false_routes"] == 0


def test_base_accepted_decisions_are_never_changed() -> None:
    module = _module()
    rows = [
        _row(
            "accepted-wrong",
            expected="tool.b",
            route="tool.a",
            accepted=True,
            score_shortfall=0.0,
        ),
        _row(
            "rescue-correct",
            expected="tool.b",
            route="tool.b",
            accepted=False,
            score_shortfall=0.001,
        ),
        _row(
            "near",
            expected=None,
            route="tool.b",
            accepted=False,
            score_shortfall=0.03,
            category="near_domain_unsupported_operation",
        ),
    ]
    rule = {
        "family": "proximity",
        "score_shortfall_max": 0.005,
        "margin_shortfall_max": 0.0,
        "view_disagreement_max": None,
    }
    metrics = module._compose(rows, global_rule=rule)
    assert metrics["supported_correct"] == 1
    assert metrics["wrong_supported"] == 1
    assert metrics["false_routes"] == 0
