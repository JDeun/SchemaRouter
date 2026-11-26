"""Paired native G5 posting + canonical typed graph refresh vs full build.

Developer-synthetic actual SQLite WAL source on one GitHub Actions CPU.
Not a commercial, original publisher, external agent or E2 test.
"""
from __future__ import annotations

import argparse
import json
import math
import platform
import resource
import statistics
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from schemarouter import SchemaRouter, SQLiteRegistry
from schemarouter.native_graph_index import NativeSchemaGraphIndex
from schemarouter.native_semantic_index import NativeSchemaPostingIndex
from scripts.benchmark_indexed_native_graph_g5_cpu_e0 import (
    GROUP,
    PRINCIPAL,
    QUERY,
    _synthetic_router,
)

EVIDENCE = "E0_SYNTHETIC_SQLITE_PAIRED_NATIVE_G5_NOT_E2"


def _summary(samples: list[float]) -> dict[str, float]:
    ordered = sorted(samples)
    def pct(percent: int) -> float:
        return round(ordered[max(0, math.ceil(len(ordered) * percent / 100) - 1)], 4)
    return {
        "p50": pct(50),
        "p95": pct(95),
        "p99": pct(99),
        "mean": round(statistics.fmean(samples), 4),
    }


def _measure_open_sqlite_catalog(
    router: SchemaRouter,
    registry: SQLiteRegistry,
    *,
    registered_routes: int,
    pairs: int,
) -> dict[str, Any]:
    current = NativeSchemaGraphIndex.build(NativeSchemaPostingIndex.build(registry))
    if current.field_index.indexed_route_count != registered_routes:
        raise RuntimeError("synthetic registered native catalog size mismatch")
    full_wall: list[float] = []
    journal_wall: list[float] = []
    full_cpu: list[float] = []
    journal_cpu: list[float] = []
    matches = 0
    supported = unsupported = 0
    for i in range(pairs):
        # Alternating genuine typed input compatibility, not descriptive
        # metadata-only changes: odd iterations restore valid string joins.
        consumer = registry.get("case_service")
        endpoint = consumer.endpoint("read")
        kind = "integer" if i % 2 == 0 else "string"
        endpoint.parameters[0].json_schema = {"type": kind}
        endpoint.input_schema = {
            "type": "object",
            "properties": {"customer_id": {"type": kind}},
            "required": ["customer_id"],
        }
        registry.register(consumer, replace=True)
        version = registry.version
        arms = (
            ("full", "journal") if i % 2 == 0
            else ("journal", "full")
        )
        results: dict[str, NativeSchemaGraphIndex] = {}
        for arm in arms:
            wall0 = time.perf_counter_ns()
            cpu0 = time.process_time_ns()
            result = (
                NativeSchemaGraphIndex.build(
                    NativeSchemaPostingIndex.build(registry)
                )
                if arm == "full"
                else NativeSchemaGraphIndex.refresh_from_sqlite_journal(
                    current, registry,
                )
            )
            wall_ms = (time.perf_counter_ns() - wall0) / 1_000_000
            cpu_ms = (time.process_time_ns() - cpu0) / 1_000_000
            if arm == "full":
                full_wall.append(wall_ms)
                full_cpu.append(cpu_ms)
            else:
                journal_wall.append(wall_ms)
                journal_cpu.append(cpu_ms)
            results[arm] = result
            if registry.version != version:
                raise RuntimeError("G5 source version changed within matched pair")
        fresh = results["full"]
        delta = results["journal"]
        fresh_query = fresh.lookup(
            router, QUERY, group=GROUP, principal=PRINCIPAL,
        )
        delta_query = delta.lookup(
            router, QUERY, group=GROUP, principal=PRINCIPAL,
        )
        if not (
            fresh.field_index.snapshot_id == delta.field_index.snapshot_id
            and fresh.field_index.indexed_route_count == registered_routes
            and dict(fresh.field_index.postings) == dict(delta.field_index.postings)
            and dict(fresh.field_index.route_fingerprints)
            == dict(delta.field_index.route_fingerprints)
            and fresh.graph.capability_ids == delta.graph.capability_ids
            and fresh.graph.edges == delta.graph.edges
            and fresh.native_root_count == delta.native_root_count
            and fresh.native_consumer_count == delta.native_consumer_count
            and fresh.edge_consumer_routes == delta.edge_consumer_routes
            and fresh_query == delta_query
        ):
            raise RuntimeError("G5 journal graph disagrees with full source oracle")
        if kind == "string":
            if fresh_query.qualified_path_count != 1:
                raise RuntimeError("G5 supported typed pair lost")
            supported += 1
        else:
            if fresh_query.qualified_path_count != 0:
                raise RuntimeError("G5 type-incompatible pair spuriously accepted")
            unsupported += 1
        matches += 1
        current = delta
    return {
        "evidence_tier": EVIDENCE,
        "independent_e2_qualified": False,
        "production_p95_qualified": False,
        "no_real_provider_calls": True,
        "measures": "durable_sqlite_posting_plus_canonical_onehop_graph_update_only",
        "source": "builtin_sqlite_registry_wal_synthetic_uncontended_local_file",
        "registry_revision": registry.version,
        "registered_source_routes": registered_routes,
        "paired_samples": pairs,
        "exact_source_native_full_graph_oracle_pairs": matches,
        "supported_typed_pairs": supported,
        "incompatible_typed_pairs": unsupported,
        "alternated_execution_order": True,
        "wall_ms": {
            "full_build": _summary(full_wall),
            "journal_refresh": _summary(journal_wall),
        },
        "process_cpu_ms": {
            "full_build": _summary(full_cpu),
            "journal_refresh": _summary(journal_cpu),
        },
        "journal_faster_pairs": sum(
            delta < full for delta, full in zip(journal_wall, full_wall, strict=True)
        ),
        "peak_process_rss_kib": int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss),
        "python_version": platform.python_version(),
        "limitations": [
            "Single-host synthetic provider-free CRM source; no model or agent E2.",
            "Only full G5 graph index building/updating, not request p95 or execution.",
            "Small paired samples are not statistically reliable tail latencies.",
            "Index map and immutable graph contract copying remain O(catalog).",
            "Exact SQLiteRegistry API-only writer, local WAL; no hostile table writers.",
            "SQLite file generation/seed and mutations are excluded from paired timers.",
            "No live concurrent writer stress, external/provider gold or Qwen E2.",
        ],
    }


def benchmark(*, registered_routes: int = 502, pairs: int = 4) -> dict[str, Any]:
    if (
        type(registered_routes) is not int
        or not 2 <= registered_routes <= 5102
        or type(pairs) is not int
        or not 2 <= pairs <= 10
    ):
        raise ValueError("bounded SQLite native G5 graph CPU E0 trial only")
    seed = _synthetic_router(registered_routes - 2)
    with TemporaryDirectory(prefix="schemarouter-sqlite-g5-e0-") as temporary:
        with SQLiteRegistry(Path(temporary) / "source.sqlite3") as registry:
            # All 500 or 5000 source registrations are one ordinary SQLite
            # batch; this may contain a NULL historical journal barrier.
            # Our next per-pair changed-key receipt starts AFTER that version.
            registry.update_many(seed.registry.tools())
            router = SchemaRouter(
                registry=registry,
                authorization_policy=seed.authorization_policy,
            )
            return _measure_open_sqlite_catalog(
                router, registry,
                registered_routes=registered_routes, pairs=pairs,
            )


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
