import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
V15_PROTOCOL = ROOT / "benchmarks" / "decision-routing-v15-blind-protocol.json"
REJECT_ONLY_CYCLE = ROOT / "benchmarks" / "operation-fit-0.10-reject-only-cycle.json"


def test_v15_is_reserved_before_reject_only_implementation() -> None:
    protocol = json.loads(V15_PROTOCOL.read_text(encoding="utf-8"))
    cycle = json.loads(REJECT_ONLY_CYCLE.read_text(encoding="utf-8"))

    assert protocol["status"] == "protocol_reserved_not_generated"
    assert protocol["corpus_exists"] is False
    assert protocol["tuning_eligible"] is False
    assert protocol["selection_policy"]["candidate_selection_data"] == "v5 development split only"
    assert protocol["selection_policy"]["candidate_confirmation_data"] == (
        "v5 calibration split only after candidate freeze"
    )
    assert protocol["candidate_family"]["prohibited_fast_path"].startswith(
        "MiniLM may not fast-accept"
    )

    assert cycle["status"] == "design_reserved_before_implementation"
    assert cycle["selection"]["split"] == "dev"
    assert [item["reject_below"] for item in cycle["selection"]["candidate_grid"]] == [
        0.10,
        0.15,
        0.20,
        0.25,
        0.30,
    ]
    assert cycle["confirmation"]["split"] == "calibration"
    assert cycle["blind_final"]["corpus_exists"] is False
    assert cycle["blind_final"]["run_allowed_only_after_candidate_freeze"] is True


def test_v15_has_no_generated_corpus_or_workflow_path() -> None:
    assert not (
        ROOT / "benchmarks" / "decision-routing-v15-operation-reject-only-holdout.json"
    ).exists()

    workflows = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((ROOT / ".github" / "workflows").glob("*.yml"))
    )
    assert "decision-routing-v15-operation-reject-only-holdout.json" not in workflows
