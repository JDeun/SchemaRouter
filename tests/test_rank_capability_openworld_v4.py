from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "analyze_rank_capability_openworld_v4.py"


def _module():
    spec = importlib.util.spec_from_file_location(
        "analyze_rank_capability_openworld_v4",
        SCRIPT,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load rank capability diagnostic")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _row(
    *,
    expected: str | None = "weather.current",
    route: str = "weather.current",
    category: str = "v4_supported_natural",
    local_kinds: list[str] | None = None,
    raw_positive_rank: int = 1,
    best_negative_rank: int = 2,
    membership_kinds: list[str] | None = None,
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
        "local_rank_kinds": local_kinds or [
            "positive",
            "negative",
            "negative",
            "positive",
        ],
        "raw_positive_rank": raw_positive_rank,
        "best_negative_rank": best_negative_rank,
        "global_membership_rank_kinds": membership_kinds or [
            "known",
            "background",
            "known",
            "background",
            "background",
        ],
    }


def test_frozen_banks_and_rule_count() -> None:
    module = _module()
    assert len(module.DOMAIN_ANCHORS) == 8
    assert set(module.DOMAIN_ANCHORS) == set(
        module.NEGATIVE_CAPABILITY_PROTOTYPES
    )
    assert all(
        len(values) == 4
        for values in module.NEGATIVE_CAPABILITY_PROTOTYPES.values()
    )
    assert len(module.BACKGROUND_PROTOTYPES) == 16
    assert len(set(module.BACKGROUND_PROTOTYPES)) == 16
    assert len(module.NEAR_MODES) == 5
    assert len(module.OOD_MODES) == 4
    assert len(module.NEAR_MODES) * len(module.OOD_MODES) == 20


def test_near_rank_rules_are_threshold_free() -> None:
    module = _module()

    top1 = _row(
        local_kinds=["negative", "positive", "negative", "positive"],
        raw_positive_rank=2,
        best_negative_rank=1,
    )
    assert module._near_veto(top1, "negative_top1")
    assert module._near_veto(top1, "negative_outranks_raw_positive")

    top2 = _row(
        local_kinds=["negative", "negative", "positive", "positive"],
        raw_positive_rank=3,
        best_negative_rank=1,
    )
    assert module._near_veto(top2, "negative_top2_all")

    top3 = _row(
        local_kinds=["negative", "positive", "negative", "positive"],
    )
    assert module._near_veto(top3, "negative_top3_majority")

    top4 = _row(
        local_kinds=["negative", "negative", "positive", "negative"],
    )
    assert module._near_veto(top4, "negative_top4_majority")


def test_ood_rank_rules_are_threshold_free() -> None:
    module = _module()

    top1 = _row(
        membership_kinds=[
            "background",
            "known",
            "background",
            "known",
            "background",
        ]
    )
    assert module._ood_veto(top1, "background_top1")

    top2 = _row(
        membership_kinds=[
            "background",
            "background",
            "known",
            "known",
            "background",
        ]
    )
    assert module._ood_veto(top2, "background_top2_all")

    top3 = _row(
        membership_kinds=[
            "background",
            "known",
            "background",
            "known",
            "known",
        ]
    )
    assert module._ood_veto(top3, "background_top3_majority")

    top5 = _row(
        membership_kinds=[
            "background",
            "known",
            "background",
            "known",
            "background",
        ]
    )
    assert module._ood_veto(top5, "background_top5_majority")


def test_capability_evidence_can_only_veto_raw_route() -> None:
    module = _module()
    row = _row(
        local_kinds=["negative", "positive", "negative", "positive"],
        membership_kinds=[
            "background",
            "known",
            "background",
            "known",
            "background",
        ],
    )
    result = module._apply_rule(
        row,
        near_mode="negative_top1",
        ood_mode="background_top1",
    )
    assert result["veto"] is True
    assert result["predicted"] is None

    safe = _row(
        local_kinds=["positive", "negative", "positive", "negative"],
        raw_positive_rank=1,
        best_negative_rank=2,
        membership_kinds=[
            "known",
            "background",
            "known",
            "background",
            "known",
        ],
    )
    result = module._apply_rule(
        safe,
        near_mode="negative_top1",
        ood_mode="background_top1",
    )
    assert result["veto"] is False
    assert result["predicted"] == "weather.current"


def test_rule_metrics_keep_complete_population_denominators() -> None:
    module = _module()
    rows = [
        _row(),
        _row(
            local_kinds=["negative", "positive", "negative", "positive"],
        ),
        _row(
            expected=None,
            category="near_domain_unsupported_operation",
            local_kinds=["negative", "positive", "negative", "positive"],
        ),
        _row(
            expected=None,
            category="out_of_domain",
            membership_kinds=[
                "background",
                "known",
                "background",
                "known",
                "background",
            ],
        ),
    ]
    metrics = module._evaluate_rule(
        rows,
        near_mode="negative_top1",
        ood_mode="background_top1",
    )
    assert metrics["supported_exact_route_accuracy"] == 0.5
    assert metrics["near_domain_unsupported_rejection"] == 1.0
    assert metrics["out_of_domain_rejection"] == 1.0
    assert metrics["false_routes"] == 0
