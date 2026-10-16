"""Current-API candidate-pool coverage ceiling before more AutoResearch reranking.

This is observable, previously exposed synthetic multilingual DEV, NOT a new
independent test. Oracle ceiling is diagnostic only; task gold is never sent
to the planner, candidate generator, authorization decision or agent.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import subprocess
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

from benchmarks.agent_utility_v5_catalog import (
    CATALOG_SIZES,
    LANGUAGES,
    TASKS_PER_CELL,
    build_registry,
    build_tasks,
)
from schemarouter import PlanRequest, SchemaPlanner
from scripts.research_current_main_multilingual_dev import (
    encoded,
    select_cases,
)

ROOT = Path(__file__).resolve().parents[1]
POOL_SIZES = (24, 64, 128)
EXPOSED_K = 5
SOURCE_FILES = (
    "scripts/research_candidate_pool_ceiling_dev.py",
    "benchmarks/agent_utility_v5_catalog.py",
    "src/schemarouter/planner.py",
    "src/schemarouter/models.py",
)
CLAIMS = {
    "corpus": "previously_exposed_generated_v5_DEV",
    "oracle": "upper_bound_only_not_runtime_or_achieved_performance",
    "independent_confirmation": False,
    "real_provider_integrations": False,
    "principal_scope_qualification": False,
    "required_output_field_gold": False,
    "agent_task_success": False,
    "executable_tool_calls": 0,
    "may_promote_to_product": False,
    "may_release": False,
}


def percentile(values: list[float], rank: float = 0.95) -> float:
    if not values or any(not math.isfinite(value) or value < 0 for value in values):
        raise ValueError("invalid runtime measurements")
    ordered = sorted(values)
    index = math.ceil(len(ordered) * rank) - 1
    return sorted(values)[index]


def measure_case(
    *,
    case: dict[str, Any],
    retrieved_ids: list[str],
    all_routes: set[str],
    width: int,
    retrieval_ms: float,
) -> dict[str, Any]:
    if width not in POOL_SIZES or not math.isfinite(retrieval_ms) or retrieval_ms < 0:
        raise ValueError("unregistered candidate pool width or time")
    if (
        len(retrieved_ids) > width or len(retrieved_ids) != len(set(retrieved_ids))
        or any(type(route) is not str or route not in all_routes for route in retrieved_ids)
    ):
        raise ValueError("unregistered, duplicate, or overexposed candidate")
    gold = case["required_route_ids"]
    if not set(gold) <= all_routes or len(gold) != len(set(gold)):
        raise ValueError("non-registered or repeated task gold")
    head = set(retrieved_ids[:EXPOSED_K])
    visible = set(retrieved_ids)
    actual = len(set(gold) & head)
    attainable = min(len(set(gold) & visible), EXPOSED_K)
    return {
        "task_id": case["task_id"], "language": case["language"],
        "stratum": case["task_stratum"], "pool": width,
        "required": len(gold), "visible_in_pool": len(set(gold) & visible),
        "actually_in_top5": actual,
        "top5_observed_full_coverage": bool(gold) and actual == len(gold),
        "top5_oracle_upper_bound_found": attainable,
        "top5_oracle_upper_bound_full_coverage": bool(gold) and attainable == len(gold),
        "missing_from_pool": sorted(set(gold) - visible),
        "retrieval_ms": round(retrieval_ms, 6),
        "returned_route_ids": retrieved_ids,
    }


def cohort_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        raise ValueError("empty cohort")
    supported = [row for row in rows if row["required"]]
    denominator = sum(row["required"] for row in supported)
    return {
        "cases": len(rows), "supported_cases": len(supported),
        "required_route_count": denominator,
        "pool_route_recall": (
            sum(row["visible_in_pool"] for row in supported) / denominator
            if denominator else None
        ),
        "actual_top5_route_recall": (
            sum(row["actually_in_top5"] for row in supported) / denominator
            if denominator else None
        ),
        "potential_top5_oracle_recall": (
            sum(row["top5_oracle_upper_bound_found"] for row in supported) / denominator
            if denominator else None
        ),
        "actual_top5_full_coverage": (
            sum(row["top5_observed_full_coverage"] for row in supported) / len(supported)
            if supported else None
        ),
        "potential_top5_oracle_full_coverage": (
            sum(row["top5_oracle_upper_bound_full_coverage"] for row in supported)
            / len(supported) if supported else None
        ),
        "missing_gold_from_pool": sum(
            len(row["missing_from_pool"]) for row in supported
        ),
        "retrieval_p95_ms": round(percentile([row["retrieval_ms"] for row in rows]), 6),
    }


def evaluate(*, cases_per_group: int = 1) -> dict[str, Any]:
    if type(cases_per_group) is not int or not 1 <= cases_per_group <= TASKS_PER_CELL:
        raise ValueError("cases_per_group outside preregistered visible DEV")
    tasks = build_tasks()
    selected = select_cases(tasks, cases_per_group=cases_per_group)
    rows: list[dict[str, Any]] = []
    candidate_pool_prefix_changes: list[dict[str, Any]] = []
    for size in CATALOG_SIZES:
        registry = build_registry(size)
        all_routes = {
            f"{tool.key}.{endpoint.name}"
            for tool in registry.tools() for endpoint in tool.endpoints
        }
        if len(all_routes) != size:
            raise ValueError("registered catalog count differs")
        planner = SchemaPlanner(registry)
        planner._index()
        for case in selected:
            observed: dict[int, list[str]] = {}
            for width in POOL_SIZES:
                started = time.perf_counter_ns()
                selection = planner.retrieve(PlanRequest(query=case["query"]), k=width)
                elapsed = (time.perf_counter_ns() - started) / 1_000_000
                if selection.registry_version != registry.version:
                    raise ValueError("registry snapshot changed")
                if selection.requested_k != width:
                    raise ValueError("candidate width returned differs")
                chosen = [item.route_id for item in selection.candidates]
                observed[width] = chosen
                scored = measure_case(
                    case=case, retrieved_ids=chosen, all_routes=all_routes,
                    width=width, retrieval_ms=elapsed,
                )
                scored["catalog_size"] = size
                rows.append(scored)
            # The planner can make K-sensitive choices. Record discrepancies,
            # do not silently assume 24 is an exact prefix of 64/128.
            for smaller, larger in zip(POOL_SIZES, POOL_SIZES[1:], strict=False):
                if observed[smaller] != observed[larger][:len(observed[smaller])]:
                    candidate_pool_prefix_changes.append({
                        "catalog_size": size, "task_id": case["task_id"],
                        "smaller": smaller, "larger": larger,
                    })
    cohort = [
        {
            "catalog_size": size, "pool": width, "language": lang,
            **cohort_summary([
                row for row in rows
                if row["catalog_size"] == size
                and row["pool"] == width and row["language"] == lang
            ]),
        }
        for size in CATALOG_SIZES for width in POOL_SIZES for lang in LANGUAGES
    ]
    source_sha = {
        path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
        for path in SOURCE_FILES
    }
    git_commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
        text=True, check=True, timeout=10,
    ).stdout.strip()
    return {
        "schema_version": 1,
        "id": "current-API-candidate-pool-ceiling-visible-DEV",
        "scope": CLAIMS.copy(),
        "source_commit": git_commit,
        "source_file_sha256": source_sha,
        "corpus_sha256": hashlib.sha256(encoded(tasks)).hexdigest(),
        "hardware": {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "cpu_count": os.cpu_count(),
            "github_run_id": os.environ.get("GITHUB_RUN_ID"),
        },
        "candidate_pools": list(POOL_SIZES),
        "exposure_k": EXPOSED_K,
        "catalog_sizes": list(CATALOG_SIZES),
        "cases_per_language_stratum": cases_per_group,
        "actual_retrieval_calls": len(rows),
        "cohorts": cohort,
        "candidate_pool_prefix_changes": candidate_pool_prefix_changes,
        "raw_cases": rows,
        "interpretation": (
            "Upper bounds use previously exposed task gold for analysis only."
            " They are NOT achieved scores and cannot be used as runtime features."
            " This study cannot prove independent multilingual, field, authorization"
            " or downstream agent task performance."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases-per-group", type=int, default=1)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = evaluate(cases_per_group=args.cases_per_group)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    for row in result["cohorts"]:
        if row["language"] in ("en", "ko", "ja") and row["catalog_size"] == 500:
            print(json.dumps({
                "language": row["language"],
                "catalog_size": row["catalog_size"],
                "pool": row["pool"],
                "actual_top5_recall": row["actual_top5_route_recall"],
                "oracle_top5_ceiling": row["potential_top5_oracle_recall"],
                "missing_gold": row["missing_gold_from_pool"],
                "retrieval_p95_ms": row["retrieval_p95_ms"],
            }))
    print(json.dumps({
        "status": "EXPOSED_DEV_ONLY", "calls": result["actual_retrieval_calls"],
        "source_commit": result["source_commit"], "independent": False,
        "oracle_is_achieved": False,
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
