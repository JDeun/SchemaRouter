"""#1560 opt-in indexed/direct-vs-existing planner parity, synthetic E0.

Original registered ToolSpecs and a separate source-scan oracle are used
ONLY for verification. The product query sees the existing immutable index,
trusted declared concept, current principal and current policy/availability.
No model, provider invocation, independent E2 task or product default change.
"""
from __future__ import annotations

import argparse
import json
import platform
import resource
import time
from math import ceil
from statistics import fmean
from typing import Any

from schemarouter import (
    AuthorizationPolicy,
    AuthorizationRule,
    CapabilityFieldContract,
    DataScopeRule,
    EndpointSpec,
    FieldSpec,
    NativeConceptCatalog,
    NativeDeclaredConcept,
    PrincipalContext,
    ToolSpec,
)
from schemarouter.concept_graph_retrieval import retrieve_authorized_concept_graph
from schemarouter.field_group_retrieval import _complete_fields, _root_envelope_empty
from schemarouter.native_graph_index import NativeSchemaGraphIndex
from schemarouter.native_semantic_index import NativeSchemaPostingIndex
from scripts.benchmark_indexed_native_graph_g5_cpu_e0 import _synthetic_router

EVIDENCE_TIER = "E0_SYNTHETIC_INDEXED_CONCEPT_PARITY_NOT_E2"
ALIASES = ("case status", "문의 상태", "問い合わせ状態")
ACTOR = PrincipalContext(subject="synthetic-readonly", roles=("reader",))
DIRECT_ROUTES = tuple(f"direct_case_{i}.read" for i in range(6))
CASES = ("one", "six", "none", "hidden", "health")
CATALOG = NativeConceptCatalog(concepts=(NativeDeclaredConcept(
    concept_id="case_status",
    aliases=ALIASES,
    required_fields=(CapabilityFieldContract(
        semantic_id="crm.status", json_schema={"type": "string"},
    ),),
    source_type="crm",
    license="host-reviewed-synthetic",
),))


def build_fixture(registered_routes: int):
    """Keep 500/5000 source-native route counts fixed across every arm."""
    if type(registered_routes) is not int or registered_routes not in (500, 5000):
        raise ValueError("only preregistered 500/5000 source catalogues allowed")
    router = _synthetic_router(registered_routes - 8)
    for i in range(6):
        router.add_tool(ToolSpec(
            name=f"direct_case_{i}", source_type="crm",
            license="host-reviewed-synthetic",
            endpoints=[EndpointSpec(
                name="read", read_only=True,
                output_fields=[FieldSpec(
                    name="status", semantic_id="crm.status",
                    json_schema={"type": "string"},
                )],
            )],
        ))
    assert router.registry.version == registered_routes
    return router


def configure_scope(router, scenario: str) -> None:
    if scenario not in CASES:
        raise ValueError("unknown predeclared E0 availability/scope scenario")
    visible = (
        range(6) if scenario in ("six", "hidden", "health") else
        (0,) if scenario in ("one", "health") else ()
    )
    allowed = ("contact_directory.read", "case_service.read") + tuple(
        DIRECT_ROUTES[i] for i in visible
    )
    router.authorization_policy = AuthorizationPolicy(
        default_effect="deny",
        rules=tuple(AuthorizationRule(
            effect="allow", operation=route, roles_any=("reader",),
        ) for route in allowed),
        data_rules=tuple(DataScopeRule(
            operation=route, roles_any=("reader",),
            hidden_fields=("status",),
        ) for route in DIRECT_ROUTES) if scenario == "hidden" else (),
    )
    router.planner.availability_predicate = (
        lambda tool, endpoint: f"{tool.key}.{endpoint.name}" not in DIRECT_ROUTES[1:]
    ) if scenario == "health" else None


def original_source_direct_oracle(router) -> tuple[str, ...]:
    """Offline original registry scan; NEVER called in either timed query."""
    permitted = router._authorization_predicate(ACTOR)
    if permitted is None:
        raise AssertionError("no explicit authorization")
    required = CATALOG.concepts[0].required_fields
    found: list[str] = []
    for tool in router.registry.tools():
        if tool.source_type != "crm" or tool.license != "host-reviewed-synthetic":
            continue
        for endpoint in tool.endpoints:
            route = f"{tool.key}.{endpoint.name}"
            if (
                not endpoint.read_only or endpoint.destructive
                or not _root_envelope_empty(endpoint)
                or not permitted(tool, endpoint)
            ):
                continue
            health = router.planner.availability_predicate
            if health is not None and not health(tool, endpoint):
                continue
            scoped = router._data_scope_endpoint_view(ACTOR, tool, endpoint)
            if scoped is not None and _complete_fields(scoped.output_fields, required):
                found.append(route)
    return tuple(sorted(found))


def _percentile(values: list[float], q: int) -> float:
    ordered = sorted(values)
    return ordered[max(0, ceil(len(ordered) * q / 100) - 1)]


def _metrics(wall: list[float], cpu: list[float]) -> dict[str, Any]:
    return {
        "wall_ms": {
            "p50": round(_percentile(wall, 50), 4),
            "p95": round(_percentile(wall, 95), 4),
            "p99": round(_percentile(wall, 99), 4),
            "mean": round(fmean(wall), 4),
        },
        "process_cpu_ms": {
            "p50": round(_percentile(cpu, 50), 4),
            "p95": round(_percentile(cpu, 95), 4),
            "p99": round(_percentile(cpu, 99), 4),
        },
    }


def benchmark(*, registered_routes: int, iterations: int = 10) -> dict[str, Any]:
    if type(iterations) is not int or not 10 <= iterations <= 40:
        raise ValueError("bounded, preregistered 10-40 benchmark samples required")
    router = build_fixture(registered_routes)
    begin = time.perf_counter_ns()
    index = NativeSchemaGraphIndex.build(NativeSchemaPostingIndex.build(router.registry))
    build_ms = (time.perf_counter_ns() - begin) / 1_000_000
    if index.field_index.indexed_route_count != registered_routes:
        raise AssertionError("registered original source route count drift")

    scenario_rows = []
    for scenario in CASES:
        configure_scope(router, scenario)
        original = original_source_direct_oracle(router)
        expected_count = {
            "one": 1, "six": 6, "none": 0, "hidden": 0, "health": 1,
        }[scenario]
        if len(original) != expected_count:
            raise AssertionError("source oracle permission/field/scope count drift")
        if len(original) == 1 and original != (DIRECT_ROUTES[0],):
            raise AssertionError("wrong original direct source")
        baseline_walls: list[float] = []
        indexed_walls: list[float] = []
        baseline_cpu: list[float] = []
        indexed_cpu: list[float] = []
        statuses: set[str] = set()
        for query in ALIASES:
            def lookup(*, indexed: bool, pinned_query: str = query):
                return retrieve_authorized_concept_graph(
                    router, pinned_query, principal=ACTOR, catalog=CATALOG,
                    index=index, experimental_indexed_direct=indexed,
                )

            # One untimed preflight for each arm; only the original source
            # oracle determines expected direct-branch completeness.
            baseline = lookup(indexed=False)
            candidate = lookup(indexed=True)
            if baseline != candidate:
                raise AssertionError("indexed/full planner concept-path parity drift")
            if (
                candidate.requested_k != 5 or candidate.executable_authority
                or candidate.independent_quality_evidence
            ):
                raise AssertionError("indexed proof became executable or qualified")
            if expected_count > 5:
                if candidate.status != "over_k_unranked" or candidate.route_ids:
                    raise AssertionError("over-K alternatives were disclosed")
            elif expected_count == 1:
                if candidate.status != "complete" or candidate.route_ids != original:
                    raise AssertionError("correct original direct source not selected")
            elif (
                candidate.status != "complete"
                or candidate.route_ids != ("contact_directory.read", "case_service.read")
            ):
                raise AssertionError("missing typed one-hop fallback")
            statuses.add(candidate.status)

            for _ in range(2):
                if lookup(indexed=False) != baseline or lookup(indexed=True) != candidate:
                    raise AssertionError("warmup changed original fixture results")
            for _ in range(iterations):
                for indexed, walls, cpus in (
                    (False, baseline_walls, baseline_cpu),
                    (True, indexed_walls, indexed_cpu),
                ):
                    t = time.perf_counter_ns()
                    c = time.process_time_ns()
                    observed = lookup(indexed=indexed)
                    cpus.append((time.process_time_ns() - c) / 1_000_000)
                    walls.append((time.perf_counter_ns() - t) / 1_000_000)
                    if observed != candidate:
                        raise AssertionError("live scope or source drift in benchmark")
        if len(statuses) != 1:
            raise AssertionError("EN/KO/JA synthetic result divergence")
        scenario_rows.append({
            "scenario": scenario,
            "original_authorized_direct_count": expected_count,
            "status": next(iter(statuses)),
            "paired_queries_per_arm": len(ALIASES) * iterations,
            "existing_planner": _metrics(baseline_walls, baseline_cpu),
            "optin_posting_index": _metrics(indexed_walls, indexed_cpu),
            "exact_structural_parity": True,
        })
    return {
        "evidence_tier": EVIDENCE_TIER,
        "independent_e2_qualified": False,
        "model_or_real_provider_called": False,
        "new_default_routing": False,
        "registered_source_routes": registered_routes,
        "source_index_sha256": index.field_index.snapshot_id,
        "strict_k": 5,
        "index_build_wall_ms": round(build_ms, 4),
        "languages": list(ALIASES),
        "scenarios": scenario_rows,
        "peak_process_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "python": platform.python_version(),
        "limitations": (
            "Synthetic native source only; matched source/principal/query,"
            " author-disclosed DEV scenario, no external publisher gold,"
            " agent final-answer evidence, independent E2 or production SLO."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registered-routes", type=int, required=True, choices=(500, 5000))
    parser.add_argument("--iterations", type=int, default=10)
    args = parser.parse_args()
    print(json.dumps(
        benchmark(registered_routes=args.registered_routes, iterations=args.iterations),
        ensure_ascii=False, sort_keys=True, allow_nan=False,
    ))


if __name__ == "__main__":
    main()
