import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CYCLE = ROOT / "benchmarks" / "operation-fit-0.10-cascade-cycle.json"
RESULT = ROOT / "benchmarks" / "operation-fit-0.10-cascade-calibration-result.json"
CALIBRATION_WORKFLOW = (
    ROOT / ".github" / "workflows" / "research-operation-cascade-calibration.yml"
)
DEV_WORKFLOW = ROOT / ".github" / "workflows" / "research-operation-cascade.yml"


def test_rejected_cascade_cycle_is_closed_without_retuning() -> None:
    cycle = json.loads(CYCLE.read_text(encoding="utf-8"))
    result = json.loads(RESULT.read_text(encoding="utf-8"))

    assert cycle["status"] == "paired_calibration_rejected_cycle_closed"
    assert cycle["selection"]["selection_locked"] is True
    assert cycle["confirmation"]["candidate_changes_allowed"] is False
    assert cycle["confirmation"]["completed"] is True
    assert cycle["confirmation"]["promotion_passed"] is False
    assert cycle["confirmation"]["result_manifest"] == (
        "benchmarks/operation-fit-0.10-cascade-calibration-result.json"
    )

    assert result["status"] == "paired_calibration_rejected"
    assert result["tuning_eligible"] is False
    assert result["frozen_candidate"]["name"] == "r030-a060-m005"
    assert result["workflow_run_id"] == 36251542594
    assert result["artifact_id"] == 10909651834
    assert result["decision"]["promotion_passed"] is False
    assert result["decision"]["blind_final_allowed"] is False


def test_paired_calibration_confirmed_speed_but_failed_quality_floor() -> None:
    result = json.loads(RESULT.read_text(encoding="utf-8"))
    baseline = result["full_bge_baseline"]
    candidate = result["frozen_cascade_candidate"]

    assert candidate["supported_operation_routed_accuracy"] >= 0.60
    assert candidate["near_domain_unsupported_operation_rejection"] == 91 / 96
    assert candidate["near_domain_unsupported_operation_rejection"] < 0.95
    assert baseline["near_domain_unsupported_operation_rejection"] == 94 / 96
    assert candidate["mean_latency_ms"] < baseline["mean_latency_ms"]
    assert result["mean_latency_reduction_vs_full_bge_fraction"] > 0.14
    assert result["decision"]["latency_gate_passed"] is True
    assert result["decision"]["quality_gate_passed"] is False


def test_consumed_cascade_workflows_are_retired() -> None:
    assert not CALIBRATION_WORKFLOW.exists()
    assert not DEV_WORKFLOW.exists()
