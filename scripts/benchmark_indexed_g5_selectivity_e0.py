"""Paired G5 query-selectivity E0: no agent, no real provider, no quality rank.

Same indexed source across all scenarios; only query/owner policy/field
visibility/availability changes. The fixture's expected route IDs are
used by the trusted synthetic ASSERTIONS, never handed to the retriever.
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
    DataScopeRule,
    EndpointSpec,
    FieldSpec,
    NativeDeclaredFieldGroup,
    ToolSpec,
)
from schemarouter.native_graph_index import NativeSchemaGraphIndex
from schemarouter.native_semantic_index import NativeSchemaPostingIndex
from scripts.benchmark_indexed_native_graph_g5_cpu_e0 import (
    GROUP,
    PRINCIPAL,
    QUERY,
    _synthetic_router,
)

EVIDENCE = "E0_SYNTHETIC_SELECTIVITY_NOT_INDEPENDENT"
BROAD_QUERY = "research label"
BROAD_GROUP = NativeDeclaredFieldGroup(
    aliases=(BROAD_QUERY,),
    required_fields=(CapabilityFieldContract(
        semantic_id="research.label", json_schema={"type": "string"},
    ),),
    source_type="research", license="host-reviewed-synthetic",
)


def _quantile(samples: list[float], q: int) -> float:
    ordered = sorted(samples)
    return ordered[max(0, ceil(len(ordered) * q / 100) - 1)]


def _scenario_policy(*, consumers: tuple[str, ...], root: bool = True,
                     hide_identifier: bool = False) -> AuthorizationPolicy:
    names = (("contact_directory",) if root else ()) + consumers
    return AuthorizationPolicy(
        default_effect="deny",
        rules=tuple(AuthorizationRule(
            effect="allow", operation=f"{name}.read", roles_any=("reader",),
        ) for name in names),
        data_rules=(DataScopeRule(
            operation="contact_directory.read", roles_any=("reader",),
            hidden_fields=("customer_id",),
        ),) if hide_identifier else (),
    )


def _require_expected(index, router, *, query, group,
                      count: int, consumers: tuple[str, ...]):
    actual = index.lookup(router, query, group=group, principal=PRINCIPAL)
    if (
        actual.qualified_path_count != count
        or actual.requested_k != 5
        or actual.independent_quality_evidence
        or actual.executable_authority
        or actual.calibrated_no_fit
        or actual.index_snapshot_id != index.field_index.snapshot_id
    ):
        raise ValueError("paired synthetic selectivity candidate drift")
    if count > 5:
        if actual.status != "over_k_unranked" or actual.candidates:
            raise ValueError("G5 emitted arbitrary truncated over-K routes")
    elif count == 0:
        if actual.status != "no_proven_hit" or actual.candidates:
            raise ValueError("G5 emitted unauthorized or unproved route")
    else:
        observed = {x.consumer_route_id for x in actual.candidates}
        expected = {f"{name}.read" for name in consumers}
        if (
            actual.status != "complete"
            or observed != expected
            or len(actual.candidates) != count
            or any(x.producer_route_id != "contact_directory.read"
                   for x in actual.candidates)
        ):
            raise ValueError("G5 typed authorized path oracle mismatch")
    return actual


def _measure(index, router, *, query: str, group,
             expected_count: int, consumers: tuple[str, ...],
             iterations: int, warmup: int = 3) -> dict:
    previous = _require_expected(index, router, query=query, group=group,
                                 count=expected_count, consumers=consumers)
    for _ in range(warmup):
        if index.lookup(router, query, group=group, principal=PRINCIPAL) != previous:
            raise ValueError("G5 source revision or scoped response changed")
    wall_ms: list[float] = []
    cpu_ms: list[float] = []
    for _ in range(iterations):
        cpu = time.process_time_ns()
        wall = time.perf_counter_ns()
        row = index.lookup(router, query, group=group, principal=PRINCIPAL)
        wall_ms.append((time.perf_counter_ns() - wall) / 1e6)
        cpu_ms.append((time.process_time_ns() - cpu) / 1e6)
        if row != previous:
            raise ValueError("G5 inconsistent synthetic scenario output")
    return {
        "verified_path_count": previous.qualified_path_count,
        "returned_path_count": len(previous.candidates),
        "status": previous.status,
        "warmup_queries": warmup,
        "measured_queries": iterations,
        "wall_ms": {
            "p50": round(_quantile(wall_ms, 50), 4),
            "p95": round(_quantile(wall_ms, 95), 4),
            "p99": round(_quantile(wall_ms, 99), 4),
            "mean": round(fmean(wall_ms), 4),
        },
        "process_cpu_ms": {
            "p50": round(_quantile(cpu_ms, 50), 4),
            "p95": round(_quantile(cpu_ms, 95), 4),
            "p99": round(_quantile(cpu_ms, 99), 4),
        },
    }


def benchmark_selectivity(*, noise_routes: int = 5100, iterations: int = 20,
                          broad_iterations: int = 3) -> dict:
    if (
        type(noise_routes) is not int or not 1 <= noise_routes <= 10000
        or type(iterations) is not int or not 10 <= iterations <= 100
        or type(broad_iterations) is not int or
        not 2 <= broad_iterations <= 10
    ):
        raise ValueError("invalid bounded E0 selectivity benchmark parameters")
    router = _synthetic_router(noise_routes)
    # A fixed owner-approved matching source catalog, independent of
    # individual query and principal policy at retrieval time.
    variants = tuple(f"case_variant_{i}" for i in range(6))
    for name in variants:
        router.add_tool(ToolSpec(
            name=name, source_type="crm", license="host-reviewed-synthetic",
            endpoints=[EndpointSpec(
                name="read", read_only=True,
                parameters=[{
                    "name": "customer_id", "required": True,
                    "location": "argument",
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
    names = ("case_service", *variants)
    t0 = time.perf_counter_ns()
    index = NativeSchemaGraphIndex.build(
        NativeSchemaPostingIndex.build(router.registry),
    )
    build_wall_ms = (time.perf_counter_ns() - t0) / 1e6
    if index.field_index.indexed_route_count != noise_routes + 8:
        raise ValueError("synthetic source registry not complete")

    cases: dict[str, dict] = {}

    def run(label: str, subset: tuple[str, ...], *,
            root: bool = True, hidden: bool = False, unavailable: tuple[str, ...] = (),
            group=GROUP, query=QUERY, expected: int | None = None,
            samples: int | None = None) -> None:
        router.authorization_policy = _scenario_policy(
            consumers=subset, root=root, hide_identifier=hidden,
        )
        # This condition changes only current availability, not registered
        # ToolSpec source; witness protects it throughout each query.
        denied_now = frozenset(unavailable)
        router.planner.availability_predicate = (
            (lambda tool, ep: tool.key not in denied_now)
            if denied_now else None
        )
        eligible = () if not root or hidden else tuple(
            x for x in subset if x not in denied_now
        )
        n = len(eligible) if expected is None else expected
        cases[label] = _measure(
            index, router, query=query, group=group, expected_count=n,
            consumers=eligible if group is GROUP else (),
            iterations=samples or iterations,
        )

    run("one_authorized", names[:1])
    run("five_authorized", names[:5])
    run("seven_eligible_overflow", names)
    run("root_denied", names, root=False)
    run("root_identifier_hidden", names, hidden=True)
    run("two_consumers_unavailable", names,
        unavailable=names[-2:])
    # The *same 5k-route catalog* contains thousands of native
    # research.label output postings but zero typed graph consumer inputs.
    # This explicitly probes a broad semantic false-positive posting
    # and MUST NOT be extrapolated from the sparse CRM query.
    run("broad_semantic_no_path", names, query=BROAD_QUERY,
        group=BROAD_GROUP, expected=0, samples=broad_iterations)

    router.planner.availability_predicate = None
    return {
        "evidence_tier": EVIDENCE,
        "independent_e2_qualified": False,
        "provider_network_or_model_calls": 0,
        "strict_k": 5,
        "synthetic_registered_routes": index.field_index.indexed_route_count,
        "graph_roots": index.native_root_count,
        "graph_consumers": index.native_consumer_count,
        "broad_posting_count": len(
            index.field_index.postings.get("research.label", ()),
        ),
        "index_build_wall_ms": round(build_wall_ms, 4),
        "peak_process_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "scenarios": cases,
        "limitations": [
            "All ontology, registry, permissions and expected paths are synthetic",
            "The synthetic oracle is fixture-defined, not publisher-independent",
            "No model, provider API or native end-task completion",
            "Broad-posting p99 uses few repetitions; no representative SLO",
            "No quality ranking over K5, no cross-run confidence intervals",
        ],
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--noise-routes", type=int, default=5100)
    ap.add_argument("--iterations", type=int, default=20)
    ap.add_argument("--broad-iterations", type=int, default=3)
    args = ap.parse_args()
    print(json.dumps(benchmark_selectivity(
        noise_routes=args.noise_routes, iterations=args.iterations,
        broad_iterations=args.broad_iterations,
    ), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    if sys.platform != "linux":
        raise SystemExit("Linux-only ru_maxrss KiB selectivity profile")
    main()
