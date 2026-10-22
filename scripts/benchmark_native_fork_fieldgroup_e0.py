"""#1560: source-native fork at 500/5000 catalog routes, E0 only.

Reuses the existing source-native G5 index and graph, with a separate
development-only exhaustive source-contract reference. No provider/agent E2.
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
from typing import Any

from schemarouter import (
    CapabilityFieldContract,
    EndpointSpec,
    FieldSpec,
    NativeDeclaredFieldGroup,
    ParameterSpec,
    PrincipalContext,
    SchemaRouter,
    ToolSpec,
)
from schemarouter.field_group_retrieval import _complete_fields
from schemarouter.native_graph_index import NativeSchemaGraphIndex
from schemarouter.native_semantic_index import NativeSchemaPostingIndex
from scripts.benchmark_indexed_native_graph_g5_cpu_e0 import _synthetic_router

EVIDENCE = "E0_SYNTHETIC_500_5000_NATIVE_FORK_NOT_PUBLISHER_E2"
ALIASES = ("customer status and owner", "고객 상태와 담당자", "顧客状態と担当者")
ACTOR = PrincipalContext(subject="synthetic-reader", roles=("reader",))
GROUP = NativeDeclaredFieldGroup(
    aliases=ALIASES,
    required_fields=(
        CapabilityFieldContract(
            semantic_id="crm.fork_status", json_schema={"type": "string"},
        ),
        CapabilityFieldContract(
            semantic_id="crm.fork_owner", json_schema={"type": "string"},
        ),
    ),
    source_type="crm",
    license="host-reviewed-synthetic",
)
ROOT = "fork_origin.read"
LEFT = "fork_status.read"
RIGHT = "fork_owner.read"


def build_fixture(registered_routes: int) -> SchemaRouter:
    if type(registered_routes) is not int or registered_routes not in (500, 5000):
        raise ValueError("only preregistered 500/5000 synthetic catalogs")
    router = _synthetic_router(registered_routes - 5)
    router.add_tool(ToolSpec(
        name="fork_origin", source_type="crm", license="host-reviewed-synthetic",
        endpoints=[EndpointSpec(
            name="read", read_only=True,
            output_fields=[FieldSpec(
                name="customer_id", semantic_id="crm.fork_customer_id",
                json_schema={"type": "string"}, identifier=True,
            )],
            output_schema={
                "type": "object",
                "properties": {"customer_id": {"type": "string"}},
                "required": ["customer_id"],
            },
        )],
    ))
    for tool_name, semantic, field_name in (
        ("fork_status", "crm.fork_status", "status"),
        ("fork_owner", "crm.fork_owner", "owner"),
    ):
        router.add_tool(ToolSpec(
            name=tool_name, source_type="crm",
            license="host-reviewed-synthetic",
            endpoints=[EndpointSpec(
                name="read", read_only=True,
                parameters=[ParameterSpec(
                    name="customer_id", semantic_id="crm.fork_customer_id",
                    required=True, json_schema={"type": "string"},
                )],
                input_schema={
                    "type": "object",
                    "properties": {"customer_id": {"type": "string"}},
                    "required": ["customer_id"],
                },
                output_fields=[FieldSpec(
                    name=field_name, semantic_id=semantic,
                    json_schema={"type": "string"},
                )],
            )],
        ))
    return router


def exhaustive_source_fork_reference(router: SchemaRouter) -> tuple[tuple[str, str, str], ...]:
    """Benchmark-only original registry scan, NOT the indexed product path.

    This intentionally does not read the G5 posting/graph indexes; it checks
    current original, per-principal scoped source fields and their structural
    parameter contracts. It only evaluates the constrained 1-root/2-leaf
    experiment: no arbitrary union or ranker.
    """
    permitted = router._authorization_predicate(ACTOR)
    if permitted is None:
        raise AssertionError("development-only principal needs explicit policy")
    allowed: list[tuple[ToolSpec, EndpointSpec]] = []
    for tool in router.registry.tools():
        for ep in tool.endpoints:
            if (
                tool.source_type != "crm"
                or tool.license != "host-reviewed-synthetic"
                or ep.read_only is not True
                or ep.destructive is True
                or not permitted(tool, ep)
            ):
                continue
            visible = router._data_scope_endpoint_view(ACTOR, tool, ep)
            if visible is not None:
                allowed.append((tool, visible))
    roots: list[tuple[str, str]] = []
    leaves: dict[str, list[str]] = {"crm.fork_status": [], "crm.fork_owner": []}
    for tool, ep in allowed:
        route = f"{tool.key}.{ep.name}"
        if not ep.parameters and ep.output_schema == {
            "type": "object",
            "properties": {"customer_id": {"type": "string"}},
            "required": ["customer_id"],
        } and sum(
            f.name == "customer_id"
            and f.identifier is True
            and f.semantic_id == "crm.fork_customer_id"
            for f in ep.output_fields
        ) == 1:
            roots.append((route, "customer_id"))
        if len(ep.parameters) != 1:
            continue
        param = ep.parameters[0]
        if (
            param.required is not True
            or param.semantic_id != "crm.fork_customer_id"
            or param.json_schema != {"type": "string"}
            or ep.input_schema != {
                "type": "object",
                "properties": {param.name: {"type": "string"}},
                "required": [param.name],
            }
        ):
            continue
        for requirement in GROUP.required_fields:
            if _complete_fields(ep.output_fields, (requirement,)):
                leaves[requirement.semantic_id].append(route)
    combinations = [
        (root, left, right)
        for root, _ in roots
        for left in leaves["crm.fork_status"]
        for right in leaves["crm.fork_owner"]
        if len({root, left, right}) == 3
    ]
    return tuple(sorted(combinations))


def percentile(values: list[float], n: int) -> float:
    samples = sorted(values)
    return round(samples[max(0, ceil(len(samples) * n / 100) - 1)], 4)


def benchmark(*, registered_routes: int, iterations: int = 30) -> dict[str, Any]:
    if type(iterations) is not int or not 10 <= iterations <= 100:
        raise ValueError("bounded E0 sample count required")
    router = build_fixture(registered_routes)
    start = time.perf_counter_ns()
    index = NativeSchemaGraphIndex.build(
        NativeSchemaPostingIndex.build(router.registry),
    )
    build_ms = (time.perf_counter_ns() - start) / 1_000_000
    expected = exhaustive_source_fork_reference(router)
    if expected != ((ROOT, LEFT, RIGHT),):
        raise AssertionError("original-source exhaustive reference unexpectedly drifted")
    for query in ALIASES:
        out = index.lookup_shared_root_forks(
            router, query, group=GROUP, principal=ACTOR,
        )
        found = tuple(
            (candidate.root_route_id, *candidate.branch_route_ids)
            for candidate in out.candidates
        )
        if (
            out.status != "complete"
            or out.qualified_fork_count != 1
            or found != expected
            or out.executable_authority
            or out.independent_quality_evidence
        ):
            raise AssertionError("indexed shared-root field evidence deviates from oracle")
    # A dynamic health revocation must invalidate the same cached index.
    router.planner.availability_predicate = (
        lambda tool, _ep: tool.key != "fork_owner"
    )
    unavailable = index.lookup_shared_root_forks(
        router, ALIASES[0], group=GROUP, principal=ACTOR,
    )
    if unavailable.status != "no_proven_hit" or unavailable.candidates:
        raise AssertionError("revoked original consumer was disclosed")
    router.planner.availability_predicate = None

    times: list[float] = []
    cpu: list[float] = []
    fixed = index.lookup_shared_root_forks(
        router, ALIASES[0], group=GROUP, principal=ACTOR,
    )
    for _ in range(5):
        assert index.lookup_shared_root_forks(
            router, ALIASES[0], group=GROUP, principal=ACTOR,
        ) == fixed
    for _ in range(iterations):
        start = time.perf_counter_ns()
        cpu_start = time.process_time_ns()
        observed = index.lookup_shared_root_forks(
            router, ALIASES[0], group=GROUP, principal=ACTOR,
        )
        cpu.append((time.process_time_ns() - cpu_start) / 1_000_000)
        times.append((time.perf_counter_ns() - start) / 1_000_000)
        if observed != fixed:
            raise AssertionError("same source snapshot yielded inconsistent G5 fork")
    return {
        "evidence_tier": EVIDENCE,
        "independent_e2_qualified": False,
        "registered_native_routes": index.field_index.indexed_route_count,
        "exhaustive_original_source_forks": len(expected),
        "verified_source_pinned_forks": fixed.qualified_fork_count,
        "en_ko_ja_exact_fieldgroup_parity": True,
        "same_snapshot_health_revocation_refused": True,
        "strict_k": fixed.requested_k,
        "schema_execution_authority": fixed.executable_authority,
        "warmup_count": 5,
        "sample_count": iterations,
        "index_build_wall_ms": round(build_ms, 4),
        "query_wall_ms": {
            "p50": percentile(times, 50),
            "p95": percentile(times, 95),
            "p99": percentile(times, 99),
            "mean": round(fmean(times), 4),
        },
        "query_process_cpu_ms": {
            "p50": percentile(cpu, 50),
            "p95": percentile(cpu, 95),
            "p99": percentile(cpu, 99),
        },
        "peak_process_rss_kib": int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "limitations": [
            "Development-authored synthetic CRM source contracts only",
            "Exhaustive oracle applies only to predefined flat one-key two-leaf topology",
            "The original-source benchmark oracle reuses shared FieldGroup field comparator",
            "No independent publisher-authored route/permission gold or observed records",
            "No live provider, agent executor, numeric SLA, stable environment or ranker",
            "Process RSS includes all catalog registration and graph build",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registered-routes", type=int, choices=(500, 5000), required=True)
    parser.add_argument("--iterations", type=int, default=30)
    args = parser.parse_args()
    print(json.dumps(
        benchmark(registered_routes=args.registered_routes, iterations=args.iterations),
        ensure_ascii=False, sort_keys=True,
    ))


if __name__ == "__main__":
    if sys.platform != "linux":
        raise SystemExit("Linux-only ru_maxrss KiB benchmark")
    main()
