"""Research 0.14 conveyor does not depend on GITHUB_TOKEN event recursion.

This is a workflow-only, outcome-blind regression: no real model or data read.
"""
from __future__ import annotations

from pathlib import Path


def test_downstream_resumes_after_bot_dispatched_heldout_completes():
    workflow = (
        Path(__file__).resolve().parents[1]
        / ".github/workflows/research-0.14-conveyor.yml"
    ).read_text(encoding="utf-8")

    assert 'cron: "7,27,47 * * * *"' in workflow
    assert "workflow_run:" in workflow
    assert "Research 0.14 Held-out Shard Recovery" in workflow
    assert "workflow_dispatch:" in workflow
    assert "group: research-0.14-conveyor" in workflow
    assert "cancel-in-progress: false" in workflow
    assert "--execute" in workflow
    assert 'ref: main' in workflow


def test_successful_original_aggregate_artifact_is_a_read_only_stage_input():
    controller = (
        Path(__file__).resolve().parents[1]
        / "scripts/research_014_conveyor.py"
    ).read_text(encoding="utf-8")
    assert "select_verified_heldout_recovery" in controller
    assert "heldout_artifact = api.artifact" in controller
    assert "heldout_digest = _artifact_digest(heldout_artifact)" in controller
    assert 'actions.append("dispatch_final_answer")' in controller
    assert "find_marked_runs(api, FINAL_WORKFLOW, heldout_digest)" in controller
