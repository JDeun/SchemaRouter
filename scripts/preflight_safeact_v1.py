"""Verify official SafeAct V1 artifact identity without importing gold into runtime.

Use as a preflight command, not as a benchmark runner.
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

EXPECTED_SHA = "841816cf1e376e6fbf8600cffac5df1736e1d369"


def verify(root: Path) -> dict[str, object]:
    root = root.resolve()
    if not (root / "run_benchmark.py").is_file():
        raise ValueError("not a SafeAct checkout")
    result = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        capture_output=True, text=True, check=True,
    )
    sha = result.stdout.strip()
    if sha != EXPECTED_SHA:
        raise ValueError(f"unfrozen SafeAct revision: {sha}")
    dataset = json.loads((root / "data/safeact/cases.json").read_text(encoding="utf-8"))
    cases = dataset.get("cases")
    if not isinstance(cases, list):
        raise ValueError("missing official case list")
    v1 = [row for row in cases if isinstance(row, dict) and row.get("protocol") == "v1"]
    if len(v1) != 131:
        raise ValueError(f"expected 131 V1 cases, found {len(v1)}")
    ids = [row.get("case_id") for row in v1]
    if any(not isinstance(item, str) or not item for item in ids) or len(set(ids)) != len(ids):
        raise ValueError("invalid or duplicate V1 case IDs")
    return {"safeact_revision": sha, "protocol": "v1", "case_count": len(v1)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("safeact_checkout", type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(args.safeact_checkout), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
