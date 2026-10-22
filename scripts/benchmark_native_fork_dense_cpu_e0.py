"""Deterministic dense same-root G5 CPU E0: authorized over-K vs live health.

This is synthetic native registry data, NOT real publisher/agent E2 or SLO.
No product implementation, gold-aware selector, model or HTTP is involved.
"""
from __future__ import annotations

import argparse
import json
import platform
import resource
import time
from pathlib import Path
from statistics import fmean
from typing import Any

from schemarouter.native_graph_index import NativeSchemaGraphIndex
from schemarouter.native_semantic_index import NativeSchemaPostingIndex
from scripts.benchmark_native_fork_fieldgroup_e0 import (
    ACTOR,
    ALIASES,
    GROUP,
    _decoy_leaf,
    build_fixture,
    exhaustive_source_fork_reference,
    percentile,
)

STUDY = "G5_DENSE_SAME_ROOT_NATIVE_CPU_E0_NOT_E2"
PREFIX = "dense_fork_status_"


def benchmark_dense(
    *, registered_routes: int, extra_status: int, iterations: int = 10,
) -> dict[str, Any]:
    if type(registered_routes) is not int or registered_routes not in (500, 5000):
        raise ValueError("requires fixed 500/5000 route base")
    if type(extra_status) is not int or extra_status not in (33, 64):
        raise ValueError("requires developer E0 fanout 33 or 64")
    if type(iterations) is not int or not 10 <= iterations <= 40:
        raise ValueError("requires bounded 10..40 E0 samples")

    router = build_fixture(registered_routes)
    for i in range(extra_status):
        router.add_tool(_decoy_leaf(
            f"{PREFIX}{i}", "crm.fork_status", "status",
        ))

    # This original registry-only oracle is for developer measurement and
    # MUST NOT participate in the actual native graph product query.
    source_forks = exhaustive_source_fork_reference(router)
    if (
        len(source_forks) != extra_status + 1
        or any(root != "fork_origin.read" for root, _, _ in source_forks)
    ):
        raise AssertionError("original typed source reference drift")

    begin = time.perf_counter_ns()
    graph = NativeSchemaGraphIndex.build(
        NativeSchemaPostingIndex.build(router.registry),
    )
    index_build_ms = (time.perf_counter_ns() - begin) / 1_000_000
    if graph.field_index.indexed_route_count != registered_routes + extra_status:
        raise AssertionError("dense E0 source registration count drift")

    def assert_observed(
        *, wanted_status: str, count: int,
    ) -> None:
        for query in ALIASES:
            actual = graph.lookup_shared_root_forks(
                router, query, group=GROUP, principal=ACTOR,
            )
            if (
                actual.status != wanted_status
                or actual.qualified_fork_count != count
                or actual.requested_k != 5
                or actual.executable_authority
                or actual.independent_quality_evidence
                or (
                    actual.candidates != ()
                    if wanted_status == "over_k_unranked"
                    else len(actual.candidates) != 1
                )
            ):
                raise AssertionError("dense fork public K5/source safety drift")

    def sample(
        *, wanted_status: str, count: int,
    ) -> dict[str, Any]:
        assert_observed(wanted_status=wanted_status, count=count)
        for _ in range(3):
            assert_observed(wanted_status=wanted_status, count=count)
        walls: list[float] = []
        cpus: list[float] = []
        for _ in range(iterations):
            wall_start = time.perf_counter_ns()
            cpu_start = time.process_time_ns()
            actual = graph.lookup_shared_root_forks(
                router, ALIASES[0], group=GROUP, principal=ACTOR,
            )
            cpus.append((time.process_time_ns() - cpu_start) / 1_000_000)
            walls.append((time.perf_counter_ns() - wall_start) / 1_000_000)
            if actual.status != wanted_status or actual.qualified_fork_count != count:
                raise AssertionError("dense fork query changed in fixed source cohort")
        return {
            "status": wanted_status,
            "qualified_forks": count,
            "wall_ms": {
                "p50": percentile(walls, 50),
                "p95": percentile(walls, 95),
                "p99": percentile(walls, 99),
                "mean": round(fmean(walls), 4),
            },
            "process_cpu_ms": {
                "p50": percentile(cpus, 50),
                "p95": percentile(cpus, 95),
                "p99": percentile(cpus, 99),
            },
        }

    overflow = sample(
        wanted_status="over_k_unranked", count=extra_status + 1,
    )

    # Same native catalog and index, same principal, only currently
    # available health state changes. This cannot grant or disclose
    # partial routes and must never become a new no-fit classifier.
    router.planner.availability_predicate = (
        lambda tool, _endpoint: not tool.key.startswith(PREFIX)
    )
    restored = sample(wanted_status="complete", count=1)
    assert_observed(wanted_status="complete", count=1)

    return {
        "study": STUDY,
        "evidence_tier": "E0_SYNTHETIC_SOURCE_NATIVE_NOT_E2",
        "independent_e2_qualified": False,
        "registered_base_routes": registered_routes,
        "registered_native_routes": graph.field_index.indexed_route_count,
        "source_native_added_status_consumers": extra_status,
        "benchmark_only_original_source_fork_count": len(source_forks),
        "strict_public_k": 5,
        "all_aliases_en_ko_ja_match": True,
        "private_arms_never_exposed": True,
        "same_source_index_live_health_revocation": True,
        "sample_count": iterations,
        "warmup_count_per_condition": 3,
        "index_build_wall_ms": round(index_build_ms, 4),
        "dense_over_k": overflow,
        "revoked_to_single_fork": restored,
        "peak_process_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "model_selected_tools": False,
        "provider_native_http_calls": 0,
        "production_slo_qualified": False,
        "limitations": [
            "Developer-authored one-root flat scalar native contracts only",
            "Original source oracle is benchmark-only and restricted to fixed topology",
            "CPU/wall samples runner-specific, not production SLO or capacity guarantee",
            "Health revoke tested on same index, not a linearizable provider transaction",
            "No learned Top5 ranker, external source permission gold, agent E2, or HTTP",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registered-routes", type=int, required=True)
    parser.add_argument("--extra-status", type=int, required=True)
    parser.add_argument("--iterations", type=int, default=10)
    parser.add_argument("--out", type=Path, required=True)
    options = parser.parse_args()
    report = benchmark_dense(
        registered_routes=options.registered_routes,
        extra_status=options.extra_status,
        iterations=options.iterations,
    )
    options.out.parent.mkdir(parents=True, exist_ok=True)
    options.out.write_text(
        json.dumps(report, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "study": report["study"],
        "registered_native_routes": report["registered_native_routes"],
        "dense_over_k": report["dense_over_k"],
        "revoked_to_single_fork": report["revoked_to_single_fork"],
        "independent_e2_qualified": False,
    }, allow_nan=False))


if __name__ == "__main__":
    main()
