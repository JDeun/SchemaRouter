"""Recreate and verify the exact canonical #420 benchmark freeze for #423 B2."""

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

from benchmarks.agent_utility_b2_catalog import (  # noqa: E402
    CATALOG_SIZES,
    TASKS,
    build_registry,
    route_ids,
)

EXPECTED_TASK_SHA = "bc0b78ff2be11b89e6ac54ea0ee336f944f04b3c203fc61da70a46ff48b4e03c"
EXPECTED_CATALOG_SHAS = {
    20: "b90e3ab473217f4becffb4933fc96e7016cf60f28b030b4d2ae8cb1639c40f5c",
    50: "e43400681d64315cadfeb54f4f3dadb0490e557e5f6bf2514c4f8e2e6d424ac3",
    100: "52b58b39ec31d377c90c16572997f69523742c8917a37e33326d429b51afc225",
    250: "e5ca7d199dd5d2e7bb89eb97d8ac0cae37f403def1fc43037f2fc816a775d2a9",
}


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _sha(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def task_rows() -> list[dict[str, Any]]:
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


def catalog_rows(size: int) -> list[dict[str, Any]]:
    registry = build_registry(size)
    return [
        tool.model_dump(mode="json")
        for tool in sorted(registry.tools(), key=lambda item: item.key)
    ]


def freeze(out_dir: Path) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)

    tasks = task_rows()
    tasks_sha = _sha(tasks)
    if tasks_sha != EXPECTED_TASK_SHA:
        raise RuntimeError(
            f"B2 task freeze drifted: {tasks_sha} != {EXPECTED_TASK_SHA}"
        )

    base_routes = set(route_ids(build_registry(20)))
    required = {
        route
        for task in TASKS
        for route in task.required_routes
    }
    if not required.issubset(base_routes):
        raise RuntimeError("B2 required routes drifted outside the 20-endpoint base catalog")

    (out_dir / "tasks.json").write_text(
        json.dumps(tasks, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    manifest: dict[str, Any] = {
        "schema_version": 1,
        "experiment": "0.14-agent-utility-b2-smollm3-v1",
        "issue": 423,
        "canonical_b1_source_sha": "b9eadefd3cd076f026a54bbc55a949f0424f5dab",
        "canonical_b1_workflow_run": 36529108855,
        "task_count": len(tasks),
        "single_task_count": sum(row["kind"] == "single" for row in tasks),
        "multi_task_count": sum(row["kind"] == "multi" for row in tasks),
        "tasks_sha256": tasks_sha,
        "catalogs": {},
    }

    for size in CATALOG_SIZES:
        catalog = catalog_rows(size)
        endpoint_count = sum(
            len(tool.get("endpoints", []))
            for tool in catalog
        )
        if endpoint_count != size:
            raise RuntimeError(
                f"B2 catalog {size} endpoint count drifted to {endpoint_count}"
            )
        actual_sha = _sha(catalog)
        expected_sha = EXPECTED_CATALOG_SHAS[size]
        if actual_sha != expected_sha:
            raise RuntimeError(
                f"B2 catalog {size} drifted: {actual_sha} != {expected_sha}"
            )
        (out_dir / f"catalog-{size}.json").write_text(
            json.dumps(catalog, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        manifest["catalogs"][str(size)] = {
            "tool_count": len(catalog),
            "endpoint_count": endpoint_count,
            "sha256": actual_sha,
        }

    (out_dir / "freeze-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(freeze(args.out_dir), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
