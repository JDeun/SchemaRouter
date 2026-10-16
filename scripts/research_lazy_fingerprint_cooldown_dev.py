"""Exact original eager vs lazy cooldown-fingerprint public API CPU study.

Synthetic same-author DEV only. No provider invocations or model inference.
Every full authorized result must be byte-equivalent before timing is reported.
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
    "src/schemarouter/executor.py",
    "src/schemarouter/planner.py",
    "src/schemarouter/models.py",
    "benchmarks/current_adapter_scaled_authorized_dev_v1.py",
    "scripts/research_lazy_fingerprint_cooldown_dev.py",
    "tests/test_lazy_fingerprint_cooldown_guard.py",
)


def p95(values: list[float]) -> float:
    if not values or any(not math.isfinite(value) or value < 0
                         for value in values):
        raise ValueError("non-finite or missing measured CPU durations")
    return round(sorted(values)[math.ceil(len(values) * .95) - 1], 5)


def evaluate(sizes: tuple[int, ...] = SIZES) -> dict[str, Any]:
    if (
        type(sizes) is not tuple or not sizes
        or len(set(sizes)) != len(sizes)
        or any(type(size) is not int or size not in SIZES for size in sizes)
    ):
        raise ValueError("unregistered lazy cooldown benchmark dimensions")
    tasks = authored_tasks()
    if len(tasks) != 27 or len({t["id"] for t in tasks}) != 27:
        raise ValueError("synthetic task definition drift")
    rows: list[dict[str, Any]] = []
    for size in sizes:
        router, policy = build_fixture(size)
        for case in tasks:
            who = principal(case["role"])
            for k in WIDTHS:
                query = PlanRequest(query=case["query"])
                def original_callback(tool: Any, endpoint: Any) -> bool:
                    return router.executor.is_access_available_for_contract(
                        tool.key, endpoint.name,
                        router.planner._snapshot_tool_fingerprint(tool),
                    )

                with patch.object(
                    router.planner, "availability_predicate",
                    original_callback,
                ):
                    start = time.perf_counter_ns()
                    baseline = router.retrieve_authorized(
                        query, principal=who, k=k,
                    )
                    old_ms = (time.perf_counter_ns() - start) / 1_000_000
                start = time.perf_counter_ns()
                current = router.retrieve_authorized(
                    query, principal=who, k=k,
                )
                new_ms = (time.perf_counter_ns() - start) / 1_000_000
                old = baseline.model_dump(mode="json")
                new = current.model_dump(mode="json")
                if old != new:
                    raise ValueError(
                        "FAIL CLOSED: eager vs lazy cooldown route, "
                        "field, fingerprint, score or rank mismatch"
                    )
                allowed = {
                    f"{tool.key}.{endpoint.name}"
                    for tool in router.registry.tools()
                    for endpoint in tool.endpoints
                    if policy.visible(who, tool, endpoint)
                }
                if set(x.route_id for x in current.candidates) - allowed:
                    raise ValueError("lazy cooldown expanded principal authority")
                if (
                    not math.isfinite(old_ms) or old_ms <= 0
                    or not math.isfinite(new_ms) or new_ms <= 0
                    or current.requested_k != k
                ):
                    raise ValueError("incomplete current authorized CPU sample")
                gold = case["gold_route"]
                rows.append({
                    "size": size,
                    "case_id": case["id"],
                    "language": case["language"],
                    "role": case["role"],
                    "k": k,
                    "old_eager_ms": round(old_ms, 5),
                    "new_lazy_ms": round(new_ms, 5),
                    "full_result_sha256": hashlib.sha256(encoded(old)).hexdigest(),
                    "exact_entire_response": True,
                    "unauthorized_candidates": 0,
                    "gold_top5": bool(
                        gold is not None
                        and gold in [x.route_id for x in current.candidates[:5]]
                    ),
                })
    expected = len(sizes) * len(WIDTHS) * len(tasks)
    if len(rows) != expected:
        raise ValueError("partial source-paired 100/250/500 experiment")
    groups = {}
    for size in sizes:
        for k in WIDTHS:
            cohort = [x for x in rows if x["size"] == size and x["k"] == k]
            old = p95([x["old_eager_ms"] for x in cohort])
            new = p95([x["new_lazy_ms"] for x in cohort])
            groups[f"{size}/K{k}"] = {
                "pairs": len(cohort),
                "original_p95_ms": old,
                "lazy_p95_ms": new,
                "relative_reduction": round((old - new) / old, 6),
                "exact_parity_count": sum(
                    x["exact_entire_response"] for x in cohort
                ),
                "unauthorized_count": sum(
                    x["unauthorized_candidates"] for x in cohort
                ),
                "supported_route_hits": sum(x["gold_top5"] for x in cohort),
            }
    sources = {
        path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
        for path in SOURCES
    }
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT,
        check=True, timeout=10, text=True, capture_output=True,
    ).stdout.strip()
    return {
        "schema_version": 1,
        "experiment": "author_visible_scoped_lazy_fingerprint_cooldown_dev",
        "source_commit": commit,
        "source_file_sha256": sources,
        "source_sha256": hashlib.sha256(encoded(sources)).hexdigest(),
        "sizes": list(sizes),
        "widths": list(WIDTHS),
        "expected_pairs": expected,
        "actual_pairs": len(rows),
        "groups": groups,
        "cases": rows,
        "peak_resident_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "hardware": {
            "os": platform.platform(), "python": platform.python_version(),
            "cpu_count": os.cpu_count(),
            "actions_run_id": os.environ.get("GITHUB_RUN_ID"),
        },
        "scope": {
            "synthetic_dev_only": True,
            "host_principal_authenticated": False,
            "cooldown_semantics_still_require_tests": True,
            "independent_confirmation": False,
            "agent_or_external_tool_executed": False,
            "automatic_product_promotion": False,
            "may_release": False,
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
        json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "status": result["experiment"],
        "verified_pairs": result["actual_pairs"],
        "may_release": False,
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
