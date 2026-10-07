from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_adaptive_context_scorer_preserves_frozen_protocol(tmp_path: Path) -> None:
    output = tmp_path / "results.json"
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/score_adaptive_context_evaluation.py",
            "--output",
            str(output),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0
    result = json.loads(output.read_text())
    metrics = result["metrics"]
    assert result["performance_evidence"] is False
    assert result["protocol_changed_after_scoring"] is False
    assert metrics["cold_start_matches_stateless"] is True
    assert metrics["frozen_history_checkpoint_unchanged"] is True
    assert metrics["stateless_required_tool_rank"] == 2
    assert metrics["frozen_history_required_tool_rank"] == 1
    assert metrics["duplicate_schema_injections"] == 0
    assert metrics["post_compaction_recovery"] is True
