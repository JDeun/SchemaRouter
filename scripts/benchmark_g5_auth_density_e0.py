"""Paired auth-density CPU profile on ONE native G5 index (synthetic E0).

Four principals share the exact same registered source, query, graph and
version. None may see unapproved targets, regardless of typed matches.
"""
from __future__ import annotations

import argparse
import json
import platform
import resource
import sys
import time
from math import ceil
from statistics import fmean

from schemarouter import (
    AuthorizationPolicy,
    AuthorizationRule,
    EndpointSpec,
    FieldSpec,
    ParameterSpec,
    PrincipalContext,
    ToolSpec,
)
from schemarouter.native_graph_index import NativeSchemaGraphIndex
from schemarouter.native_semantic_index import NativeSchemaPostingIndex
from scripts.benchmark_indexed_native_graph_g5_cpu_e0 import (
    EVIDENCE,
    GROUP,
    QUERY,
    _synthetic_router,
)

SCENARIOS = (("zero", 0), ("one", 1), ("five", 5), ("six", 6))
DENIED_TYPED_DISTRACTORS = 24
WARMUP = 5


def _consumer(name: str) -> ToolSpec:
    return ToolSpec(
        name=name, source_type="crm", license="host-reviewed-synthetic",
        endpoints=[EndpointSpec(
            name="read", read_only=True,
            parameters=[ParameterSpec(
                name="customer_id", required=True, location="argument",
                json_schema={"type": "string"},
                semantic_id="crm.customer_id",
            )],
            input_schema={
                "type": "object",
                "properties": {"customer_id": {"type": "string"}},
                "required": ["customer_id"],
            },
            output_fields=[FieldSpec(
                name="status", semantic_id="crm.status",
                json_schema={"type": "string"},
            )],
        )],
    )


def _build_shared_density_source(noise_routes: int):
    router = _synthetic_router(noise_routes)
    for i in range(5):
        router.add_tool(_consumer(f"eligible_{i:02d}"))
    for i in range(DENIED_TYPED_DISTRACTORS):
        router.add_tool(_consumer(f"denied_{i:02d}"))

    # No permission from source/license/semantic declarations; separate
    # explicit host-side principal+route policy is the only grant.
    rules = [
        AuthorizationRule(
            effect="allow", operation="contact_directory.read",
            roles_any=("one", "five", "six"),
        ),
        AuthorizationRule(
            effect="allow", operation="case_service.read",
            roles_any=("one", "five", "six"),
        ),
    ]
    for i in range(5):
        rules.append(AuthorizationRule(
            effect="allow", operation=f"eligible_{i:02d}.read",
            roles_any=("six",) if i == 4 else ("five", "six"),
        ))
    router.authorization_policy = AuthorizationPolicy(
        default_effect="deny", rules=tuple(rules),
    )
    return router


def _percentile(values: list[float], q: int) -> float:
    ordered = sorted(values)
    return ordered[max(0, ceil(len(ordered) * q / 100) - 1)]


def benchmark_density_matrix(
    *, noise_routes: int = 5100, iterations: int = 50,
) -> dict:
    if (
        type(noise_routes) is not int or not 0 <= noise_routes <= 10000
        or type(iterations) is not int or not 10 <= iterations <= 200
    ):
        raise ValueError("bounded native graph density benchmark only")
    router = _build_shared_density_source(noise_routes)
    started = time.perf_counter_ns()
    index = NativeSchemaGraphIndex.build(
        NativeSchemaPostingIndex.build(router.registry),
    )
    build_wall_ms = (time.perf_counter_ns() - started) / 1_000_000
    expected_registered = noise_routes + 2 + 5 + DENIED_TYPED_DISTRACTORS
    if index.field_index.indexed_route_count != expected_registered:
        raise ValueError("native density source count unexpected")
    if index.native_root_count != 1 or index.native_consumer_count != 30:
        raise ValueError("native density topology unexpected")

    metrics: dict[str, dict] = {}
    for scenario, count in SCENARIOS:
        actor = PrincipalContext(subject="synthetic", roles=(scenario,))
        reference = index.lookup(router, QUERY, group=GROUP, principal=actor)
        expected_status = (
            "no_proven_hit" if count == 0 else
            "over_k_unranked" if count > 5 else "complete"
        )
        expected_ids = {"case_service.read"} if count >= 1 else set()
        if count >= 5:
            expected_ids.update(f"eligible_{i:02d}.read" for i in range(4))
        if count >= 6:
            expected_ids.add("eligible_04.read")
        if (
            reference.status != expected_status
            or reference.qualified_path_count != count
            or reference.requested_k != 5
            or {
                path.consumer_route_id for path in reference.candidates
            } != (expected_ids if count <= 5 else set())
            or any(
                path.producer_route_id != "contact_directory.read"
                for path in reference.candidates
            )
        ):
            raise ValueError("native density principal or K5 result violated")

        for _ in range(WARMUP):
            if index.lookup(router, QUERY, group=GROUP, principal=actor) != reference:
                raise ValueError("native density warmup changed source result")

        wall_samples: list[float] = []
        cpu_samples: list[float] = []
        for _ in range(iterations):
            wall_start = time.perf_counter_ns()
            cpu_start = time.process_time_ns()
            response = index.lookup(router, QUERY, group=GROUP, principal=actor)
            cpu_samples.append((time.process_time_ns() - cpu_start) / 1_000_000)
            wall_samples.append((time.perf_counter_ns() - wall_start) / 1_000_000)
            if response != reference:
                raise ValueError("native density principal result unstable")

        metrics[scenario] = {
            "expected_and_verified_authorized_paths": count,
            "status": reference.status,
            "visible_candidates": len(reference.candidates),
            "typed_denied_distractors": DENIED_TYPED_DISTRACTORS,
            "query_wall_ms": {
                "p50": round(_percentile(wall_samples, 50), 4),
                "p95": round(_percentile(wall_samples, 95), 4),
                "p99": round(_percentile(wall_samples, 99), 4),
                "mean": round(fmean(wall_samples), 4),
            },
            "query_process_cpu_ms": {
                "p50": round(_percentile(cpu_samples, 50), 4),
                "p95": round(_percentile(cpu_samples, 95), 4),
                "p99": round(_percentile(cpu_samples, 99), 4),
            },
        }

    return {
        "evidence_tier": EVIDENCE,
        "independent_e2_qualified": False,
        "frozen_query_and_source": True,
        "one_index_shared_across_principals": True,
        "synthetic_registered_routes": expected_registered,
        "typed_denied_distractors": DENIED_TYPED_DISTRACTORS,
        "index_build_wall_ms": round(build_wall_ms, 4),
        "strict_k": 5,
        "warmup_queries_per_scenario": WARMUP,
        "measured_queries_per_scenario": iterations,
        "scenario_metrics": metrics,
        "peak_process_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "limitations": [
            "One developer-authored synthetic catalog/query and four host-role fixtures",
            "No independent truth, real endpoint/model call or task success",
            "Single Linux CI runner, high-selectivity typed schema distribution",
            "Peak process RSS includes source build and ALL scenario allocations",
            "No learned Top-K rank, statistical comparison or production SLO",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--noise-routes", type=int, default=5100)
    parser.add_argument("--iterations", type=int, default=50)
    args = parser.parse_args()
    print(json.dumps(
        benchmark_density_matrix(
            noise_routes=args.noise_routes, iterations=args.iterations,
        ),
        sort_keys=True, ensure_ascii=False,
    ))


if __name__ == "__main__":
    if sys.platform != "linux":
        raise SystemExit("RSS KiB telemetry is Linux-only")
    main()
