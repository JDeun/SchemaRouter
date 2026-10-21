"""E0: paired full/native G5 graph update vs SQLite WAL mutation-journal update.

Real SQLite on one GitHub Ubuntu runner, but all source schemas synthetic.
Not production request latency, independently owned provider data or E2.
"""
from __future__ import annotations

import argparse
import json
import math
import platform
import resource
import statistics
import tempfile
import time
from pathlib import Path
from typing import Any

from schemarouter import (
    AuthorizationPolicy,
    AuthorizationRule,
    SchemaRouter,
    SQLiteRegistry,
)
from schemarouter.native_graph_index import NativeSchemaGraphIndex
from schemarouter.native_semantic_index import NativeSchemaPostingIndex
from scripts.benchmark_indexed_native_graph_g5_cpu_e0 import (
    GROUP,
    PRINCIPAL,
    QUERY,
    _synthetic_router,
)

EVIDENCE = "E0_SYNTHETIC_SQLITE_G5_GRAPH_JOURNAL_CPU_NOT_E2"


def _percentile(values: list[float], percent: int) -> float:
    ordered = sorted(values)
    position = max(0, math.ceil(len(ordered) * percent / 100) - 1)
    return round(ordered[position], 4)


def _summary(values: list[float]) -> dict[str, float]:
    return {
        "p50": _percentile(values, 50),
        "p95": _percentile(values, 95),
        "p99": _percentile(values, 99),
        "mean": round(statistics.fmean(values), 4),
    }


def benchmark(*, registered_routes: int = 502, pairs: int = 4) -> dict[str, Any]:
    if (
        type(registered_routes) is not int
        or not 2 <= registered_routes <= 5102
        or type(pairs) is not int
        or not 2 <= pairs <= 10
    ):
        raise ValueError("bounded synthetic SQLite G5 CPU trial only")
    original = _synthetic_router(registered_routes - 2)
    wall: dict[str, list[float]] = {"full": [], "journal": []}
    cpu: dict[str, list[float]] = {"full": [], "journal": []}
    parity = compatible = incompatible = 0
    with tempfile.TemporaryDirectory(prefix="schemarouter-sqlite-g5-e0-") as tmp:
        with SQLiteRegistry(Path(tmp) / "native-source.sqlite3") as source:
            source.update_many(original.registry.tools())
            router = SchemaRouter(
                registry=source,
                authorization_policy=AuthorizationPolicy(
                    default_effect="deny",
                    rules=(AuthorizationRule(
                        effect="allow", operation="*.read", roles_any=("reader",),
                    ),),
                ),
            )
            previous = NativeSchemaGraphIndex.build(
                NativeSchemaPostingIndex.build(source)
            )
            if previous.field_index.indexed_route_count != registered_routes:
                raise RuntimeError("unexpected source catalog size")
            for iteration in range(pairs):
                # Real native source contract edit: alternate one incompatible
                # scalar consumer join and one compatible scalar join.
                tool = source.get("case_service")
                endpoint = tool.endpoint("read")
                kind = "integer" if iteration % 2 == 0 else "string"
                endpoint.parameters[0].json_schema = {"type": kind}
                endpoint.input_schema = {
                    "type": "object",
                    "properties": {"customer_id": {"type": kind}},
                    "required": ["customer_id"],
                }
                source.register(tool, replace=True)
                version = source.version
                results: dict[str, NativeSchemaGraphIndex] = {}
                order = ("full", "journal") if iteration % 2 == 0 else (
                    "journal", "full"
                )
                for arm in order:
                    wall_start = time.perf_counter_ns()
                    cpu_start = time.process_time_ns()
                    result = (
                        NativeSchemaGraphIndex.build(
                            NativeSchemaPostingIndex.build(source)
                        )
                        if arm == "full"
                        else NativeSchemaGraphIndex.refresh_from_sqlite_journal(
                            previous, source,
                        )
                    )
                    wall[arm].append(
                        (time.perf_counter_ns() - wall_start) / 1_000_000
                    )
                    cpu[arm].append(
                        (time.process_time_ns() - cpu_start) / 1_000_000
                    )
                    if source.version != version:
                        raise RuntimeError("cross-arm SQLite source changed")
                    results[arm] = result
                fresh = results["full"]
                updated = results["journal"]
                full_query = fresh.lookup(
                    router, QUERY, group=GROUP, principal=PRINCIPAL,
                )
                delta_query = updated.lookup(
                    router, QUERY, group=GROUP, principal=PRINCIPAL,
                )
                if not (
                    fresh.field_index.snapshot_id
                    == updated.field_index.snapshot_id
                    and fresh.field_index.registry_version == version
                    and updated.field_index.registry_version == version
                    and fresh.field_index.indexed_route_count == registered_routes
                    and dict(fresh.field_index.route_fingerprints)
                    == dict(updated.field_index.route_fingerprints)
                    and dict(fresh.field_index.tool_fingerprints)
                    == dict(updated.field_index.tool_fingerprints)
                    and dict(fresh.field_index.postings)
                    == dict(updated.field_index.postings)
                    and dict(fresh.field_index.route_locations)
                    == dict(updated.field_index.route_locations)
                    and fresh.graph.capability_ids == updated.graph.capability_ids
                    and fresh.graph.edges == updated.graph.edges
                    and fresh.native_root_count == updated.native_root_count
                    and fresh.native_consumer_count == updated.native_consumer_count
                    and fresh.edge_consumer_routes == updated.edge_consumer_routes
                    and full_query == delta_query
                ):
                    raise RuntimeError("SQLite G5 journal graph differs from full oracle")
                expected = 0 if kind == "integer" else 1
                if full_query.qualified_path_count != expected:
                    raise RuntimeError("typed no-fit or supported path changed")
                compatible += int(expected == 1)
                incompatible += int(expected == 0)
                parity += 1
                previous = updated
    return {
        "evidence_tier": EVIDENCE,
        "provider_independent_e2_qualified": False,
        "production_sla_qualified": False,
        "source": "developer_synthetic_native_ToolSpec_real_SQLite_WAL",
        "timed_scope": "posting_plus_canonical_graph_update_only",
        "registered_native_routes": registered_routes,
        "pairs": pairs,
        "full_oracle_equal_pairs": parity,
        "supported_typed_pairs": compatible,
        "incompatible_typed_pairs": incompatible,
        "alternated_execution_order": True,
        "wall_ms": {k: _summary(v) for k, v in wall.items()},
        "process_cpu_ms": {k: _summary(v) for k, v in cpu.items()},
        "journal_faster_pairs": sum(
            a < b for a, b in zip(wall["journal"], wall["full"], strict=True)
        ),
        "peak_process_rss_kib": int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss),
        "python_version": platform.python_version(),
        "limitations": [
            "Original publisher/agent E2 not sampled; all ToolSpecs synthetic.",
            "Source seed setup, network, execution and query latency are excluded.",
            "Index/graph immutable copies remain O(catalog); samples are sparse.",
            "SQLite file must have only audited registry API writers.",
            "No production tail-latency, SLA, concurrent benchmark or release claim.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registered-routes", type=int, default=502)
    parser.add_argument("--pairs", type=int, default=4)
    options = parser.parse_args()
    print(json.dumps(
        benchmark(registered_routes=options.registered_routes, pairs=options.pairs),
        ensure_ascii=False, sort_keys=True,
    ))


if __name__ == "__main__":
    main()
