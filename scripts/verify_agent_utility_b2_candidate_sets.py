"""Verify #423 B2 candidate sets exactly reproduce canonical #420 B1."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmarks.agent_utility_b2_catalog import (  # noqa: E402
    CATALOG_SIZES,
    TASKS,
    build_registry,
    route_ids,
)
from scripts.evaluate_agent_utility_phase_a import _rank  # noqa: E402

EXPECTED_SHA256 = "9bea0645f64ec726abe5983d9a19eefe12afb1ab6cfae65ecd87464f545f0176"
EXPECTED_ROWS = 92


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def candidate_manifest() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for size in CATALOG_SIZES:
        registry = build_registry(size)
        full = sorted(route_ids(registry))
        for task in TASKS:
            ranked = _rank(registry, task.query)
            ranking = [str(row["route_id"]) for row in ranked]
            rows.append(
                {
                    "catalog_size": size,
                    "task_id": task.task_id,
                    "full": full,
                    "top3": sorted(ranking[:3]),
                    "top5": sorted(ranking[:5]),
                    "top10": sorted(ranking[:10]),
                    "oracle": sorted(task.required_routes),
                }
            )
    rows.sort(key=lambda row: (row["catalog_size"], row["task_id"]))
    return rows


def verify() -> dict[str, Any]:
    rows = candidate_manifest()
    actual = hashlib.sha256(_canonical(rows)).hexdigest()
    if len(rows) != EXPECTED_ROWS:
        raise RuntimeError(
            f"B2 candidate manifest row count drifted: {len(rows)} != {EXPECTED_ROWS}"
        )
    if actual != EXPECTED_SHA256:
        raise RuntimeError(
            f"B2 candidate-set identity drifted: {actual} != {EXPECTED_SHA256}"
        )
    return {
        "rows": len(rows),
        "sha256": actual,
        "status": "pass",
    }


def main() -> None:
    print(json.dumps(verify(), sort_keys=True))


if __name__ == "__main__":
    main()
