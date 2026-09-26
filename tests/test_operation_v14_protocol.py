import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
V13_PROTOCOL = ROOT / "benchmarks" / "decision-routing-v13-blind-protocol.json"
V14_PROTOCOL = ROOT / "benchmarks" / "decision-routing-v14-blind-protocol.json"
CASCADE_CYCLE = ROOT / "benchmarks" / "operation-fit-0.10-cascade-cycle.json"


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

    assert cycle["status"] == "design_reserved_before_implementation"
    assert cycle["selection"]["split"] == "dev"
    assert cycle["confirmation"]["split"] == "calibration"
    assert cycle["blind_final"]["corpus_exists"] is False
    assert cycle["blind_final"]["run_allowed_only_after_candidate_freeze"] is True


def test_v14_has_no_checked_in_corpus_or_workflow_path() -> None:
    assert not (
        ROOT / "benchmarks" / "decision-routing-v14-operation-cascade-holdout.json"
    ).exists()

    workflows = "
".join(
        path.read_text(encoding="utf-8")
        for path in sorted((ROOT / ".github" / "workflows").glob("*.yml"))
    )
    assert "decision-routing-v14-operation-cascade-holdout.json" not in workflows
