from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--adapter", required=True)
    parser.add_argument("--json-out", required=True, type=Path)
    parser.add_argument("tests", nargs="+")
    args = parser.parse_args()

    started = datetime.now(timezone.utc)
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", *args.tests],
        check=False,
    )
    finished = datetime.now(timezone.utc)

    report = {
        "adapter": args.adapter,
        "source": "repository-local deterministic contract tests",
        "status": "success" if completed.returncode == 0 else "failure",
        "generated_at": finished.isoformat(),
        "details": {
            "evidence_kind": "local_reference_contract",
            "provider": "repository fixtures",
            "discovery_success": completed.returncode == 0,
            "execution_success": completed.returncode == 0,
            "test_paths": args.tests,
            "duration_ms": round(
                (finished - started).total_seconds() * 1000,
                3,
            ),
        },
    }
    if completed.returncode != 0:
        report["error_type"] = "ReferenceContractTestFailure"

    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
