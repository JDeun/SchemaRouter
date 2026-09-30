"""Freeze the independent structural-v2 confirmation surface before scoring."""

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

from benchmarks import agent_utility_v5_catalog as dev_catalog  # noqa: E402
from benchmarks.agent_utility_v5_structural_confirmation import (  # noqa: E402
    CONFIRMATION_CATALOG_SIZES,
    CONFIRMATION_LANGUAGES,
    CONFIRMATION_STRATA,
    CONFIRMATION_TASKS_PER_CELL,
    build_confirmation_registry,
    build_confirmation_tasks,
)

PREREG = (
    ROOT
    / "benchmarks"
    / "agent-utility-v5-structural-retrieval-v2-preregistration.json"
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
    return " ".join(value.casefold().split())


def _route_ids(registry: Any) -> set[str]:
    return {
        f"{tool.key}.{endpoint.name}"
        for tool in registry.tools()
        for endpoint in tool.endpoints
    }


def _catalog_payload(registry: Any) -> list[dict[str, Any]]:
    return [
        tool.model_dump(mode="json")
        for tool in sorted(
            registry.tools(),
            key=lambda item: item.key,
        )
    ]


def _validate_tasks(
    tasks: list[dict[str, Any]],
) -> None:
    if len(tasks) != 240:
        raise RuntimeError(
            f"expected 240 confirmation tasks, found {len(tasks)}"
        )

    ids = [str(task["task_id"]) for task in tasks]
    if len(ids) != len(set(ids)):
        raise RuntimeError(
            "confirmation semantic task IDs must be unique"
        )

    queries = [
        _normalize_query(str(task["query"]))
        for task in tasks
    ]
    if len(queries) != len(set(queries)):
        raise RuntimeError(
            "confirmation normalized queries must be unique"
        )

    counts = Counter(
        (
            str(task["task_stratum"]),
            str(task["language"]),
        )
        for task in tasks
    )
    expected_cells = {
        (stratum, language)
        for stratum in CONFIRMATION_STRATA
        for language in CONFIRMATION_LANGUAGES
    }
    if set(counts) != expected_cells:
        raise RuntimeError(
            "confirmation stratum/language cells drifted"
        )
    if set(counts.values()) != {
        CONFIRMATION_TASKS_PER_CELL
    }:
        raise RuntimeError(
            "confirmation stratum/language cells are not balanced"
        )

    supported = set(CONFIRMATION_STRATA[:-2])
    unsupported = set(CONFIRMATION_STRATA[-2:])
    core_routes = _route_ids(
        build_confirmation_registry(
            min(CONFIRMATION_CATALOG_SIZES)
        )
    )
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
                f"{task['task_id']} unsupported task declares a required route"
            )
        missing = sorted(required - core_routes)
        if missing:
            raise RuntimeError(
                f"{task['task_id']} requires missing routes: "
                + ", ".join(missing)
            )

    dev_queries = {
        _normalize_query(str(task["query"]))
        for task in dev_catalog.build_tasks()
    }
    overlap = sorted(set(queries) & dev_queries)
    if overlap:
        raise RuntimeError(
            "confirmation has exact normalized query overlap with DEV: "
            + repr(overlap[:5])
        )


def freeze_confirmation(
    out_dir: Path,
) -> dict[str, Any]:
    prereg = json.loads(PREREG.read_text(encoding="utf-8"))
    if (
        prereg["status"]
        != "preregistered_before_confirmation_surface_generation"
    ):
        raise RuntimeError(
            "structural v2 candidate was not frozen before confirmation"
        )

    tasks = build_confirmation_tasks()
    _validate_tasks(tasks)

    out_dir.mkdir(parents=True, exist_ok=True)
    tasks_path = out_dir / "confirmation-tasks.json"
    tasks_path.write_text(
        json.dumps(tasks, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    dev_500 = dev_catalog.build_registry(500)
    dev_routes = _route_ids(dev_500)
    dev_core_routes = {
        f"{tool.key}.{endpoint.name}"
        for tool in dev_catalog._core_tools()  # noqa: SLF001
        for endpoint in tool.endpoints
    }

    manifest: dict[str, Any] = {
        "schema_version": 1,
        "issue": 430,
        "experiment": prereg["experiment"],
        "surface": "confirmation",
        "status": "frozen_before_scoring",
        "preregistration_path": str(PREREG.relative_to(ROOT)),
        "preregistration_file_sha256": _file_sha(PREREG),
        "fixed_candidate": prereg["fixed_candidate"],
        "semantic_task_count": len(tasks),
        "task_rows_sha256": _sha(tasks),
        "languages": list(CONFIRMATION_LANGUAGES),
        "task_strata": list(CONFIRMATION_STRATA),
        "tasks_per_cell": CONFIRMATION_TASKS_PER_CELL,
        "cell_count": (
            len(CONFIRMATION_STRATA)
            * len(CONFIRMATION_LANGUAGES)
        ),
        "exact_normalized_dev_query_overlap_count": 0,
        "catalogs": {},
        "confirmation_rows_inspected_before_freeze": False,
        "confirmation_metrics_used_for_tuning": False,
    }

    prior_routes: set[str] | None = None
    for size in CONFIRMATION_CATALOG_SIZES:
        registry = build_confirmation_registry(size)
        routes = _route_ids(registry)
        if prior_routes is not None and not prior_routes.issubset(
            routes
        ):
            raise RuntimeError(
                "confirmation catalogs must be nested"
            )
        prior_routes = routes

        catalog = _catalog_payload(registry)
        endpoint_count = sum(
            len(tool.get("endpoints", []))
            for tool in catalog
        )
        if endpoint_count != size:
            raise RuntimeError(
                "confirmation catalog endpoint count drifted: "
                f"{endpoint_count} != {size}"
            )

        shared_with_dev = routes & dev_routes
        if shared_with_dev != dev_core_routes:
            unexpected = sorted(
                shared_with_dev - dev_core_routes
            )
            raise RuntimeError(
                "confirmation auxiliary routes overlap DEV: "
                + ", ".join(unexpected[:10])
            )

        path = out_dir / f"catalog-{size}.json"
        path.write_text(
            json.dumps(
                catalog,
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        manifest["catalogs"][str(size)] = {
            "endpoint_count": endpoint_count,
            "tool_count": len(catalog),
            "sha256": _sha(catalog),
            "shared_dev_route_count": len(
                shared_with_dev
            ),
            "shared_dev_routes_are_canonical_only": True,
        }

    manifest["catalog_family_sha256"] = _sha(
        manifest["catalogs"]
    )
    manifest_path = out_dir / "freeze-manifest.json"
    manifest_path.write_text(
        json.dumps(
            manifest,
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--out-dir",
        type=Path,
        required=True,
    )
    args = parser.parse_args()

    manifest = freeze_confirmation(args.out_dir)
    print(
        json.dumps(
            {
                "semantic_task_count": manifest[
                    "semantic_task_count"
                ],
                "task_rows_sha256": manifest[
                    "task_rows_sha256"
                ],
                "catalog_family_sha256": manifest[
                    "catalog_family_sha256"
                ],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
