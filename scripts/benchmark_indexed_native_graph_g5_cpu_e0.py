"""Reproducible local CPU/RSS profile for opt-in G5, NOT independent E2.

Each route is synthetic and provider-free. No network, model, task gold, or
agent execution. Build cost and indexed query cost are reported separately.
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
    CapabilityFieldContract,
    EndpointSpec,
    FieldSpec,
    NativeDeclaredFieldGroup,
    PrincipalContext,
    SchemaRouter,
    ToolSpec,
)
from schemarouter.native_graph_index import NativeSchemaGraphIndex
from schemarouter.native_semantic_index import NativeSchemaPostingIndex

EVIDENCE = "E0_SYNTHETIC_CPU_NOT_INDEPENDENT"
QUERY = "case status"
PRINCIPAL = PrincipalContext(subject="synthetic-readonly-user", roles=("reader",))
GROUP = NativeDeclaredFieldGroup(
    aliases=(QUERY,),
    required_fields=(CapabilityFieldContract(
        semantic_id="crm.status", json_schema={"type": "string"},
    ),),
    source_type="crm", license="host-reviewed-synthetic",
)


def _synthetic_router(noise_routes: int) -> SchemaRouter:
    router = SchemaRouter(authorization_policy=AuthorizationPolicy(
        default_effect="deny",
        rules=(AuthorizationRule(
            effect="allow", operation="*.read", roles_any=("reader",),
        ),),
    ))
    router.add_tool(ToolSpec(
        name="contact_directory", source_type="crm",
        license="host-reviewed-synthetic",
        endpoints=[EndpointSpec(
            name="read", read_only=True, output_fields=[FieldSpec(
                name="customer_id", semantic_id="crm.customer_id",
                json_schema={"type": "string"}, identifier=True,
            )],
        )],
    ))
    router.add_tool(ToolSpec(
        name="case_service", source_type="crm",
        license="host-reviewed-synthetic",
        endpoints=[EndpointSpec(
            name="read", read_only=True,
            parameters=[{
                "name": "customer_id", "required": True, "location": "argument",
                "json_schema": {"type": "string"},
                "semantic_id": "crm.customer_id",
            }],
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
    ))
    for i in range(noise_routes):
        # Intentional heterogeneous unrelated registered native schemas:
        # no task-gold derived semantics; query must avoid fetching these.
        router.add_tool(ToolSpec(
            name=f"unrelated_{i:05d}", source_type="research",
            license="host-reviewed-synthetic",
            endpoints=[EndpointSpec(
                name="read", read_only=True, output_fields=[FieldSpec(
                    name="label", semantic_id="research.label",
                    json_schema={"type": "string"},
                )],
            )],
        ))
    return router


def _percentile(values: list[float], percentile: int) -> float:
    ordered = sorted(values)
    return ordered[max(0, ceil(len(ordered) * percentile / 100) - 1)]


def benchmark(*, noise_routes: int = 5100, iterations: int = 50) -> dict:
    if (
        type(noise_routes) is not int or not 0 <= noise_routes <= 10000
        or type(iterations) is not int or not 10 <= iterations <= 200
    ):
        raise ValueError("bounded synthetic CPU benchmark only")
    router = _synthetic_router(noise_routes)
    build_started = time.perf_counter_ns()
    field_index = NativeSchemaPostingIndex.build(router.registry)
    graph_index = NativeSchemaGraphIndex.build(field_index)
    build_ms = (time.perf_counter_ns() - build_started) / 1_000_000
    result = graph_index.lookup(
        router, QUERY, group=GROUP, principal=PRINCIPAL,
    )
    if (
        graph_index.field_index.indexed_route_count != noise_routes + 2
        or result.status != "complete"
        or result.qualified_path_count != 1
        or result.candidates[0].producer_route_id != "contact_directory.read"
        or result.candidates[0].consumer_route_id != "case_service.read"
    ):
        raise ValueError("invalid native graph synthetic reference result")
    # Prewarm not timed, keep observed metadata/generation constant.
    for _ in range(5):
        check = graph_index.lookup(
            router, QUERY, group=GROUP, principal=PRINCIPAL,
        )
        if check != result:
            raise ValueError("source-dependent G5 benchmark result drift")
    elapsed: list[float] = []
    cpu_ms: list[float] = []
    for _ in range(iterations):
        wall = time.perf_counter_ns()
        cpu = time.process_time_ns()
        check = graph_index.lookup(
            router, QUERY, group=GROUP, principal=PRINCIPAL,
        )
        cpu_ms.append((time.process_time_ns() - cpu) / 1_000_000)
        elapsed.append((time.perf_counter_ns() - wall) / 1_000_000)
        if check != result:
            raise ValueError("G5 benchmark source fingerprint result drift")
    usage = resource.getrusage(resource.RUSAGE_SELF)
    return {
        "evidence_tier": EVIDENCE,
        "independent_e2_qualified": False,
        "synthetic_registered_routes": graph_index.field_index.indexed_route_count,
        "graph_roots": graph_index.native_root_count,
        "graph_consumers": graph_index.native_consumer_count,
        "warmup_queries": 5,
        "measured_queries": iterations,
        "strict_k": result.requested_k,
        "verified_candidate_paths": result.qualified_path_count,
        "build_wall_ms": round(build_ms, 4),
        "query_wall_ms": {
            "p50": round(_percentile(elapsed, 50), 4),
            "p95": round(_percentile(elapsed, 95), 4),
            "p99": round(_percentile(elapsed, 99), 4),
            "mean": round(fmean(elapsed), 4),
        },
        "query_process_cpu_ms": {
            "p50": round(_percentile(cpu_ms, 50), 4),
            "p95": round(_percentile(cpu_ms, 95), 4),
            "p99": round(_percentile(cpu_ms, 99), 4),
        },
        "peak_process_rss_kib": int(usage.ru_maxrss),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "limitations": [
            "Developer-synthetic registry, query, ontology and answer topology",
            "No real provider communication, independent task gold or model agent",
            "One-process peak RSS includes registration and index build",
            "No ranking over K, no confidence intervals or comparative speedup",
            "No release or commercial SLO qualification",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--noise-routes", type=int, default=5100)
    parser.add_argument("--iterations", type=int, default=50)
    args = parser.parse_args()
    print(json.dumps(
        benchmark(noise_routes=args.noise_routes, iterations=args.iterations),
        ensure_ascii=False, sort_keys=True,
    ))


if __name__ == "__main__":
    if sys.platform != "linux":
        raise SystemExit("Linux-only ru_maxrss KiB benchmark")
    main()
