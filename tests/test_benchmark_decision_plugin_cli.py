from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "benchmark_decision_routing.py"


def test_benchmark_cli_exposes_decision_plugin_options() -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )

    assert "--decision-plugin" in completed.stdout
    assert "--decision-plugin-config-env" in completed.stdout
