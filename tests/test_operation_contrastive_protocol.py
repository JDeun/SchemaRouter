import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FROZEN = ROOT / "benchmarks" / "operation-fit-0.10-frozen-candidate.json"
CYCLE = ROOT / "benchmarks" / "operation-fit-0.10-cycle.json"
V13_RESULT = ROOT / "benchmarks" / "operation-fit-0.10-v13-result.json"
CALIBRATION_WORKFLOW = (
    ROOT / ".github" / "workflows" / "research-operation-contrastive-calibration.yml"
)
DEV_WORKFLOW = ROOT / ".github" / "workflows" / "research-operation-contrastive.yml"


def test_frozen_candidate_remains_beta_one_historical_evidence() -> None:
    frozen = json.loads(FROZEN.read_text(encoding="utf-8"))

    assert frozen["selected_candidate"]["beta"] == 1.0
    assert frozen["selected_candidate"]["operation_fit_min_score"] == 0.01
    assert frozen["selected_candidate"]["operation_fit_min_margin"] == 0.0
    assert frozen["frozen_from_dev_run"]["selection_split"] == "dev"


def test_contrastive_cycle_is_closed_after_consumed_v13() -> None:
    cycle = json.loads(CYCLE.read_text(encoding="utf-8"))
    result = json.loads(V13_RESULT.read_text(encoding="utf-8"))

    assert cycle["status"] == "blind_final_passed_cycle_closed"
    assert cycle["final_evidence"]["result"] == "benchmarks/operation-fit-0.10-v13-result.json"
    assert cycle["final_evidence"]["tuning_eligible"] is False
    assert result["status"] == "consumed_blind_final"
    assert result["tuning_eligible"] is False
    assert result["supported_operation_routed_accuracy"] == 0.6171875
    assert result["near_domain_unsupported_operation_rejection"] == 0.984375


def test_consumed_contrastive_workflows_are_retired() -> None:
    cycle = json.loads(CYCLE.read_text(encoding="utf-8"))

    assert cycle["retirement"]["development_workflow_removed"] is True
    assert cycle["retirement"]["calibration_workflow_removed"] is True
    assert not DEV_WORKFLOW.exists()
    assert not CALIBRATION_WORKFLOW.exists()
