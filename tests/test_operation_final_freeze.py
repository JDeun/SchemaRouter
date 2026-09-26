import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIRMED = ROOT / "benchmarks" / "operation-fit-0.10-confirmed-candidate.json"
V13_PROTOCOL = ROOT / "benchmarks" / "decision-routing-v13-blind-protocol.json"


def test_operation_candidate_is_frozen_before_v13_generation() -> None:
    confirmed = json.loads(CONFIRMED.read_text(encoding="utf-8"))
    protocol = json.loads(V13_PROTOCOL.read_text(encoding="utf-8"))

    assert confirmed["status"] == "candidate_confirmed_and_frozen_before_blind_final"
    assert confirmed["selected_candidate"]["beta"] == 1.0
    assert confirmed["selected_candidate"]["operation_fit_min_score"] == 0.01
    assert confirmed["selected_candidate"]["operation_fit_min_margin"] == 0.0
    assert confirmed["calibration_confirmation"]["workflow_run_id"] == 36245567627
    assert confirmed["calibration_confirmation"]["artifact_id"] == 10907402275
    assert confirmed["decision"]["calibration_passed_both_floors"] is True

    assert protocol["status"] == "protocol_reserved_not_generated"
    assert protocol["corpus_exists"] is False
    assert protocol["tuning_eligible"] is False
    assert protocol["generation_timing"] == "only_after_complete_candidate_configuration_is_frozen"
