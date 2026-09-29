"""Freeze the #430 adaptive-shortlist DEV surface before scoring."""

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

from benchmarks.agent_utility_b2_catalog import TASKS as B2_TASKS  # noqa: E402
from benchmarks.agent_utility_v2_catalog import development_rows  # noqa: E402
from benchmarks.agent_utility_v5_catalog import (  # noqa: E402
    CATALOG_SIZES,
    LANGUAGES,
    STRATA,
    TASKS_PER_CELL,
    build_registry,
    build_tasks,
)

PREREG = (
    ROOT
    / "benchmarks"
    / "agent-utility-v5-adaptive-shortlist-preregistration.json"
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


def _file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _normalize_query(value: str) -> str:
    return " ".join(value.lower().split())


def _route_ids(registry: Any) -> set[str]:
    return {
        f"{tool.key}.{endpoint.name}"
        for tool in registry.tools()
        for endpoint in tool.endpoints
    }


def _validate_tasks(tasks: list[dict[str, Any]]) -> None:
    if len(tasks) != 240:
        raise RuntimeError(f"expected 240 DEV tasks, found {len(tasks)}")

    cell_counts = Counter(
        (str(task["task_stratum"]), str(task["language"]))
        for task in tasks
    )
    expected_cells = {
        (stratum, language)
        for stratum in STRATA
        for language in LANGUAGES
    }
    if set(cell_counts) != expected_cells:
        raise RuntimeError("adaptive DEV stratum/language cell set drifted")
    if set(cell_counts.values()) != {TASKS_PER_CELL}:
        raise RuntimeError(
            f"adaptive DEV cell balance drifted: {dict(cell_counts)}"
        )

    supported = set(STRATA[:-2])
    unsupported = set(STRATA[-2:])
    base_routes = _route_ids(build_registry(min(CATALOG_SIZES)))
    for task in tasks:
        stratum = str(task["task_stratum"])
        required = {
            str(route)
            for route in task["required_route_ids"]
        }
        if stratum in supported and not required:
            raise RuntimeError(
                f"{task['task_id']} supported task has no required route"
            )
        if stratum in unsupported and required:
            raise RuntimeError(
                f"{task['task_id']} unsupported task declares required route"
            )
        missing = sorted(required - base_routes)
        if missing:
            raise RuntimeError(
                f"{task['task_id']} gold routes missing from all catalogs: "
                + ", ".join(missing)
            )

    new_queries = {
        _normalize_query(str(task["query"]))
        for task in tasks
    }
    prior_queries = {
        _normalize_query(str(row["query"]))
        for row in development_rows()
    }
    prior_queries.update(
        _normalize_query(str(task.query))
        for task in B2_TASKS
    )
    overlap = sorted(new_queries & prior_queries)
    if overlap:
        raise RuntimeError(
            "adaptive DEV query exact-overlap with prior benchmark: "
            + repr(overlap[:5])
        )


def freeze_dev(out_dir: Path) -> dict[str, Any]:
    prereg = json.loads(PREREG.read_text(encoding="utf-8"))
    tasks = build_tasks()
    _validate_tasks(tasks)
    out_dir.mkdir(parents=True, exist_ok=True)

    tasks_path = out_dir / "dev-tasks.json"
    tasks_path.write_text(
        json.dumps(tasks, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    manifest: dict[str, Any] = {
        "schema_version": 1,
        "experiment": prereg["experiment"],
        "issue": 430,
        "surface": "development",
        "status": "frozen_before_scoring",
        "preregistration_path": str(PREREG.relative_to(ROOT)),
        "preregistration_file_sha256": _file_sha(PREREG),
        "semantic_task_count": len(tasks),
        "task_rows": len(tasks),
        "languages": list(LANGUAGES),
        "task_strata": list(STRATA),
        "tasks_per_cell": TASKS_PER_CELL,
        "cell_count": len(STRATA) * len(LANGUAGES),
        "task_rows_sha256": _sha(tasks),
        "exact_prior_query_overlap_count": 0,
        "catalogs": {},
    }

    prior_routes: set[str] | None = None
    for size in CATALOG_SIZES:
        registry = build_registry(size)
        catalog = [
            tool.model_dump(mode="json")
            for tool in sorted(registry.tools(), key=lambda item: item.key)
        ]
        routes = _route_ids(registry)
        if prior_routes is not None and not prior_routes.issubset(routes):
            raise RuntimeError("adaptive catalogs are not nested")
        prior_routes = routes

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
            "endpoint_count": endpoint_count,
            "tool_count": len(catalog),
            "sha256": _sha(catalog),
        }

    manifest["catalog_family_sha256"] = _sha(manifest["catalogs"])
    manifest_path = out_dir / "freeze-manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    manifest = freeze_dev(args.out_dir)
    print(json.dumps(manifest, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
