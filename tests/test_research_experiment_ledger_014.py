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


def test_014_ledger_points_to_canonical_b2_attempt9() -> None:
    data = _load()
    b2 = _experiment(data, "0.14-b2-strong-agent-replication")

    assert b2["status"] == "attempt9_running_canonical_arm64_sdpa"
    assert b2["canonical_attempt9_workflow_run_id"] == 36642658406
    assert b2["expected_episode_count"] == 460
    assert b2["execution_infrastructure"]["runner"] == "ubuntu-24.04-arm"
    assert b2["execution_infrastructure"]["attention_implementation"] == "sdpa"
    assert b2["prior_attempts"]["prior_partial_outcomes_used_for_tuning"] is False


def test_014_ledger_records_structural_retrieval_confirmation() -> None:
    data = _load()
    result = _experiment(data, "0.14-structural-retrieval-v2")

    assert result["status"] == "terminal_independent_confirmation_passed"
    assert result["candidate"] == "STRUCT-4.5-1.5"
    assert result["confirmation"]["workflow_run"] == 36648848734
    assert result["confirmation"]["recall_at_10"] == {
        "100": 1,
        "250": 1,
        "500": 1,
    }
    assert result["confirmation"]["full_coverage_at_10"] == {
        "100": 1,
        "250": 1,
        "500": 1,
    }


def test_014_ledger_records_fixed3_fresh_confirmation() -> None:
    data = _load()
    result = _experiment(data, "0.14-structural-fixed3-v4")

    assert result["status"] == "terminal_fresh_confirmation_passed"
    assert result["workflow_run"] == 36653940042
    assert result["result"]["recall"]["500"] > 0.99
    assert result["result"]["full_coverage"]["500"] > 0.98
    assert result["result"]["schema_token_reduction_vs_fixed5_fraction"] > 0.35
    assert result["result"]["passed"] is True


def test_014_ledger_freezes_k3_downstream_until_b2_terminal() -> None:
    data = _load()
    result = _experiment(
        data,
        "0.14-structural-fixed3-agent-utility-v5",
    )

    assert result["status"] == (
        "preregistered_frozen_waiting_canonical_b2_terminal"
    )
    assert result["canonical_b2_run"] == 36642658406
    assert result["expected_episode_count"] == 184
    assert result["result"] is None


def test_014_ledger_keeps_future_surfaces_sealed() -> None:
    data = _load()
    corrective = _experiment(
        data,
        "0.14-corrective-state-aware-reretrieval",
    )
    heldout = _experiment(data, "0.14-large-held-out-generalization")
    answer = _experiment(data, "0.14-final-answer-quality")

    assert corrective["scaffold"]["content_generation_authorized"] is False
    assert corrective["scaffold"]["execution_authorized"] is False
    assert heldout["corpus_content_generated"] is False
    assert answer["content_generation_authorized"] is False
    assert answer["answer_inference_authorized"] is False


def test_014_session_resume_rule_points_to_attempt9() -> None:
    tracking = _load()["work_tracking"]

    assert tracking["active_experiments"] == [423]
    assert tracking["infrastructure_in_progress"] == [423]
    assert tracking["current_cycle_status"] == (
        "b2_attempt9_running_structural_k3_downstream_frozen_terminal_gated"
    )
    assert "36642658406" in tracking["session_resume_rule"]
    assert "partial B2 row outcomes" in tracking["session_resume_rule"]
