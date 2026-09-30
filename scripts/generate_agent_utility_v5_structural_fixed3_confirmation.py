"""Freeze the fresh structural fixed-K=3 v4 confirmation surface."""

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
    build_registry,
    build_tasks,
)
from benchmarks.agent_utility_v5_structural_confirmation import (  # noqa: E402
    build_confirmation_registry,
    build_confirmation_tasks,
)
from benchmarks.agent_utility_v5_structural_fixed3_confirmation import (  # noqa: E402
    FIXED3_CONFIRM_CATALOG_SIZES,
    FIXED3_CONFIRM_LANGUAGES,
    FIXED3_CONFIRM_STRATA,
    FIXED3_CONFIRM_TASKS_PER_CELL,
    build_fixed3_confirmation_registry,
    build_fixed3_confirmation_tasks,
)

PREREG = (
    ROOT
    / "benchmarks"
    / "agent-utility-v5-structural-fixed3-v4-preregistration.json"
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


def _normalize_query(value: str) -> str:
    return " ".join(value.casefold().split())


def _routes(registry: Any) -> set[str]:
    return {
        f"{tool.key}.{endpoint.name}"
        for tool in registry.tools()
        for endpoint in tool.endpoints
    }


def freeze_fixed3_confirmation(out_dir: Path) -> dict[str, Any]:
    prereg = json.loads(PREREG.read_text(encoding="utf-8"))
    if (
        prereg["status"]
        != "preregistered_before_fresh_confirmation_surface_generation"
    ):
        raise RuntimeError("fixed3 v4 preregistration is not frozen")

    tasks = build_fixed3_confirmation_tasks()
    expected = int(
        prereg["confirmation_surface"]["semantic_task_count"]
    )
    if len(tasks) != expected:
        raise RuntimeError(
            f"expected {expected} tasks, found {len(tasks)}"
        )

    counts = Counter(
        (task["task_stratum"], task["language"])
        for task in tasks
    )
    expected_cells = {
        (stratum, language)
        for stratum in FIXED3_CONFIRM_STRATA
        for language in FIXED3_CONFIRM_LANGUAGES
    }
    if set(counts) != expected_cells:
        raise RuntimeError("fixed3 confirmation cell set drifted")
    if set(counts.values()) != {
        FIXED3_CONFIRM_TASKS_PER_CELL
    }:
        raise RuntimeError("fixed3 confirmation cell balance drifted")

    supported = set(FIXED3_CONFIRM_STRATA[:-2])
    unsupported = set(FIXED3_CONFIRM_STRATA[-2:])
    for task in tasks:
        required = list(task["required_route_ids"])
        if task["task_stratum"] in supported and not required:
            raise RuntimeError(
                f"{task['task_id']}: supported task has no gold route"
            )
        if task["task_stratum"] in unsupported and required:
            raise RuntimeError(
                f"{task['task_id']}: unsupported task has gold routes"
            )

    new_queries = {
        _normalize_query(str(task["query"]))
        for task in tasks
    }
    dev_queries = {
        _normalize_query(str(task["query"]))
        for task in build_tasks()
    }
    prior_confirmation_queries = {
        _normalize_query(str(task["query"]))
        for task in build_confirmation_tasks()
    }
    if new_queries & dev_queries:
        raise RuntimeError("fixed3 confirmation overlaps adaptive DEV queries")
    if new_queries & prior_confirmation_queries:
        raise RuntimeError(
            "fixed3 confirmation overlaps structural-v2 confirmation queries"
        )

    canonical_routes = {
        f"{tool.key}.{endpoint.name}"
        for tool in _core_tools()
        for endpoint in tool.endpoints
    }
    prior_dev_routes = _routes(build_registry(500))
    prior_confirmation_routes = _routes(
        build_confirmation_registry(500)
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
        "semantic_task_count": len(tasks),
        "cell_count": len(counts),
        "tasks_per_cell": FIXED3_CONFIRM_TASKS_PER_CELL,
        "task_rows_sha256": _sha(tasks),
        "exact_normalized_adaptive_dev_query_overlap_count": 0,
        "exact_normalized_structural_v2_confirmation_query_overlap_count": 0,
        "confirmation_rows_inspected_before_freeze": False,
        "confirmation_metrics_used_for_tuning": False,
        "b2_outcomes_used": False,
        "catalogs": {},
    }

    prior: set[str] | None = None
    for size in FIXED3_CONFIRM_CATALOG_SIZES:
        registry = build_fixed3_confirmation_registry(size)
        routes = _routes(registry)
        if prior is not None and not prior < routes:
            raise RuntimeError("fixed3 confirmation catalogs are not nested")
        prior = routes

        overlap_dev = routes & prior_dev_routes
        overlap_prior_confirmation = (
            routes & prior_confirmation_routes
        )
        if overlap_dev != canonical_routes:
            raise RuntimeError(
                "fixed3 confirmation reuses noncanonical DEV route identity"
            )
        if overlap_prior_confirmation != canonical_routes:
            raise RuntimeError(
                "fixed3 confirmation reuses prior auxiliary route identity"
            )

        catalog = [
            tool.model_dump(mode="json")
            for tool in sorted(
                registry.tools(),
                key=lambda item: item.key,
            )
        ]
        endpoint_count = sum(
            len(tool["endpoints"])
            for tool in catalog
        )
        if endpoint_count != size:
            raise RuntimeError(
                f"catalog {size} drifted to {endpoint_count} endpoints"
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
            "shared_prior_routes_are_canonical_only": True,
            "shared_prior_route_count": len(canonical_routes),
        }

    manifest["catalog_family_sha256"] = _sha(
        manifest["catalogs"]
    )
    (out_dir / "freeze-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    manifest = freeze_fixed3_confirmation(args.out_dir)
    print(json.dumps(manifest, sort_keys=True))


if __name__ == "__main__":
    main()
