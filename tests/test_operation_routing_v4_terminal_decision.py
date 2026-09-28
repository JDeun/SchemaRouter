from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TERMINAL = ROOT / "benchmarks" / "operation-routing-v4-terminal-decision.json"


def _data() -> dict:
    return json.loads(TERMINAL.read_text(encoding="utf-8"))


def test_terminal_decision_preserves_production_target() -> None:
    data = _data()
    target = data["production_target"]

    assert data["status"] == "closed_without_promoted_candidate"
    assert target["supported_exact_route_accuracy_min"] == 0.85
    assert target["near_domain_unsupported_rejection_min"] == 0.97
    assert target["out_of_domain_rejection"] == 1.0
    assert target["false_route_rate_max"] == 0.01
    assert target["authority_violations_max"] == 0
    assert target["execution_errors_max"] == 0
    assert target["executable_p95_ms_max"] == 250


def test_dev_pass_is_not_promoted_after_fresh_failure() -> None:
    data = _data()
    dev = data["strongest_dev_candidate"]
    fresh = data["decisive_fresh_confirmation"]

    assert dev["development_gate_passed"] is True
    assert dev["metrics"]["supported_exact_route_accuracy"] >= 0.85
    assert dev["metrics"]["false_route_rate"] <= 0.01

    assert fresh["promotion_gate_passed"] is False
    assert fresh["tuning_eligible"] is False
    assert fresh["metrics"]["near_domain_unsupported_rejection"] < 0.97
    assert fresh["metrics"]["false_route_rate"] > 0.01


def test_final_evaluation_is_unconsumed_when_fresh_gate_never_passed() -> None:
    data = _data()
    final = data["final_evaluation"]

    assert final["issue"] == 198
    assert final["calibration_run"] is False
    assert final["blind_final_run"] is False
    assert "entry requirement" in final["reason"]


def test_failed_fresh_surfaces_remain_non_tuning() -> None:
    data = _data()
    governance = data["governance"]

    assert governance["failed_fresh_surfaces_forbidden_for_tuning"] == [
        270,
        287,
        326,
    ]
    assert governance["terminal_families_must_not_be_repaired_posthoc"] is True
    assert governance["successor_requires_new_preregistration"] is True


def test_conservative_reference_is_not_mislabeled_as_target_pass() -> None:
    data = _data()
    reference = data["retained_conservative_reference"]

    assert reference["production_target_passed"] is False
    assert reference["metrics"]["supported_exact_route_accuracy"] < 0.85
    assert reference["metrics"]["false_route_rate"] <= 0.01
