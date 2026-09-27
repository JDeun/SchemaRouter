from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_long_term_operation_routing_targets_are_locked() -> None:
    target = json.loads(
        (ROOT / "benchmarks" / "operation-routing-production-targets.json").read_text(
            encoding="utf-8"
        )
    )
    final_targets = target["final_targets"]

    assert final_targets["supported_exact_route_accuracy"]["target_min"] == 0.85
    assert final_targets["unsupported_rejection"]["target_range"] == [0.97, 0.99]
    assert final_targets["false_route_rate"]["target_max"] == 0.01
    assert final_targets["invalid_plan_rate"]["target_max"] == 0.0
    assert final_targets["execution_authority_violation_rate"]["target_max"] == 0.0
    assert target["governance"]["current_cycle_gates_must_not_be_changed_retroactively"] is True
    assert target["governance"]["calibration_and_blind_sets_must_not_be_used_for_tuning"] is True


def test_next_cycle_is_design_only_and_does_not_generate_fresh_data() -> None:
    plan = json.loads(
        (ROOT / "benchmarks" / "operation-routing-next-cycle-design.json").read_text(
            encoding="utf-8"
        )
    )

    assert plan["stage"] == "design_only"
    assert plan["status"] == "design_only_no_corpus_generated"
    assert plan["objective"]["supported_exact_route_accuracy_min"] == 0.70
    assert plan["objective"]["near_domain_unsupported_rejection_min"] == 0.96
    assert plan["objective"]["false_route_rate_max"] == 0.02
    assert plan["research_hygiene"]["corpus_generation"].startswith(
        "Do not generate the next cycle"
    )
    assert plan["promotion"]["candidate_freeze_before_calibration"] is True
    assert plan["promotion"]["calibration_pass_before_blind_generation"] is True
