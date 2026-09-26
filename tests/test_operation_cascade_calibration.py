import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FROZEN = ROOT / "benchmarks" / "operation-fit-0.10-cascade-frozen-candidate.json"
WORKFLOW = ROOT / ".github" / "workflows" / "research-operation-cascade-calibration-once.yml"


def test_cascade_candidate_is_frozen_before_calibration() -> None:
    frozen = json.loads(FROZEN.read_text(encoding="utf-8"))

    assert frozen["status"] == "candidate_frozen_before_calibration"
    candidate = frozen["selected_candidate"]
    assert candidate["name"] == "r030-a060-m005"
    assert candidate["reject_below"] == 0.30
    assert candidate["accept_above"] == 0.60
    assert candidate["accept_margin"] == 0.05
    assert candidate["bge_beta"] == 1.0
    assert candidate["pairwise_min_score"] == 0.01
    assert candidate["pairwise_min_margin"] == 0.0

    calibration = frozen["calibration"]
    assert calibration["split"] == "calibration"
    assert calibration["supported_operation_floor"] == 0.60
    assert calibration["near_domain_unsupported_rejection_floor"] == 0.95
    assert calibration["candidate_changes_allowed"] is False


def test_cascade_calibration_workflow_is_fixed_and_holdout_isolated() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "benchmarks/decision-routing-v5-operation-calibration.json" in workflow
    assert workflow.count("--split calibration") == 2
    assert "--split dev" not in workflow
    assert "benchmarks.bge_contrastive:score_pairs" in workflow
    assert "benchmarks.bge_cascade:score_pairs" in workflow
    assert 'SCHEMAROUTER_BENCHMARK_CASCADE_REJECT_BELOW: "0.30"' in workflow
    assert 'SCHEMAROUTER_BENCHMARK_CASCADE_ACCEPT_ABOVE: "0.60"' in workflow
    assert 'SCHEMAROUTER_BENCHMARK_CASCADE_ACCEPT_MARGIN: "0.05"' in workflow
    assert "decision-routing-v12" not in workflow
    assert "decision-routing-v13" not in workflow
    assert "decision-routing-v14" not in workflow
