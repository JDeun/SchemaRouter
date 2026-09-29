"""Freeze the #434 DEV surface without opening the confirmation surface."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmarks.agent_utility_v2_catalog import (  # noqa: E402
    CATALOG_SIZES,
    DEVELOPMENT_TASKS,
    LANGUAGES,
    STRATA,
    build_registry,
    development_rows,
)

PREREG_PATH = ROOT / "benchmarks" / "agent-utility-v2-representation-preregistration.json"


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _sha(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _route_ids(endpoint_count: int) -> set[str]:
    registry = build_registry(endpoint_count)
    return {
        f"{tool.key}.{endpoint.name}"
        for tool in registry.tools()
        for endpoint in tool.endpoints
    }


def _validate_dev_surface() -> None:
    if len(DEVELOPMENT_TASKS) != 60:
        raise RuntimeError(
            f"DEV semantic task count drifted: {len(DEVELOPMENT_TASKS)}"
        )

    counts = Counter(task.stratum for task in DEVELOPMENT_TASKS)
    expected = {stratum: 5 for stratum in STRATA}
    if dict(sorted(counts.items())) != dict(sorted(expected.items())):
        raise RuntimeError(
            f"DEV stratum balance drifted: expected={expected} actual={dict(counts)}"
        )

    ids = [task.semantic_task_id for task in DEVELOPMENT_TASKS]
    if len(ids) != len(set(ids)):
        raise RuntimeError("DEV semantic_task_id values must be unique")

    for task in DEVELOPMENT_TASKS:
        if set(task.queries) != set(LANGUAGES):
            raise RuntimeError(
                f"{task.semantic_task_id} language renderings drifted: "
                f"{sorted(task.queries)}"
            )
        if task.supported and not task.required_routes:
            raise RuntimeError(
                f"{task.semantic_task_id} is supported but has no required route"
            )
        if not task.supported and task.required_routes:
            raise RuntimeError(
                f"{task.semantic_task_id} is unsupported but declares gold routes"
            )

    base_routes = _route_ids(min(CATALOG_SIZES))
    missing = sorted(
        route
        for task in DEVELOPMENT_TASKS
        if task.supported
        for route in task.required_routes
        if route not in base_routes
    )
    if missing:
        raise RuntimeError(
            "all supported DEV gold routes must exist in every catalog stratum: "
            + ", ".join(missing)
        )

    rows = development_rows()
    if len(rows) != 360:
        raise RuntimeError(f"DEV row count drifted: {len(rows)}")


def freeze_dev(out_dir: Path) -> dict[str, Any]:
    _validate_dev_surface()
    out_dir.mkdir(parents=True, exist_ok=True)

    task_rows = development_rows()
    task_path = out_dir / "dev-tasks.json"
    task_path.write_text(
        json.dumps(task_rows, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    semantic_manifest = [
        {
            "semantic_task_id": task.semantic_task_id,
            "stratum": task.stratum,
            "required_routes": list(task.required_routes),
            "supported": task.supported,
        }
        for task in DEVELOPMENT_TASKS
    ]

    manifest: dict[str, Any] = {
        "schema_version": 1,
        "experiment": "typed-multifield-intent-manual-retrieval-ablation-v1",
        "issue": 434,
        "surface": "development",
        "confirmation_surface_opened": False,
        "preregistration_path": str(PREREG_PATH.relative_to(ROOT)),
        "preregistration_file_sha256": _file_sha(PREREG_PATH),
        "semantic_task_count": len(DEVELOPMENT_TASKS),
        "rows": len(task_rows),
        "languages": list(LANGUAGES),
        "strata": list(STRATA),
        "stratum_semantic_task_count": 5,
        "semantic_manifest_sha256": _sha(semantic_manifest),
        "dev_rows_sha256": _sha(task_rows),
        "catalogs": {},
    }

    for size in CATALOG_SIZES:
        registry = build_registry(size)
        catalog = [
            tool.model_dump(mode="json")
            for tool in sorted(registry.tools(), key=lambda item: item.key)
        ]
        endpoint_count = sum(
            len(tool.get("endpoints", []))
            for tool in catalog
        )
        if endpoint_count != size:
            raise RuntimeError(
                f"catalog {size} endpoint count drifted to {endpoint_count}"
            )
        path = out_dir / f"catalog-{size}.json"
        path.write_text(
            json.dumps(catalog, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        manifest["catalogs"][str(size)] = {
            "tool_count": len(catalog),
            "endpoint_count": endpoint_count,
            "sha256": _sha(catalog),
        }

    manifest_path = out_dir / "freeze-manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--surface",
        choices=("development", "confirmation"),
        default="development",
    )
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()

    if args.surface == "confirmation":
        raise SystemExit(
            "confirmation generation is sealed until a representation candidate "
            "and its generator revision are frozen under #434"
        )

    manifest = freeze_dev(args.out_dir)
    print(json.dumps(manifest, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
