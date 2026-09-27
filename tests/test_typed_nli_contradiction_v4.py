from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ANALYZER = ROOT / "scripts" / "analyze_typed_nli_contradiction_v4.py"


def _module():
    spec = importlib.util.spec_from_file_location(
        "analyze_typed_nli_contradiction_v4",
        ANALYZER,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load typed NLI diagnostic")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _row(
    *,
    expected: str | None,
    raw_top_route: str,
    contradiction: float,
    category: str,
    language: str = "en",
    family: str | None = None,
) -> dict[str, object]:
    return {
        "case_id": f"{language}-{raw_top_route}-{contradiction}",
        "expected": expected,
        "raw_top_route": raw_top_route,
        "raw_top_score": 0.8,
        "raw_top_margin": 0.1,
        "raw_correct": expected == raw_top_route,
        "contradiction": contradiction,
        "neutral": 0.2,
        "entailment": max(0.0, 0.8 - contradiction),
        "dominant_nli_state": "contradiction" if contradiction >= 0.5 else "entailment",
        "category": category,
        "language": language,
        "unsupported_family": family,
    }


def test_preregistered_threshold_grid_is_fixed() -> None:
    module = _module()
    assert module.CONTRADICTION_THRESHOLDS == (
        0.50,
        0.65,
        0.80,
        0.90,
        0.95,
        0.98,
        0.99,
    )


def test_contradiction_veto_never_changes_raw_winner() -> None:
    module = _module()
    rows = [
        _row(
            expected="tool.a",
            raw_top_route="tool.a",
            contradiction=0.20,
            category="v4_supported_natural",
        ),
        _row(
            expected=None,
            raw_top_route="tool.a",
            contradiction=0.95,
            category="near_domain_unsupported_operation",
            family="unsupported-a",
        ),
        _row(
            expected=None,
            raw_top_route="tool.b",
            contradiction=0.99,
            category="out_of_domain",
        ),
    ]
    result = module._metrics_at_threshold(rows, 0.90)
    assert result["supported_exact_route_accuracy"] == 1.0
    assert result["near_domain_unsupported_rejection"] == 1.0
    assert result["out_of_domain_rejection"] == 1.0
    assert result["false_routes"] == 0


def test_low_contradiction_does_not_require_positive_entailment() -> None:
    module = _module()
    rows = [
        {
            **_row(
                expected="tool.a",
                raw_top_route="tool.a",
                contradiction=0.10,
                category="v4_supported_natural",
            ),
            "neutral": 0.80,
            "entailment": 0.10,
            "dominant_nli_state": "neutral",
        },
        _row(
            expected=None,
            raw_top_route="tool.a",
            contradiction=0.95,
            category="near_domain_unsupported_operation",
            family="unsupported-a",
        ),
        _row(
            expected=None,
            raw_top_route="tool.b",
            contradiction=0.95,
            category="out_of_domain",
        ),
    ]
    result = module._metrics_at_threshold(rows, 0.90)
    assert result["supported_correct"] == 1
    assert result["vetoed_supported_correct_winners"] == 0


def test_veto_can_reduce_recall_but_cannot_create_correctness() -> None:
    module = _module()
    rows = [
        _row(
            expected="tool.a",
            raw_top_route="tool.b",
            contradiction=0.10,
            category="v4_supported_natural",
        ),
        _row(
            expected="tool.a",
            raw_top_route="tool.a",
            contradiction=0.95,
            category="v4_supported_natural",
        ),
        _row(
            expected=None,
            raw_top_route="tool.a",
            contradiction=0.95,
            category="near_domain_unsupported_operation",
            family="unsupported-a",
        ),
        _row(
            expected=None,
            raw_top_route="tool.b",
            contradiction=0.95,
            category="out_of_domain",
        ),
    ]
    result = module._metrics_at_threshold(rows, 0.90)
    assert result["supported_correct"] == 0
    assert result["vetoed_supported_correct_winners"] == 1


def test_dominant_state_preserves_unknown_semantics() -> None:
    module = _module()
    assert module._dominant_state(
        {"contradiction": 0.1, "neutral": 0.8, "entailment": 0.1}
    ) == "neutral"
