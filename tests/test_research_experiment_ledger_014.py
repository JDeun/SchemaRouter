from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "benchmarks" / "research-experiment-ledger.json"


def _load() -> dict:
    return json.loads(LEDGER.read_text(encoding="utf-8"))


def _experiment(data: dict, experiment_id: str) -> dict:
    rows = {
        row["id"]: row
        for row in data["experiments"]
    }
    return rows[experiment_id]


def test_014_ledger_records_b1_as_terminal() -> None:
    data = _load()
    b1 = _experiment(data, "0.14-b1-local-agent-ab")

    assert b1["status"] == "terminal_canonical_b1"
    assert b1["result"]["episode_count"] == 552
    assert b1["result"]["sr5_required_route_recall"] == 1.0
    assert b1["result"]["sr5_all_required_task_coverage"] == 1.0
    assert b1["result"]["unauthorized_destructive_executions"] == 0


def test_014_ledger_keeps_b2_frozen_and_nonterminal() -> None:
    data = _load()
    b2 = _experiment(data, "0.14-b2-strong-agent-replication")

    assert b2["status"] == "attempt5_running_frozen_same_run_infra_recovery"
    assert b2["expected_episode_count"] == 460
    assert b2["semantic_task_count"] == 23
    assert b2["canonical_attempt5_workflow_run_id"] == 36561002246
    assert b2["observed_infrastructure_failures"]["partial_outcomes_used_for_tuning"] is False
    assert "attempt5_terminal" in b2["decision"]


def test_014_ledger_records_representation_negative_result() -> None:
    data = _load()
    typed = _experiment(data, "0.14-typed-representation-dev-ablation")

    assert typed["issue"] == 434
    assert typed["status"] == "terminal_no_promotion_confirmation_sealed"
    assert typed["result"]["confirmation_opened"] is False
    assert typed["result"]["typed_multifield"]["full_coverage_at_5_delta"] == 0.02
    assert typed["result"]["typed_multifield"]["repeated_p95_latency_ratio_approx"] > 1.5


def test_014_ledger_keeps_future_content_sealed() -> None:
    data = _load()
    heldout = _experiment(data, "0.14-large-held-out-generalization")
    answer = _experiment(data, "0.14-final-answer-quality")

    assert heldout["unique_semantic_tasks"] == 780
    assert heldout["corpus_content_generated"] is False

    assert answer["unique_semantic_tasks"] == 144
    assert answer["content_generation_authorized"] is False
    assert answer["answer_inference_authorized"] is False


def test_014_ledger_resume_rule_points_to_active_b2() -> None:
    data = _load()
    tracking = data["work_tracking"]

    assert tracking["current_cycle_status"] == (
        "b1_terminal_b2_strong_agent_infrastructure_recovery"
    )
    assert tracking["active_experiments"] == [423]
    assert 420 in tracking["completed_work"]
    assert 434 in tracking["completed_work"]
    assert 423 in tracking["infrastructure_in_progress"]
    assert "partial B2 outcomes" in tracking["session_resume_rule"]
