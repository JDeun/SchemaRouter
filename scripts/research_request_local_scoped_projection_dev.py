"""Measure source-bound request-local scoped projection reuse with exact parity.

All capability endpoints are current typed synthetic DEV from #1429. The
legacy baseline retains authorization and data-scope projection, but does
not reuse its own request-local EndpointSpec; no score or policy changes.
"""
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
from unittest.mock import patch

from benchmarks.current_adapter_field_scope_dev_v1 import principal
from benchmarks.current_adapter_scaled_authorized_dev_v1 import (
    SIZES,
    authored_tasks,
    build_fixture,
)
from schemarouter import PlanRequest
from scripts.research_current_main_multilingual_dev import encoded

ROOT = Path(__file__).resolve().parents[1]
WIDTHS = (24, 56)
SOURCES = (
    "src/schemarouter/runtime.py",
    "src/schemarouter/planner.py",
    "src/schemarouter/authorization.py",
    "benchmarks/current_adapter_scaled_authorized_dev_v1.py",
    "scripts/research_request_local_scoped_projection_dev.py",
    "tests/test_request_local_scoped_projection.py",
)


def p95(values: list[float]) -> float:
    if not values or any(not math.isfinite(x) or x < 0 for x in values):
        raise ValueError("missing valid wall-clock samples")
    return round(sorted(values)[math.ceil(len(values) * 0.95) - 1], 5)


def _without_reuse(router, who, predicate):
    registry = router._scoped_analysis_registry(who, predicate)
    return registry, lambda tool, endpoint: router._data_scope_endpoint_view(
        who, tool, endpoint,
    )


def evaluate(sizes: tuple[int, ...] = SIZES) -> dict[str, Any]:
    if (
        type(sizes) is not tuple or not sizes
        or len(set(sizes)) != len(sizes)
        or any(type(n) is not int or n not in SIZES for n in sizes)
    ):
        raise ValueError("unapproved principal projection CPU research width")
    tasks = authored_tasks()
    if len(tasks) != 27:
        raise ValueError("synthetic study labels changed")
    rows: list[dict[str, Any]] = []
    for size in sizes:
        router, policy = build_fixture(size)
        for task in tasks:
            who = principal(task["role"])
            for k in WIDTHS:
                query = PlanRequest(query=task["query"])
                with patch.object(
                    router, "_request_local_scoped_projection",
                    lambda p, pred, router=router: _without_reuse(router, p, pred),
                ):
                    start = time.perf_counter_ns()
                    old = router.retrieve_authorized(
                        query, principal=who, k=k,
                    )
                    before_ms = (time.perf_counter_ns() - start) / 1e6
                start = time.perf_counter_ns()
                new = router.retrieve_authorized(query, principal=who, k=k)
                after_ms = (time.perf_counter_ns() - start) / 1e6
                baseline_json = old.model_dump(mode="json")
                current_json = new.model_dump(mode="json")
                if baseline_json != current_json:
                    raise ValueError(
                        "FAIL CLOSED: request-local visible scope changed "
                        "the full authorized result"
                    )
                ids = {item.route_id for item in new.candidates}
                eligible = {
                    f"{tool.key}.{ep.name}"
                    for tool in router.registry.tools()
                    for ep in tool.endpoints
                    if policy.visible(who, tool, ep)
                }
                if ids - eligible:
                    raise ValueError("projected search introduced unauthorized route")
                gold = task["gold_route"]
                rows.append({
                    "size": size, "case_id": task["id"],
                    "language": task["language"], "role": task["role"],
                    "k": k, "baseline_ms": round(before_ms, 5),
                    "optimized_ms": round(after_ms, 5),
                    "entire_response_identical": True,
                    "unauthorized_candidates": 0,
                    "required_route_in_top5": bool(
                        gold is not None
                        and gold in [x.route_id for x in new.candidates[:5]]
                    ),
                    "full_output_digest": hashlib.sha256(
                        encoded(baseline_json)
                    ).hexdigest(),
                })
    expected = len(sizes) * len(tasks) * len(WIDTHS)
    if len(rows) != expected:
        raise ValueError("incomplete paired authorized DEV experiment")
    groups: dict[str, dict[str, Any]] = {}
    for size in sizes:
        for k in WIDTHS:
            group = [r for r in rows if r["size"] == size and r["k"] == k]
            groups[f"{size}/K{k}"] = {
                "pairs": len(group),
                "old_p95_ms": p95([r["baseline_ms"] for r in group]),
                "reused_p95_ms": p95([r["optimized_ms"] for r in group]),
                "exact_result_pairs": sum(
                    r["entire_response_identical"] for r in group
                ),
                "unauthorized_candidates": sum(
                    r["unauthorized_candidates"] for r in group
                ),
                "required_route_hits": sum(
                    r["required_route_in_top5"] for r in group
                ),
            }
    source_sha = {
        path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
        for path in SOURCES
    }
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, timeout=10,
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    return {
        "schema_version": 1,
        "experiment": "author_visible_scoped_projection_reuse_dev",
        "source_commit": commit,
        "source_file_sha256": source_sha,
        "source_sha256": hashlib.sha256(encoded(source_sha)).hexdigest(),
        "expected_pairs": expected,
        "actual_pairs": len(rows),
        "sizes": list(sizes),
        "widths": list(WIDTHS),
        "groups": groups,
        "cases": rows,
        "peak_resident_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "hardware": {
            "os": platform.platform(), "cpu_count": os.cpu_count(),
            "python": platform.python_version(),
            "actions_run_id": os.environ.get("GITHUB_RUN_ID"),
        },
        "scope": {
            "synthetic_dev": True,
            "independent_confirmation": False,
            "real_host_authentication": False,
            "agent_task_success": False,
            "may_release": False,
            "automatic_product_promotion": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sizes", nargs="+", type=int, default=list(SIZES))
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = evaluate(sizes=tuple(args.sizes))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, allow_nan=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "status": "LOCAL_PROJECTION_EXACT_PARITY_SYNTHETIC_DEV_ONLY",
        "paired": result["actual_pairs"],
        "may_release": False,
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
