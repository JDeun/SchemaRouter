"""Regression for the standalone GitHub Actions conveyor entrypoint.

The production workflow runs `python scripts/research_014_conveyor.py`,
not `python -m scripts.research_014_conveyor`.  Python then puts scripts/
on sys.path, not the project root.  Exercise that environment in an isolated
subprocess so ordinary pytest imports cannot mask a missing bootstrap.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_conveyor_script_bootstraps_repo_package_import(tmp_path: Path) -> None:
    script = (
        Path(__file__).resolve().parents[1] / "scripts/research_014_conveyor.py"
    )
    probe = (
        "import runpy, sys; "
        "runpy.run_path(sys.argv[1], run_name='conveyor_import_probe'); "
        "from scripts.research_014_heldout_recovery "
        "import AGGREGATE_RESCUE_RUN; "
        "assert AGGREGATE_RESCUE_RUN == 38342986866"
    )
    result = subprocess.run(
        [sys.executable, "-I", "-c", probe, str(script)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr
