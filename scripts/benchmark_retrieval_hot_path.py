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
    lightweight: bool,
    iterations: int,
) -> dict[str, Any]:
    fixture = load_catalog()
    router = build_router(fixture["tools"])
    router.planner.candidate_index = candidate_index

    # Warm model/schema caches. The indexed path also builds its immutable version snapshot here.
    for query, _ in CASES:
        if lightweight:
            router.retrieve_routes(query, k=3)
        else:
            router.retrieve(query, k=3)

    samples: list[float] = []
    per_query: list[dict[str, Any]] = []
    for query, _ in CASES:
        query_samples: list[float] = []
        for _ in range(iterations):
            started = time.perf_counter_ns()
            if lightweight:
                router.retrieve_routes(query, k=3)
            else:
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
        "lightweight": lightweight,
        "sample_count": len(samples),
        "median_ms": statistics.median(samples),
        "p95_ms": _percentile(samples, 0.95),
        "mean_ms": statistics.mean(samples),
        "per_query": per_query,
    }


def _measure_fingerprint_overhead(iterations: int) -> dict[str, float]:
    fixture = load_catalog()
    router = build_router(fixture["tools"])
    pairs = router.planner._index().all_endpoint_pairs()
    availability = router.planner.availability_predicate
    if availability is None:
        raise AssertionError("Gearlynx router must expose the normal availability predicate")

    fingerprint_samples: list[float] = []
    availability_samples: list[float] = []
    cached_availability_samples: list[float] = []
    fingerprints = {tool.key: tool.fingerprint for tool, _ in pairs}

    for _ in range(iterations):
        started = time.perf_counter_ns()
        for tool, _ in pairs:
            _ = tool.fingerprint
        fingerprint_samples.append((time.perf_counter_ns() - started) / 1_000_000)

        started = time.perf_counter_ns()
        for tool, endpoint in pairs:
            availability(tool, endpoint)
        availability_samples.append((time.perf_counter_ns() - started) / 1_000_000)

        started = time.perf_counter_ns()
        for tool, endpoint in pairs:
            router.executor.is_access_available_for_contract(
                tool.key,
                endpoint.name,
                fingerprints[tool.key],
            )
        cached_availability_samples.append(
            (time.perf_counter_ns() - started) / 1_000_000
        )

    return {
        "endpoint_count": float(len(pairs)),
        "fingerprint_batch_median_ms": statistics.median(fingerprint_samples),
        "availability_batch_median_ms": statistics.median(availability_samples),
        "cached_availability_batch_median_ms": statistics.median(
            cached_availability_samples
        ),
    }


def evaluate(iterations: int = 50) -> dict[str, Any]:
    if iterations < 1:
        raise ValueError("iterations must be >= 1")

    fixture = load_catalog()
    indexed = build_router(fixture["tools"])
    exhaustive = build_router(fixture["tools"])
    exhaustive.planner.candidate_index = False

    mismatches: list[str] = []
    lightweight_mismatches: list[str] = []
    for query, _ in CASES:
        indexed_result = indexed.retrieve(query, k=3)
        exhaustive_result = exhaustive.retrieve(query, k=3)
        if indexed_result.model_dump(mode="json") != exhaustive_result.model_dump(mode="json"):
            mismatches.append(query)

        route_result = indexed.retrieve_routes(query, k=3)
        route_signature = [
            (
                item.route_id,
                item.score,
                tuple(item.matched_fields),
                tuple(
                    (component.kind, component.value, component.matched)
                    for component in item.score_components
                ),
                item.selection_source,
            )
            for item in route_result.candidates
        ]
        full_signature = [
            (
                item.route_id,
                item.score,
                tuple(item.matched_fields),
                tuple(
                    (component.kind, component.value, component.matched)
                    for component in item.score_components
                ),
                item.selection_source,
            )
            for item in indexed_result.candidates
        ]
        if route_signature != full_signature:
            lightweight_mismatches.append(query)

    if mismatches:
        raise AssertionError(
            "indexed retrieval changed public retrieval semantics for: "
            + ", ".join(mismatches)
        )
    if lightweight_mismatches:
        raise AssertionError(
            "lightweight retrieval changed ranking/evidence semantics for: "
            + ", ".join(lightweight_mismatches)
        )

    optimized_typed = _run_condition(
        candidate_index=True,
        lightweight=False,
        iterations=iterations,
    )
    optimized_routes = _run_condition(
        candidate_index=True,
        lightweight=True,
        iterations=iterations,
    )
    legacy_typed = _run_condition(
        candidate_index=False,
        lightweight=False,
        iterations=iterations,
    )
    legacy_routes = _run_condition(
        candidate_index=False,
        lightweight=True,
        iterations=iterations,
    )
    return {
        "schema_version": 2,
        "benchmark": "retrieval-hot-path-gearlynx-e1",
        "fixture_tool_count": len(fixture["tools"]),
        "case_count": len(CASES),
        "iterations_per_case": iterations,
        "semantic_mismatches": mismatches,
        "lightweight_semantic_mismatches": lightweight_mismatches,
        "fingerprint_overhead": _measure_fingerprint_overhead(iterations),
        "optimized_typed": optimized_typed,
        "optimized_route_refs": optimized_routes,
        "legacy_typed_snapshot_copy": legacy_typed,
        "legacy_route_refs_snapshot_copy": legacy_routes,
        "typed_median_speedup": (
            legacy_typed["median_ms"] / optimized_typed["median_ms"]
        ),
        "route_ref_vs_legacy_typed_median_speedup": (
            legacy_typed["median_ms"] / optimized_routes["median_ms"]
        ),
        "route_ref_vs_optimized_typed_median_speedup": (
            optimized_typed["median_ms"] / optimized_routes["median_ms"]
        ),
        "note": (
            "candidate_index=False reproduces the pre-#691 per-request registry snapshot "
            "copy. retrieve_routes() measures candidate selection without typed schema "
            "materialization. Timings are host-local and absolute values must not be "
            "compared across machines."
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
