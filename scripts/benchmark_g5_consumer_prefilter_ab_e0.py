"""Same-process G5 broad-posting AB: canonical-edge prefilter on vs off.

The OFF condition widens only a frozen dataclass view's *structural*
consumer superset, leaving the exact SAME production G5 lookup routine,
registry, canonical graph, original policy and principal untouched.
This is an E0 diagnostic, not a production fallback or independent SLO.
"""
from __future__ import annotations

import argparse
import json
import platform
import sys
import time
from dataclasses import replace
from math import ceil

from schemarouter.native_graph_index import NativeSchemaGraphIndex
from schemarouter.native_semantic_index import NativeSchemaPostingIndex
from scripts.benchmark_indexed_g5_selectivity_e0 import (
    BROAD_GROUP,
    BROAD_QUERY,
)
from scripts.benchmark_indexed_native_graph_g5_cpu_e0 import (
    PRINCIPAL,
    _synthetic_router,
)

EVIDENCE = "E0_PAIRED_SYNTHETIC_STRUCTURAL_PREFILTER_NOT_INDEPENDENT"


def _percentile(values: list[float], q: int) -> float:
    xs = sorted(values)
    return xs[max(0, ceil(len(xs) * q / 100) - 1)]


def benchmark_ab(*, noise_routes: int = 5100, iterations: int = 5) -> dict:
    if (
        type(noise_routes) is not int or not 1 <= noise_routes <= 10000
        or type(iterations) is not int or not 3 <= iterations <= 10
    ):
        raise ValueError("invalid bounded E0 same-process G5 AB settings")
    router = _synthetic_router(noise_routes)
    index = NativeSchemaGraphIndex.build(
        NativeSchemaPostingIndex.build(router.registry),
    )
    # Turn OFF the prefilter *only* by allowing the entire original
    # posting universe through its existing check. All original native
    # fingerprint, auth, data-scope and canonical compatibility remain.
    off = replace(
        index,
        edge_consumer_routes=frozenset(index.field_index.route_locations),
    )
    if (
        off.graph is not index.graph
        or off.field_index is not index.field_index
        or index.edge_consumer_routes != frozenset({"case_service.read"})
    ):
        raise ValueError("synthetic G5 AB structural input drift")
    conditions = {
        "canonical_prefilter_enabled": index,
        "canonical_prefilter_disabled_superset": off,
    }
    for current in conditions.values():
        result = current.lookup(
            router, BROAD_QUERY, group=BROAD_GROUP, principal=PRINCIPAL,
        )
        if result.status != "no_proven_hit" or result.candidates:
            raise ValueError("paired G5 no-path answer mismatch")

    timings: dict[str, list[float]] = {key: [] for key in conditions}
    for i in range(iterations + 2):
        # Alternate order to limit systematic cache/order bias. First two
        # full AB cycles are warm-up and EXCLUDED from returned timing data.
        keys = (
            tuple(conditions)
            if i % 2 == 0 else tuple(reversed(tuple(conditions)))
        )
        for name in keys:
            start = time.perf_counter_ns()
            row = conditions[name].lookup(
                router, BROAD_QUERY, group=BROAD_GROUP, principal=PRINCIPAL,
            )
            elapsed = (time.perf_counter_ns() - start) / 1_000_000
            if row.status != "no_proven_hit" or row.candidates:
                raise ValueError("paired G5 returned inconsistent candidate evidence")
            if i >= 2:
                timings[name].append(elapsed)

    return {
        "evidence_tier": EVIDENCE,
        "independent_e2_qualified": False,
        "registered_source_routes": index.field_index.indexed_route_count,
        "broad_semantic_postings": len(
            index.field_index.postings.get("research.label", ()),
        ),
        "canonical_graph_edge_count": len(index.graph.edges),
        "warmup_ab_cycles": 2,
        "measured_ab_cycles": iterations,
        "same_original_source_and_graph": True,
        "method": "same production G5 lookup, structural candidate prefilter toggled",
        "query_wall_ms": {
            name: {
                "p50": round(_percentile(xs, 50), 4),
                "p95": round(_percentile(xs, 95), 4),
                "p99": round(_percentile(xs, 99), 4),
            }
            for name, xs in timings.items()
        },
        "python": platform.python_version(),
        "platform": platform.platform(),
        "limitations": [
            "Deliberately constructed common output postings with zero typed graph paths",
            "Same-process E0 local AB, not independent workload/agent/provider",
            "Small sample p99 is the maximum and not a service latency SLO",
            "This toggle is a benchmark-only structural superset, not a product API",
            "No semantic NLP, complete Top-K ranker or comparative task-success evidence",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--noise-routes", type=int, default=5100)
    parser.add_argument("--iterations", type=int, default=5)
    args = parser.parse_args()
    print(json.dumps(benchmark_ab(
        noise_routes=args.noise_routes, iterations=args.iterations,
    ), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    if sys.platform != "linux":
        raise SystemExit("Linux-only G5 structural AB profile")
    main()
