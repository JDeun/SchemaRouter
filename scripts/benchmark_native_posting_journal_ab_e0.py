"""Paired fresh-build vs source-journal posting refresh on SYNTHETIC CPU.

This measures ONLY native semantic posting update (no graph rebuild, agent,
network, commercial p95 or independently attested provider task success).
"""
from __future__ import annotations

import argparse
import json
import math
import platform
import resource
import statistics
import time
from typing import Any

from schemarouter.native_semantic_index import NativeSchemaPostingIndex
from scripts.benchmark_indexed_native_graph_g5_cpu_e0 import _synthetic_router

EVIDENCE = "E0_SYNTHETIC_NATIVE_POSTING_REFRESH_ONLY_NOT_E2"


def _quantile_ms(samples: list[float], pct: float) -> float:
    ordered = sorted(samples)
    rank = math.ceil(len(ordered) * pct / 100) - 1
    return round(ordered[max(0, rank)], 4)


def _summary(samples: list[float]) -> dict[str, float]:
    return {
        "p50": _quantile_ms(samples, 50),
        "p95": _quantile_ms(samples, 95),
        "p99": _quantile_ms(samples, 99),
        "mean": round(statistics.fmean(samples), 4),
    }


def benchmark(*, registered_routes: int = 502, pairs: int = 4) -> dict[str, Any]:
    if (
        type(registered_routes) is not int
        or not 2 <= registered_routes <= 5102
        or type(pairs) is not int
        or not 2 <= pairs <= 12
    ):
        raise ValueError("bounded source-native synthetic posting benchmark required")
    # Fixed two real typed root/consumer schema routes; the rest is
    # author-created unrelated noise. No original provider queries.
    router = _synthetic_router(registered_routes - 2)
    registry = router.registry
    previous = NativeSchemaPostingIndex.build(registry)
    if previous.indexed_route_count != registered_routes:
        raise RuntimeError("initial catalog size changed")
    full_ms: list[float] = []
    journal_ms: list[float] = []
    full_cpu_ms: list[float] = []
    journal_cpu_ms: list[float] = []
    identical = 0
    for iteration in range(pairs):
        # A metadata-only source version mutation still changes exact
        # native tool fingerprints. Keep query semantics and candidate
        # cardinality constant in every paired run.
        name = "contact_directory"
        changed = registry.get(name)
        changed.description = f"native-posting-refresh-e0-{iteration}"
        registry.register(changed, replace=True)
        version = registry.version
        results: dict[str, NativeSchemaPostingIndex] = {}
        variants = (
            ("full_rebuild", "journal_refresh") if iteration % 2 == 0
            else ("journal_refresh", "full_rebuild")
        )
        for variant in variants:
            cpu0 = time.process_time_ns()
            wall0 = time.perf_counter_ns()
            result = (
                NativeSchemaPostingIndex.build(registry)
                if variant == "full_rebuild"
                else NativeSchemaPostingIndex.refresh_from_inmemory_journal(
                    previous, registry,
                )
            )
            elapsed = (time.perf_counter_ns() - wall0) / 1_000_000
            cpu_elapsed = (time.process_time_ns() - cpu0) / 1_000_000
            if registry.version != version:
                raise RuntimeError("source changed during paired benchmark")
            if variant == "full_rebuild":
                full_ms.append(elapsed)
                full_cpu_ms.append(cpu_elapsed)
            else:
                journal_ms.append(elapsed)
                journal_cpu_ms.append(cpu_elapsed)
            results[variant] = result
        rebuilt = results["full_rebuild"]
        journal = results["journal_refresh"]
        if (
            rebuilt.snapshot_id != journal.snapshot_id
            or dict(rebuilt.postings) != dict(journal.postings)
            or dict(rebuilt.route_fingerprints) != dict(journal.route_fingerprints)
            or dict(rebuilt.tool_fingerprints) != dict(journal.tool_fingerprints)
            or dict(rebuilt.route_locations) != dict(journal.route_locations)
            or rebuilt.indexed_route_count != journal.indexed_route_count
        ):
            raise RuntimeError("journal update disagrees with full native rebuild")
        identical += 1
        previous = journal
    usage = resource.getrusage(resource.RUSAGE_SELF)
    return {
        "evidence_tier": EVIDENCE,
        "independent_e2_qualified": False,
        "production_p95_qualified": False,
        "graph_delta_included": False,
        "source": "developer_synthetic_inmemory_no_provider_calls",
        "registered_source_routes": registered_routes,
        "paired_samples": pairs,
        "alternated_execution_order": True,
        "exact_full_build_index_oracle_pairs": identical,
        "wall_ms": {
            "full_rebuild": _summary(full_ms),
            "journal_refresh": _summary(journal_ms),
        },
        "process_cpu_ms": {
            "full_rebuild": _summary(full_cpu_ms),
            "journal_refresh": _summary(journal_cpu_ms),
        },
        "delta_faster_pairs": sum(
            fast < slow for fast, slow in zip(journal_ms, full_ms, strict=True)
        ),
        "peak_process_rss_kib": int(usage.ru_maxrss),
        "python_version": platform.python_version(),
        "limitations": [
            "Snapshot map copying/deterministic SHA-256 receipt remains O(catalog).",
            "Journal fast path is only the exact built-in InMemoryRegistry.",
            "Does not time graph-edge delta, authorization, model, E2, SQLite or I/O.",
            "P95/p99 from limited synthetic samples are descriptive, not an SLA.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registered-routes", type=int, default=502)
    parser.add_argument("--pairs", type=int, default=4)
    args = parser.parse_args()
    print(json.dumps(
        benchmark(registered_routes=args.registered_routes, pairs=args.pairs),
        ensure_ascii=False, sort_keys=True,
    ))


if __name__ == "__main__":
    main()
