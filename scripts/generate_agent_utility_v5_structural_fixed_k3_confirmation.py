"""Freeze fresh independent fixed-K3 confirmation content before scoring."""

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

from benchmarks.agent_utility_v5_catalog import (  # noqa: E402
    _core_tools,
    build_registry as build_dev_registry,
    build_tasks as build_dev_tasks,
)
from benchmarks.agent_utility_v5_structural_confirmation import (  # noqa: E402
    build_confirmation_registry as build_v2_registry,
    build_confirmation_tasks as build_v2_tasks,
)
from benchmarks.agent_utility_v5_structural_fixed_k3_confirmation import (  # noqa: E402
    CONFIRMATION_CATALOG_SIZES,
    CONFIRMATION_LANGUAGES,
    CONFIRMATION_STRATA,
    CONFIRMATION_TASKS_PER_CELL,
    build_fixed_k3_confirmation_registry,
    build_fixed_k3_confirmation_tasks,
)

PREREG = (
    ROOT
    / "benchmarks"
    / "agent-utility-v5-structural-fixed-k3-preregistration.json"
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


def freeze_confirmation(out_dir: Path) -> dict[str, Any]:
    prereg = json.loads(PREREG.read_text(encoding="utf-8"))
    if (
        prereg["status"]
        != "preregistered_before_fresh_confirmation_generation"
    ):
        raise RuntimeError(
            "fixed-K3 successor was not frozen before confirmation"
        )

    tasks = build_fixed_k3_confirmation_tasks()
    expected_tasks = int(
        prereg["confirmation_surface"]["semantic_task_count"]
    )
    if len(tasks) != expected_tasks:
        raise RuntimeError(
            f"fixed-K3 task count drifted: {len(tasks)} != {expected_tasks}"
        )

    cell_counts = Counter(
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
    if set(cell_counts) != expected_cells:
        raise RuntimeError("fixed-K3 confirmation cell set drifted")
    if set(cell_counts.values()) != {
        CONFIRMATION_TASKS_PER_CELL
    }:
        raise RuntimeError(
            "fixed-K3 confirmation cells are not balanced"
        )

    prior_queries = {
        _normalize_query(str(task["query"]))
        for task in build_dev_tasks()
    }
    prior_queries.update(
        _normalize_query(str(task["query"]))
        for task in build_v2_tasks()
    )
    fresh_queries = {
        _normalize_query(str(task["query"]))
        for task in tasks
    }
    query_overlap = sorted(fresh_queries & prior_queries)
    if query_overlap:
        raise RuntimeError(
            "fixed-K3 confirmation overlaps prior query surface: "
            + repr(query_overlap[:5])
        )

    canonical_routes = {
        f"{tool.key}.{endpoint.name}"
        for tool in _core_tools()
        for endpoint in tool.endpoints
    }
    prior_routes = (
        _route_ids(build_dev_registry(500))
        | _route_ids(build_v2_registry(500))
    )

    out_dir.mkdir(parents=True, exist_ok=True)
    tasks_path = out_dir / "confirmation-tasks.json"
    tasks_path.write_text(
        json.dumps(tasks, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    manifest: dict[str, Any] = {
        "schema_version": 1,
        "issue": 430,
        "experiment": prereg["experiment"],
        "surface": "fresh_confirmation",
        "status": "frozen_before_scoring",
        "preregistration_path": str(PREREG.relative_to(ROOT)),
        "preregistration_file_sha256": _file_sha(PREREG),
        "fixed_candidate": prereg["fixed_candidate"],
        "semantic_task_count": len(tasks),
        "task_rows_sha256": _sha(tasks),
        "languages": list(CONFIRMATION_LANGUAGES),
        "task_strata": list(CONFIRMATION_STRATA),
        "tasks_per_cell": CONFIRMATION_TASKS_PER_CELL,
        "cell_count": len(expected_cells),
        "exact_normalized_prior_query_overlap_count": 0,
        "catalogs": {},
        "prior_confirmation_rows_used_for_scoring": False,
        "b2_outcomes_used": False,
        "confirmation_metrics_used_for_tuning": False,
    }

    prior_fresh_routes: set[str] | None = None
    for size in CONFIRMATION_CATALOG_SIZES:
        registry = build_fixed_k3_confirmation_registry(size)
        routes = _route_ids(registry)
        if (
            prior_fresh_routes is not None
            and not prior_fresh_routes.issubset(routes)
        ):
            raise RuntimeError(
                "fixed-K3 confirmation catalogs must be nested"
            )
        prior_fresh_routes = routes

        overlap = routes & prior_routes
        if overlap != canonical_routes:
            unexpected = sorted(overlap - canonical_routes)
            raise RuntimeError(
                "fixed-K3 auxiliary routes overlap prior surfaces: "
                + ", ".join(unexpected[:10])
            )

        catalog = _catalog_payload(registry)
        endpoint_count = sum(
            len(tool.get("endpoints", []))
            for tool in catalog
        )
        if endpoint_count != size:
            raise RuntimeError(
                f"fixed-K3 catalog {size} drifted to {endpoint_count}"
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
            "shared_prior_route_count": len(overlap),
            "shared_prior_routes_are_canonical_only": True,
        }

    manifest["catalog_family_sha256"] = _sha(
        manifest["catalogs"]
    )
    (out_dir / "freeze-manifest.json").write_text(
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
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()

    manifest = freeze_confirmation(args.out_dir)
    print(
        json.dumps(
            {
                "task_rows_sha256": manifest[
                    "task_rows_sha256"
                ],
                "catalog_family_sha256": manifest[
                    "catalog_family_sha256"
                ],
                "exact_normalized_prior_query_overlap_count": (
                    manifest[
                        "exact_normalized_prior_query_overlap_count"
                    ]
                ),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
