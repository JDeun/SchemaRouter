"""Profile the retrieval hot path against the pre-#691 exhaustive snapshot path.

This benchmark is intentionally narrow: it uses the frozen Gearlynx E1 fixture and compares
identical public retrieval results while toggling the versioned candidate index. It is a
microbenchmark for routing overhead, not an end-to-end agent benchmark.
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
from pathlib import Path
from typing import Any

from external_validation_gearlynx import CASES, build_router, load_catalog


def _percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(len(ordered) * fraction))
    return ordered[index]


def _run_condition(
    *,
    candidate_index: bool,
    iterations: int,
) -> dict[str, Any]:
    fixture = load_catalog()
    router = build_router(fixture["tools"])
    router.planner.candidate_index = candidate_index

    # Warm model/schema caches. The indexed path also builds its immutable version snapshot here.
    for query, _ in CASES:
        router.retrieve(query, k=3)

    samples: list[float] = []
    per_query: list[dict[str, Any]] = []
    for query, _ in CASES:
        query_samples: list[float] = []
        for _ in range(iterations):
            started = time.perf_counter_ns()
            router.retrieve(query, k=3)
            elapsed_ms = (time.perf_counter_ns() - started) / 1_000_000
            samples.append(elapsed_ms)
            query_samples.append(elapsed_ms)
        per_query.append(
            {
                "query": query,
                "median_ms": statistics.median(query_samples),
                "p95_ms": _percentile(query_samples, 0.95),
            }
        )

    return {
        "candidate_index": candidate_index,
        "sample_count": len(samples),
        "median_ms": statistics.median(samples),
        "p95_ms": _percentile(samples, 0.95),
        "mean_ms": statistics.mean(samples),
        "per_query": per_query,
    }


def evaluate(iterations: int = 50) -> dict[str, Any]:
    if iterations < 1:
        raise ValueError("iterations must be >= 1")

    fixture = load_catalog()
    indexed = build_router(fixture["tools"])
    exhaustive = build_router(fixture["tools"])
    exhaustive.planner.candidate_index = False

    mismatches: list[str] = []
    for query, _ in CASES:
        indexed_result = indexed.retrieve(query, k=3).model_dump(mode="json")
        exhaustive_result = exhaustive.retrieve(query, k=3).model_dump(mode="json")
        if indexed_result != exhaustive_result:
            mismatches.append(query)

    if mismatches:
        raise AssertionError(
            "indexed retrieval changed public retrieval semantics for: "
            + ", ".join(mismatches)
        )

    optimized = _run_condition(candidate_index=True, iterations=iterations)
    legacy = _run_condition(candidate_index=False, iterations=iterations)
    speedup = (
        legacy["median_ms"] / optimized["median_ms"]
        if optimized["median_ms"] > 0
        else None
    )
    return {
        "schema_version": 1,
        "benchmark": "retrieval-hot-path-gearlynx-e1",
        "fixture_tool_count": len(fixture["tools"]),
        "case_count": len(CASES),
        "iterations_per_case": iterations,
        "semantic_mismatches": mismatches,
        "optimized": optimized,
        "legacy_exhaustive_snapshot_copy": legacy,
        "median_speedup": speedup,
        "note": (
            "candidate_index=False reproduces the pre-#691 retrieval path that deep-copies "
            "the full registry snapshot on every retrieval. Results are host-local timing "
            "evidence and must not be compared across machines as absolute latency."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--iterations", type=int, default=50)
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()

    result = evaluate(args.iterations)
    rendered = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)
    print(rendered)
    if args.json_out is not None:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(rendered + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
