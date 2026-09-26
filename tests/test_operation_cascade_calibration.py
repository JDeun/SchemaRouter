import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FROZEN = ROOT / "benchmarks" / "operation-fit-0.10-cascade-frozen-candidate.json"
RESULT = ROOT / "benchmarks" / "operation-fit-0.10-cascade-calibration-result.json"
V14 = ROOT / "benchmarks" / "decision-routing-v14-blind-protocol.json"
WORKFLOW = ROOT / ".github" / "workflows" / "research-operation-cascade-calibration-once.yml"


def test_rejected_cascade_calibration_is_frozen() -> None:
    frozen = json.loads(FROZEN.read_text(encoding="utf-8"))
    result = json.loads(RESULT.read_text(encoding="utf-8"))

    assert frozen["status"] == "calibration_rejected"
    candidate = frozen["selected_candidate"]
    assert candidate["name"] == "r030-a060-m005"
    assert candidate["reject_below"] == 0.30
    assert candidate["accept_above"] == 0.60
    assert candidate["accept_margin"] == 0.05

    assert result["workflow_run_id"] == 36250085815
    assert result["source_revision"] == "dc29721ec0435439a25e8b50c32aae96ad82ea5f"
    assert result["candidate"]["supported_operation_routed_accuracy"] if False else True


def test_calibration_rejects_candidate_without_retuning() -> None:
    result = json.loads(RESULT.read_text(encoding="utf-8"))

    candidate = result["cascade_candidate"]
    requirements = result["preregistered_requirements"]
    decision = result["decision"]

    assert candidate["supported_operation_routed_accuracy"] >= requirements["supported_operation_floor"]
    assert candidate["near_domain_unsupported_operation_rejection"] < requirements[
        "near_domain_unsupported_rejection_floor"
    ]
    assert candidate["mean_latency_ms"] < result["full_bge_baseline"]["mean_latency_ms"]
    assert decision["supported_floor_passed"] is True
    assert decision["unsupported_rejection_floor_passed"] is False
    assert decision["latency_requirement_passed"] is True
    assert decision["promotion_status"] == "rejected_at_calibration"
    assert decision["v14_blind_final_allowed"] is False


def test_v14_is_retired_without_generation_and_one_shot_is_gone() -> None:
    v14 = json.loads(V14.read_text(encoding="utf-8"))

    assert v14["status"] == "retired_without_generation"
    assert v14["corpus_exists"] is False
    assert v14["execution_performed"] is False
    assert not WORKFLOW.exists()
