import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIRMED = ROOT / "benchmarks" / "operation-fit-0.10-confirmed-candidate.json"
V13_PROTOCOL = ROOT / "benchmarks" / "decision-routing-v13-blind-protocol.json"
V13_RESULT = ROOT / "benchmarks" / "operation-fit-0.10-v13-result.json"


def test_operation_candidate_freeze_precedes_consumed_v13() -> None:
    confirmed = json.loads(CONFIRMED.read_text(encoding="utf-8"))
    protocol = json.loads(V13_PROTOCOL.read_text(encoding="utf-8"))
    result = json.loads(V13_RESULT.read_text(encoding="utf-8"))

    assert confirmed["status"] == "candidate_confirmed_and_frozen_before_blind_final"
    assert confirmed["selected_candidate"]["beta"] == 1.0
    assert confirmed["selected_candidate"]["operation_fit_min_score"] == 0.01
    assert confirmed["selected_candidate"]["operation_fit_min_margin"] == 0.0
    assert confirmed["calibration_confirmation"]["workflow_run_id"] == 36245567627
    assert confirmed["decision"]["calibration_passed_both_floors"] is True

    assert protocol["status"] == "consumed_blind_final"
    assert protocol["corpus_exists"] is True
    assert protocol["tuning_eligible"] is False
    assert protocol["consumed_run_id"] == 36246386089
    assert protocol["consumed_corpus_sha256"] == result["corpus_sha256"]
    assert result["candidate_freeze_revision"] == "14e1977011c5b926476731736f7a4a9e1876367a"
    assert result["tuning_eligible"] is False
