"""Run the native static ServiceNow readonly-package exposure baseline."""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from statistics import median
from typing import Any


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _materialize(contracts: list[dict[str, Any]]) -> bytes:
    return json.dumps(
        contracts,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def run(*, package_dir: Path, snapshot_path: Path, repeats: int | None) -> dict[str, Any]:
    manifest = _load(package_dir / "manifest.json")
    cases = _load(package_dir / manifest["files"]["cases"])
    snapshot = _load(snapshot_path)
    repeats = int(manifest["comparison"]["latency_repeats"]) if repeats is None else repeats
    if repeats < 1:
        raise ValueError("repeats must be positive")

    tools = snapshot["tools"]
    names = [tool["name"] for tool in tools]

    rows: list[dict[str, Any]] = []
    for case in cases["cases"]:
        _materialize(tools)
        durations: list[float] = []
        for _ in range(repeats):
            start = time.perf_counter()
            candidate_tools = list(names)
            visible_contracts = list(tools)
            _materialize(visible_contracts)
            durations.append((time.perf_counter() - start) * 1000.0)

        rows.append(
            {
                "id": case["id"],
                "candidate_tools": candidate_tools,
                "visible_contracts": visible_contracts,
                "latency_ms": median(durations),
            }
        )

    return {
        "schema_version": 1,
        "package_id": manifest["package_id"],
        "implementation": {
            "name": "ServiceNow Platform MCP static readonly package",
            "commit": snapshot["source"]["commit"],
            "commit_source": "frozen_snapshot",
            "fixture_reference_revision": manifest["source_revisions"]["servicenow_platform_mcp"],
            "package_version": snapshot["source"].get("package_version"),
            "configuration": {
                "condition": "static_readonly",
                "tool_package": "readonly",
                "tool_count": len(tools),
                "repeats_per_query": repeats,
                "execution": "disabled",
                "latency_boundary": "static selection + canonical native-contract materialization",
            },
        },
        "index_build_ms": 0.0,
        "results": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package-dir", required=True, type=Path)
    parser.add_argument("--snapshot", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--repeats", type=int)
    args = parser.parse_args()

    payload = run(
        package_dir=args.package_dir,
        snapshot_path=args.snapshot,
        repeats=args.repeats,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(args.out)


if __name__ == "__main__":
    main()
