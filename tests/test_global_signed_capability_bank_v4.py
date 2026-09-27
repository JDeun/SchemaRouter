from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "analyze_global_signed_capability_bank_v4.py"


def _module():
    spec = importlib.util.spec_from_file_location(
        "analyze_global_signed_capability_bank_v4",
        SCRIPT,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load global signed capability diagnostic")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _row(
    *,
    expected: str | None,
    raw_route: str,
    category: str,
    envelope: float,
    max_negative: float,
    signed_advantage: float,
    top_positive_route: str,
) -> dict[str, object]:
    return {
        "expected": expected,
        "raw_top_route": raw_route,
        "raw_correct": expected == raw_route,
        "category": category,
        "language": "en",
        "unsupported_family": (
            "weather.family_1"
            if category == "near_domain_unsupported_operation"
            else None
        ),
        "capability_envelope": envelope,
        "max_negative_score": max_negative,
        "signed_advantage": signed_advantage,
        "top_positive_route": top_positive_route,
    }


def test_frozen_banks_have_expected_cardinality() -> None:
    module = _module()
    assert len(module.NEGATIVE_CAPABILITY_PROTOTYPES) == 8
    assert all(
        len(values) == 4
        for values in module.NEGATIVE_CAPABILITY_PROTOTYPES.values()
    )
    assert sum(
        len(values)
        for values in module.NEGATIVE_CAPABILITY_PROTOTYPES.values()
    ) == 32


def test_preregistered_grid_has_504_rules() -> None:
    module = _module()
    count = (
        len(module.ENVELOPE_MIN_THRESHOLDS)
        * len(module.NEGATIVE_MIN_THRESHOLDS)
        * len(module.SIGNED_ADVANTAGE_THRESHOLDS)
        * len(module.POSITIVE_CONSISTENCY_MODES)
    )
    assert count == 504


def test_evidence_can_only_veto_raw_route() -> None:
    module = _module()
    row = _row(
        expected="weather.current",
        raw_route="weather.current",
        category="v4_supported_natural",
        envelope=0.8,
        max_negative=0.7,
        signed_advantage=0.2,
        top_positive_route="weather.current",
    )
    result = module._apply_rule(
        row,
        envelope_min=0.4,
        negative_min=0.5,
        signed_advantage_min=0.1,
        require_positive_consistency=False,
    )
    assert result["veto"] is True
    assert result["predicted"] is None

    safe = {
        **row,
        "max_negative_score": 0.3,
        "signed_advantage": -0.2,
    }
    result = module._apply_rule(
        safe,
        envelope_min=0.4,
        negative_min=0.5,
        signed_advantage_min=0.1,
        require_positive_consistency=False,
    )
    assert result["veto"] is False
    assert result["predicted"] == "weather.current"


def test_low_envelope_rejects_ood_without_rerouting() -> None:
    module = _module()
    row = _row(
        expected=None,
        raw_route="weather.current",
        category="out_of_domain",
        envelope=0.2,
        max_negative=0.1,
        signed_advantage=-0.1,
        top_positive_route="weather.current",
    )
    result = module._apply_rule(
        row,
        envelope_min=0.4,
        negative_min=0.5,
        signed_advantage_min=0.1,
        require_positive_consistency=False,
    )
    assert result["envelope_veto"] is True
    assert result["predicted"] is None


def test_positive_consistency_is_veto_only() -> None:
    module = _module()
    row = _row(
        expected="weather.current",
        raw_route="weather.current",
        category="v4_supported_natural",
        envelope=0.8,
        max_negative=0.2,
        signed_advantage=-0.2,
        top_positive_route="weather.forecast",
    )
    result = module._apply_rule(
        row,
        envelope_min=0.4,
        negative_min=0.5,
        signed_advantage_min=0.1,
        require_positive_consistency=True,
    )
    assert result["consistency_veto"] is True
    assert result["predicted"] is None


def test_rule_metrics_keep_complete_population_denominators() -> None:
    module = _module()
    rows = [
        _row(
            expected="weather.current",
            raw_route="weather.current",
            category="v4_supported_natural",
            envelope=0.8,
            max_negative=0.2,
            signed_advantage=-0.2,
            top_positive_route="weather.current",
        ),
        _row(
            expected="weather.current",
            raw_route="weather.current",
            category="v4_supported_natural",
            envelope=0.2,
            max_negative=0.2,
            signed_advantage=-0.2,
            top_positive_route="weather.current",
        ),
        _row(
            expected=None,
            raw_route="weather.current",
            category="near_domain_unsupported_operation",
            envelope=0.8,
            max_negative=0.8,
            signed_advantage=0.3,
            top_positive_route="weather.current",
        ),
        _row(
            expected=None,
            raw_route="weather.current",
            category="out_of_domain",
            envelope=0.2,
            max_negative=0.2,
            signed_advantage=-0.2,
            top_positive_route="weather.current",
        ),
    ]
    metrics = module._evaluate_rule(
        rows,
        envelope_min=0.4,
        negative_min=0.5,
        signed_advantage_min=0.1,
        require_positive_consistency=False,
    )
    assert metrics["supported_exact_route_accuracy"] == 0.5
    assert metrics["near_domain_unsupported_rejection"] == 1.0
    assert metrics["out_of_domain_rejection"] == 1.0
    assert metrics["false_routes"] == 0
