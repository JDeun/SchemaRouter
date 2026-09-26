import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CYCLE = ROOT / "benchmarks" / "operation-fit-0.10-cascade-cycle.json"
WORKFLOW = ROOT / ".github" / "workflows" / "research-operation-cascade-calibration.yml"


def test_cascade_candidate_is_frozen_before_calibration() -> None:
    cycle = json.loads(CYCLE.read_text(encoding="utf-8"))
    selected = cycle["selection"]["selected_candidate"]

    assert cycle["status"] == "candidate_selected_and_frozen_before_calibration"
    assert cycle["selection"]["selection_locked"] is True
    assert selected == {
        "name": "r030-a060-m005",
        "reject_below": 0.3,
        "accept_above": 0.6,
        "accept_margin": 0.05,
        "bge_beta": 1,
        "pairwise_min_score": 0.01,
        "pairwise_min_margin": 0,
    }
    assert cycle["confirmation"]["candidate_changes_allowed"] is False


def test_calibration_is_v5_only_and_uses_one_paired_job() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "paired-calibration:" in workflow
    assert "benchmarks/decision-routing-v5-operation-calibration.json" in workflow
    assert workflow.count("--split calibration") == 2
    assert "--split dev" not in workflow
    assert "decision-routing-v12" not in workflow
    assert "decision-routing-v13" not in workflow
    assert "decision-routing-v14" not in workflow
    assert "Run full-BGE v5 calibration baseline" in workflow
    assert "Run frozen cascade v5 calibration candidate" in workflow
    assert workflow.index("Run full-BGE v5 calibration baseline") < workflow.index(
        "Run frozen cascade v5 calibration candidate"
    )


def test_calibration_locks_exact_candidate_and_promotion_gates() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert 'SCHEMAROUTER_BENCHMARK_CASCADE_REJECT_BELOW: "0.30"' in workflow
    assert 'SCHEMAROUTER_BENCHMARK_CASCADE_ACCEPT_ABOVE: "0.60"' in workflow
    assert 'SCHEMAROUTER_BENCHMARK_CASCADE_ACCEPT_MARGIN: "0.05"' in workflow
    assert 'SCHEMAROUTER_BENCHMARK_CONTRASTIVE_BETA: "1.00"' in workflow
    assert "supported_floor = 0.60" in workflow
    assert "rejection_floor = 0.95" in workflow
    assert 'candidate["mean_latency_ms"] < baseline["mean_latency_ms"]' in workflow
    assert "promotion_passed = bool(quality_passed and latency_passed)" in workflow
