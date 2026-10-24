"""#1560 opt-in P1 source-index parity/CPU probe, NOT external answer E2.

Compares warm original Algorithm 1 field-coverage lookup on the exact
same source/owner/principal with and without the already existing native
semantic posting direct index. No tool is invoked or LLM is consulted.
"""
from __future__ import annotations

import argparse
import json
import platform
import resource
import time
from math import ceil
from typing import Any

from schemarouter import (
    CapabilityFieldContract,
    EndpointSpec,
    FieldSpec,
    NativeConceptCatalog,
    NativeDeclaredConcept,
    NativeSchemaGraphIndex,
    NativeSchemaPostingIndex,
    ToolSpec,
    retrieve_paper_field_coverage,
)
from scripts.benchmark_indexed_native_graph_g5_cpu_e0 import _synthetic_router
from scripts.benchmark_native_fork_fieldgroup_e0 import (
    ACTOR,
    ALIASES,
    GROUP,
    LEFT,
    RIGHT,
    ROOT,
    build_fixture,
)

EVIDENCE = "E0_SYNTHETIC_INDEXED_PAPER_DIRECT_NOT_E2"
QUERY = "customer status and owner"


def _percentile_ms(samples_ns: list[int], percentile: int) -> float:
    ordered = sorted(samples_ns)
    position = max(0, ceil(len(ordered) * percentile / 100) - 1)
    return round(ordered[position] / 1_000_000, 4)


def _direct_fixture(registered_routes: int):
    # Two source-native G5 fixture routes plus one direct two-field reader;
    # the remainder are identically shaped, unrelated research.label decoys.
    router = _synthetic_router(registered_routes - 3)
    router.add_tool(ToolSpec(
        name="paper_complete", source_type="crm", license="host-reviewed-synthetic",
        endpoints=[EndpointSpec(name="read", read_only=True, output_fields=[
            FieldSpec(name="request_id", semantic_id="crm.request_id",
                      json_schema={"type": "string"}, identifier=True),
            FieldSpec(name="status", semantic_id="crm.fork_status",
                      json_schema={"type": "string"}),
            FieldSpec(name="owner", semantic_id="crm.fork_owner",
                      json_schema={"type": "string"}),
        ])],
    ))
    catalog = NativeConceptCatalog(concepts=(NativeDeclaredConcept(
        concept_id="crm.paper_fields", aliases=(QUERY,),
        required_fields=(
            CapabilityFieldContract(semantic_id="crm.fork_status",
                                    json_schema={"type": "string"}),
            CapabilityFieldContract(semantic_id="crm.fork_owner",
                                    json_schema={"type": "string"}),
        ), source_type="crm", license="host-reviewed-synthetic",
    ),))
    return router, catalog


def _fork_fixture(registered_routes: int):
    router = build_fixture(registered_routes, mixed_scope=True)
    # The imported source fixture declares both attributes explicitly,
    # whereas NativeDeclaredFieldGroup permits either to be omitted.
    assert GROUP.source_type is not None and GROUP.license is not None
    catalog = NativeConceptCatalog(concepts=(NativeDeclaredConcept(
        concept_id="crm.paper_fork", aliases=ALIASES,
        required_fields=GROUP.required_fields,
        source_type=GROUP.source_type, license=GROUP.license,
    ),))
    return router, catalog


def benchmark(
    *, registered_routes: int, iterations: int = 10, scenario: str = "direct",
) -> dict[str, Any]:
    """Measure original full-scoped vs indexed-direct proof; require parity.

    Time to build and verify the complete catalog index is reported
    separately from warm repeated lookup. No baseline tuning or benchmark
    result can grant authority or alter product routing.
    """
    if (
        type(registered_routes) is not int
        or registered_routes not in (500, 5000)
        or type(iterations) is not int
        or not 10 <= iterations <= 50
    ):
        raise ValueError("expected 500/5000 routes and 10-50 iterations")
    if type(scenario) is not str or scenario not in {"direct", "fork"}:
        raise ValueError("expected source-native direct or fork scenario")
    if platform.system() != "Linux":
        # ru_maxrss reports KiB on Linux and bytes on macOS. Keep a
        # comparable host memory metric instead of silently mixing units.
        raise RuntimeError("Linux-only native schema CPU/RSS benchmark")

    router, catalog = (
        _direct_fixture(registered_routes) if scenario == "direct"
        else _fork_fixture(registered_routes)
    )
    query = QUERY if scenario == "direct" else ALIASES[0]
    start_build = time.perf_counter_ns()
    index = NativeSchemaGraphIndex.build(
        NativeSchemaPostingIndex.build(router.registry),
    )
    build_ms = round((time.perf_counter_ns() - start_build) / 1_000_000, 4)
    if index.field_index.indexed_route_count != registered_routes:
        raise AssertionError("source-native route count changed")

    def lookup(indexed: bool):
        return retrieve_paper_field_coverage(
            router, query, principal=ACTOR, catalog=catalog, index=index,
            experimental_indexed_direct=indexed,
        )

    # A genuinely complete source is known from *source registration*,
    # not assumed from either algorithm's candidate menu.
    baseline = lookup(False)
    indexed = lookup(True)
    expected_routes = (
        {"paper_complete.read"} if scenario == "direct" else {ROOT, LEFT, RIGHT}
    )
    if (
        baseline.status != "complete"
        or indexed.status != "complete"
        or baseline.alternatives != indexed.alternatives
        or len(indexed.alternatives) != 1
        or {r.route_id for r in indexed.alternatives[0].routes} != expected_routes
    ):
        raise AssertionError("source-attested indexed direct parity failed")

    times: dict[str, list[int]] = {"baseline": [], "indexed": []}
    # Interleave to limit time-related CPU/system bias. The initial
    # proof calls above are warm-up and excluded from these distributions.
    for iteration in range(iterations):
        modes = (False, True) if iteration % 2 == 0 else (True, False)
        for indexed_mode in modes:
            start = time.perf_counter_ns()
            measured = lookup(indexed_mode)
            elapsed_ns = time.perf_counter_ns() - start
            if measured.alternatives != baseline.alternatives:
                raise AssertionError("source-authorized field parity drifted")
            times["indexed" if indexed_mode else "baseline"].append(elapsed_ns)

    routes = indexed.alternatives[0].routes
    return {
        "evidence": EVIDENCE,
        "scenario": scenario,
        "registered_routes": registered_routes,
        "iterations_per_mode": iterations,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "status": indexed.status,
        "route_ids": [route.route_id for route in routes],
        "output_fields": [name for route in routes for name in route.output_fields],
        "field_projection_by_route": {
            route.route_id: list(route.output_fields) for route in routes
        },
        "required_semantic_ids": list(indexed.alternatives[0].required_semantic_ids),
        "index_build_ms": build_ms,
        "warm_ms": {
            mode: {
                "p50": _percentile_ms(samples, 50),
                "p95": _percentile_ms(samples, 95),
                "p99": _percentile_ms(samples, 99),
            }
            for mode, samples in times.items()
        },
        "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "external_e2": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--routes", type=int, choices=(500, 5000), required=True)
    parser.add_argument("--iterations", type=int, default=10)
    parser.add_argument("--scenario", choices=("direct", "fork"), default="direct")
    args = parser.parse_args()
    print(json.dumps(
        benchmark(
            registered_routes=args.routes,
            iterations=args.iterations,
            scenario=args.scenario,
        ),
        ensure_ascii=False, sort_keys=True, indent=2,
    ))


if __name__ == "__main__":
    main()
