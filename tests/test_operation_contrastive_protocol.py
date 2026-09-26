import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FROZEN = ROOT / "benchmarks" / "operation-fit-0.10-frozen-candidate.json"
CALIBRATION_WORKFLOW = (
    ROOT / ".github" / "workflows" / "research-operation-contrastive-calibration.yml"
)
V12 = "decision-routing-v12-operation-contrastive-holdout.json"
V13 = "decision-routing-v13"


def test_frozen_candidate_is_beta_one_and_uses_only_v5_calibration() -> None:
    frozen = json.loads(FROZEN.read_text(encoding="utf-8"))
    workflow = CALIBRATION_WORKFLOW.read_text(encoding="utf-8")

    assert frozen["status"] == "candidate_frozen_before_calibration"
    assert frozen["selected_candidate"]["beta"] == 1.0
    assert frozen["selected_candidate"]["operation_fit_min_score"] == 0.01
    assert frozen["selected_candidate"]["operation_fit_min_margin"] == 0.0
    assert "--split calibration" in workflow
    assert "benchmarks/decision-routing-v5-operation-calibration.json" in workflow
    assert 'SCHEMAROUTER_BENCHMARK_CONTRASTIVE_BETA: "1.00"' in workflow


def test_calibration_workflow_cannot_touch_future_evidence() -> None:
    workflow = CALIBRATION_WORKFLOW.read_text(encoding="utf-8")

    assert V12 not in workflow
    assert V13 not in workflow
    assert "--split dev" not in workflow
