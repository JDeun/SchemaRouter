from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "benchmark_decision_routing.py"


def test_benchmark_cli_exposes_generic_system_one_options() -> None:
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
    output = completed.stdout
    assert "--system-one-base-url" in output
    assert "--system-one-model" in output
    assert "--system-one-provider" in output
    assert "--system-one-timeout" in output
    assert "--system-one-min-confidence" in output
    assert "--system-one-api-key-env" in output
