"""Freeze #418 Phase-A tasks and catalog strata before evaluation."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmarks.agent_utility_v1_catalog import (  # noqa: E402
    CATALOG_SIZES,
    TASKS,
    build_registry,
    route_ids,
)


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _sha(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _task_rows() -> list[dict[str, Any]]:
    return [
        {
            "task_id": task.task_id,
            "query": task.query,
            "required_routes": list(task.required_routes),
            "kind": task.kind,
            "expected_answer": task.expected_answer,
        }
        for task in TASKS
    ]


def _catalog_rows(size: int) -> list[dict[str, Any]]:
    registry = build_registry(size)
    return [
        tool.model_dump(mode="json")
        for tool in sorted(registry.tools(), key=lambda item: item.key)
    ]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    tasks = _task_rows()
    base_routes = set(route_ids(build_registry(20)))
    required = {
        route
        for task in TASKS
        for route in task.required_routes
    }
    if not required.issubset(base_routes):
        raise RuntimeError(
            "all required routes must exist in the 20-endpoint base catalog"
        )

    task_path = args.out_dir / "tasks.json"
    task_path.write_text(
        json.dumps(tasks, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    manifest: dict[str, Any] = {
        "experiment": "0.14-agent-utility-phase-a-v1",
        "issue": 418,
        "task_count": len(tasks),
        "single_task_count": sum(row["kind"] == "single" for row in tasks),
        "multi_task_count": sum(row["kind"] == "multi" for row in tasks),
        "tasks_sha256": _sha(tasks),
        "catalogs": {},
    }

    for size in CATALOG_SIZES:
        catalog = _catalog_rows(size)
        endpoint_count = sum(
            len(tool.get("endpoints", []))
            for tool in catalog
        )
        if endpoint_count != size:
            raise RuntimeError(
                f"catalog {size} endpoint count drifted to {endpoint_count}"
            )
        path = args.out_dir / f"catalog-{size}.json"
        path.write_text(
            json.dumps(catalog, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        manifest["catalogs"][str(size)] = {
            "tool_count": len(catalog),
            "endpoint_count": endpoint_count,
            "sha256": _sha(catalog),
        }

    (args.out_dir / "freeze-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
