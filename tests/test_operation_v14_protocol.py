import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
V13_PROTOCOL = ROOT / "benchmarks" / "decision-routing-v13-blind-protocol.json"
V14_PROTOCOL = ROOT / "benchmarks" / "decision-routing-v14-blind-protocol.json"
CASCADE_CYCLE = ROOT / "benchmarks" / "operation-fit-0.10-cascade-cycle.json"
CASCADE_WORKFLOW = ROOT / ".github" / "workflows" / "research-operation-cascade.yml"


def test_v14_protocol_is_reserved_before_cascade_implementation() -> None:
    v13 = json.loads(V13_PROTOCOL.read_text(encoding="utf-8"))
    v14 = json.loads(V14_PROTOCOL.read_text(encoding="utf-8"))
    cycle = json.loads(CASCADE_CYCLE.read_text(encoding="utf-8"))

    assert v13["status"] == "consumed_blind_final"
    assert v13["tuning_eligible"] is False

    assert v14["status"] == "protocol_reserved_not_generated"
    assert v14["corpus_exists"] is False
    assert v14["tuning_eligible"] is False
    assert v14["cycle"] == "0.10-operation-cascade-v2"
    assert v14["selection_policy"]["candidate_selection_data"] == "v5 development split only"
    assert v14["selection_policy"]["candidate_confirmation_data"] == (
        "v5 calibration split only after candidate freeze"
    )
    assert v14["selection_policy"]["supported_operation_floor"] == 0.60
    assert v14["selection_policy"]["near_domain_unsupported_rejection_floor"] == 0.95

    assert cycle["status"] == "development_sweep_preregistered"
    assert cycle["selection"]["split"] == "dev"
    assert len(cycle["selection"]["candidate_grid"]) == 6
    assert cycle["confirmation"]["split"] == "calibration"
    assert cycle["blind_final"]["corpus_exists"] is False
    assert cycle["blind_final"]["run_allowed_only_after_candidate_freeze"] is True


def test_v14_has_no_checked_in_corpus_or_workflow_path() -> None:
    assert not (
        ROOT / "benchmarks" / "decision-routing-v14-operation-cascade-holdout.json"
    ).exists()

    workflows = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((ROOT / ".github" / "workflows").glob("*.yml"))
    )
    assert "decision-routing-v14-operation-cascade-holdout.json" not in workflows


def test_cascade_dev_workflow_is_v5_dev_only() -> None:
    workflow = CASCADE_WORKFLOW.read_text(encoding="utf-8")

    assert "benchmarks/decision-routing-v5-operation-calibration.json" in workflow
    assert "--split dev" in workflow
    assert "--split calibration" not in workflow
    assert "decision-routing-v12" not in workflow
    assert "decision-routing-v13" not in workflow
    assert "decision-routing-v14" not in workflow
    assert 'SCHEMAROUTER_BENCHMARK_CONTRASTIVE_BETA: "1.00"' in workflow
