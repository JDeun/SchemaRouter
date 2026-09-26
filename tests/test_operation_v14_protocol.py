import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
V13_PROTOCOL = ROOT / "benchmarks" / "decision-routing-v13-blind-protocol.json"
V14_PROTOCOL = ROOT / "benchmarks" / "decision-routing-v14-blind-protocol.json"
CASCADE_CYCLE = ROOT / "benchmarks" / "operation-fit-0.10-cascade-cycle.json"
CALIBRATION_RESULT = (
    ROOT / "benchmarks" / "operation-fit-0.10-cascade-calibration-result.json"
)


def test_v14_protocol_is_retired_without_generation() -> None:
    v13 = json.loads(V13_PROTOCOL.read_text(encoding="utf-8"))
    v14 = json.loads(V14_PROTOCOL.read_text(encoding="utf-8"))
    cycle = json.loads(CASCADE_CYCLE.read_text(encoding="utf-8"))
    result = json.loads(CALIBRATION_RESULT.read_text(encoding="utf-8"))

    assert v13["status"] == "consumed_blind_final"
    assert v13["tuning_eligible"] is False

    assert v14["status"] == "retired_not_generated_after_candidate_rejection"
    assert v14["corpus_exists"] is False
    assert v14["tuning_eligible"] is False
    assert v14["cycle"] == "0.10-operation-cascade-v2"
    assert v14["retirement"]["corpus_generated"] is False
    assert v14["retirement"]["blind_final_executed"] is False
    assert v14["retirement"]["reusable_for_future_cycle"] is False
    assert v14["retirement"]["workflow_run_id"] == result["workflow_run_id"]

    assert cycle["status"] == "paired_calibration_rejected_cycle_closed"
    assert cycle["confirmation"]["promotion_passed"] is False
    assert cycle["blind_final"]["corpus_exists"] is False
    assert cycle["blind_final"]["run_allowed"] is False
    assert cycle["blind_final"]["disposition"] == (
        "retired_without_generation_after_calibration_rejection"
    )


def test_v14_has_no_checked_in_corpus_or_runnable_workflow_path() -> None:
    assert not (
        ROOT / "benchmarks" / "decision-routing-v14-operation-cascade-holdout.json"
    ).exists()

    workflows = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((ROOT / ".github" / "workflows").glob("*.yml"))
    )
    assert "decision-routing-v14-operation-cascade-holdout.json" not in workflows
    assert "V14 Blind Final" not in workflows
    assert "Operation Cascade Dev Sweep" not in workflows
    assert "Operation Cascade Calibration" not in workflows
