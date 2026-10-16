"""Experimental exact scoped-index parity and CPU DEV, never release authority."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import resource
import subprocess
import time
from pathlib import Path
from typing import Any

from benchmarks.current_adapter_field_scope_dev_v1 import principal
from benchmarks.current_adapter_scaled_authorized_dev_v1 import (
    SIZES,
    WIDTHS,
    authored_tasks,
    build_fixture,
)
from schemarouter import PlanRequest
from scripts.research_current_main_multilingual_dev import encoded

ROOT = Path(__file__).resolve().parents[1]
SOURCES = (
    "src/schemarouter/planner.py",
    "src/schemarouter/runtime.py",
    "src/schemarouter/authorization.py",
    "benchmarks/current_adapter_scaled_authorized_dev_v1.py",
    "scripts/research_scoped_candidate_exact_index_dev.py",
    "tests/test_scoped_candidate_exact_index.py",
)
MAX_PAIRS = len(SIZES) * len(WIDTHS) * 27


def percentile(values: list[float]) -> float:
    if not values or any(not math.isfinite(x) or x < 0 for x in values):
        raise ValueError("unmeasured or nonfinite parity CPU durations")
    return round(sorted(values)[math.ceil(len(values) * 0.95) - 1], 5)


def evaluate(sizes: tuple[int, ...] = SIZES) -> dict[str, Any]:
    if (
        type(sizes) is not tuple or not sizes
        or len(sizes) != len(set(sizes))
        or any(type(x) is not int or x not in SIZES for x in sizes)
    ):
        raise ValueError("unregistered scoped-index DEV catalog dimensions")
    tasks = authored_tasks()
    if len(tasks) != 27 or len({row["id"] for row in tasks}) != 27:
        raise ValueError("unregistered synthetic DEV labels")
    rows: list[dict[str, Any]] = []
    for size in sizes:
        router, policy = build_fixture(size)
        for task in tasks:
            who = principal(task["role"])
            for width in (24, 56):
                query = PlanRequest(query=task["query"])
                try:
                    router.planner.candidate_index = False
                    started = time.perf_counter_ns()
                    baseline = router.retrieve_authorized(
                        query, principal=who, k=width,
                    )
                    before = (time.perf_counter_ns() - started) / 1_000_000
                    router.planner.candidate_index = True
                    started = time.perf_counter_ns()
                    indexed = router.retrieve_authorized(
                        query, principal=who, k=width,
                    )
                    after = (time.perf_counter_ns() - started) / 1_000_000
                finally:
                    router.planner.candidate_index = True
                before_raw = baseline.model_dump(mode="json")
                after_raw = indexed.model_dump(mode="json")
                if before_raw != after_raw:
                    raise ValueError(
                        "FAIL CLOSED: index changes an authorized score, "
                        "route, source fingerprint, field, or shortlist"
                    )
                if (
                    baseline.requested_k != width
                    or indexed.registry_version != router.registry.version
                    or any(not math.isfinite(x) or x < 0 for x in (before, after))
                ):
                    raise ValueError("invalid production-scoped parity receipt")
                visible = {
                    f"{tool.key}.{endpoint.name}"
                    for tool in router.registry.tools()
                    for endpoint in tool.endpoints
                    if policy.visible(who, tool, endpoint)
                }
                if not set(c.route_id for c in indexed.candidates) <= visible:
                    raise ValueError("index bypassed current route policy")
                gold = task["gold_route"]
                present = any(c.route_id == gold for c in indexed.candidates[:5])
                rows.append({
                    "size": size,
                    "case_id": task["id"],
                    "language": task["language"],
                    "role": task["role"],
                    "width": width,
                    "gold_route": gold,
                    "gold_top5_found": bool(gold is not None and present),
                    "baseline_ms": round(before, 5),
                    "indexed_ms": round(after, 5),
                    "exact_result_sha256": hashlib.sha256(
                        encoded(before_raw)
                    ).hexdigest(),
                    "identical": True,
                    "unauthorized_ids": 0,
                })
    expected = len(sizes) * len(WIDTHS) * len(tasks)
    if len(rows) != expected:
        raise ValueError("incomplete authorized paired cohort")
    summary = {
        f"{size}/K{width}": {
            "pairs": len(group),
            "baseline_p95_ms": percentile([r["baseline_ms"] for r in group]),
            "indexed_p95_ms": percentile([r["indexed_ms"] for r in group]),
            "exact_parity": all(r["identical"] for r in group),
            "route_hits": sum(r["gold_top5_found"] for r in group),
            "unauthorized_ids": sum(r["unauthorized_ids"] for r in group),
        }
        for size in sizes
        for width in WIDTHS
        if (group := [
            row for row in rows if row["size"] == size and row["width"] == width
        ])
    }
    sources = {
        path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
        for path in SOURCES
    }
    source_commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT,
        text=True, capture_output=True, check=True, timeout=10,
    ).stdout.strip()
    return {
        "schema_version": 1,
        "status": "SOURCE_BOUND_SCOPED_INDEX_EXACT_PARITY_SYNTHETIC_DEV_ONLY",
        "source_commit": source_commit,
        "source_file_sha256": sources,
        "source_sha256": hashlib.sha256(encoded(sources)).hexdigest(),
        "sizes": list(sizes),
        "widths": [24, 56],
        "paired_case_count": len(rows),
        "expected_paired_cases": expected,
        "summary": summary,
        "cases": rows,
        "peak_resident_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "hardware": {
            "os": platform.platform(),
            "cpu_count": os.cpu_count(),
            "python": platform.python_version(),
            "actions_run_id": os.environ.get("GITHUB_RUN_ID"),
        },
        "scope": {
            "synthetic_earlier_authored_dev": True,
            "independent_confirmation": False,
            "agent_task_success": False,
            "may_release": False,
            "automatic_product_promotion": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sizes", nargs="+", type=int, default=list(SIZES))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = evaluate(tuple(args.sizes))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "status": result["status"],
        "paired": result["paired_case_count"],
        "all_exact_parity": True,
        "may_release": False,
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
