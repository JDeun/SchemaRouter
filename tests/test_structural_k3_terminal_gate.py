from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "research-0.14-structural-k3-agent.yml"
PREREG = (
    ROOT
    / "benchmarks"
    / "agent-utility-v5-structural-fixed3-agent-preregistration.json"
)


def test_k3_autolaunch_requires_successful_canonical_b2() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "github.event.workflow_run.id == 36642658406" in text
    assert "github.event.workflow_run.conclusion == 'success'" in text
    assert 'assert run["status"] == "completed"' in text
    assert 'assert run["conclusion"] == "success"' in text


def test_k3_preregistration_freezes_success_requirement() -> None:
    data = json.loads(PREREG.read_text(encoding="utf-8"))

    assert data["independence"]["canonical_b2_run"] == 36642658406
    assert data["independence"]["b2_terminal_required_before_launch"] is True
    assert data["independence"]["b2_success_required_before_launch"] is True
    assert data["execution_governance"]["canonical_b2_success_required"] is True
    assert (
        data["execution_freeze"][
            "auto_launch_requires_canonical_b2_conclusion"
        ]
        == "success"
    )
