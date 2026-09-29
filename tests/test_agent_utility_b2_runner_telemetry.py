from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AMENDMENT = (
    ROOT
    / "benchmarks"
    / "agent-utility-v1-b2-runner-telemetry-amendment.json"
)
WORKFLOW = ROOT / ".github" / "workflows" / "research-0.14-b2-smollm3-full.yml"


def test_b2_runner_telemetry_is_diagnostic_only() -> None:
    data = json.loads(AMENDMENT.read_text(encoding="utf-8"))

    assert data["issue"] == 423
    assert data["activation"] == {
        "attempt5_same_run_retries_take_precedence": True,
        "apply_to_current_attempt5": False,
        "only_for_future_new_workflow_attempt_if_needed": True,
    }

    assert data["telemetry"]["interval_seconds"] == 60
    assert data["governance"]["telemetry_must_not_read_or_branch_on_task_outcomes"] is True
    assert data["governance"]["telemetry_must_not_change_candidate_visibility"] is True
    assert data["governance"]["benchmark_rows_must_not_be_selected_or_removed_from_telemetry"] is True

    assert all(value is False for value in data["frozen_semantics"].values())


def test_b2_workflow_keeps_frozen_execution_shape_with_telemetry() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "max-parallel: 6" in text
    assert "timeout-minutes: 180" in text
    assert "benchmarks/agent-utility-v1-b2-sharding-resilient.json" in text
    assert '/usr/bin/time -v python scripts/evaluate_agent_utility_phase_b_smollm3.py' in text
    assert 'sleep 60' in text
    assert 'free -m || true' in text
    assert 'df -h . /tmp || true' in text
    assert 'ps -eo pid,ppid,rss,vsz,%mem,%cpu,cmd --sort=-rss' in text
