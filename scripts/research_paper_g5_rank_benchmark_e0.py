"""Synthetic E0 comparator benchmark for Algorithm 1 owner-pinned G5 Rank.

No source provider, LLM or tool is called; the input tuples model already
authorized and source-verified complete paths. This is not end-to-end latency,
an executor quality assessment, an independent publisher gold set, or E2.
"""
from __future__ import annotations

import argparse
import json
import statistics
import time
from pathlib import Path
from typing import Any, cast

from schemarouter.native_graph_index import (
    NativeIndexedGraphCandidate,
    NativeIndexedTwoHopCandidate,
)
from schemarouter.paper_native_rank import (
    PaperNativeRankPolicy,
    rank_authorized_paper_graph_one_hop,
    rank_authorized_paper_graph_two_hop,
)


def _fixture(
    n: int, hops: int,
) -> tuple[
    tuple[NativeIndexedGraphCandidate, ...] |
    tuple[NativeIndexedTwoHopCandidate, ...],
    PaperNativeRankPolicy,
]:
    winner = f"target_{n - 1:05d}.read"
    policy = PaperNativeRankPolicy(
        snapshot_id="a" * 64,
        route_priorities={winner: 100},
    )
    if hops == 1:
        paths = tuple(NativeIndexedGraphCandidate(
            producer_route_id=f"root_{i:05d}.read",
            consumer_route_id=f"target_{i:05d}.read",
            producer_tool_fingerprint="t",
            producer_endpoint_fingerprint="e",
            consumer_tool_fingerprint="t",
            consumer_endpoint_fingerprint="e",
            producer_identifier_field="case_id",
            consumer_required_parameter="case_id",
            consumer_output_fields=("case status",),
            parameter_bindings=(("case_id", "case_id"),),
        ) for i in range(n))
        return paths, policy
    paths2 = tuple(NativeIndexedTwoHopCandidate(
        route_ids=(
            f"root_{i:05d}.read",
            f"middle_{i:05d}.read",
            f"target_{i:05d}.read",
        ),
        route_fingerprints=(("t", "e"), ("t", "e"), ("t", "e")),
        root_to_intermediate=(("contact_id", "contact_id"),),
        intermediate_to_target=(("case_id", "case_id"),),
        target_output_fields=("case status",),
        source_root_parameters=(),
    ) for i in range(n))
    return paths2, policy


def _percentile_ms(values: list[float], p: float) -> float:
    ordered = sorted(values)
    return round(ordered[min(len(ordered) - 1, int(p * len(ordered) + 0.999999) - 1)] * 1_000, 4)


def benchmark(*, n: int, hops: int, samples: int = 7) -> dict[str, Any]:
    if n not in (500, 5000) or hops not in (1, 2) or not 1 <= samples <= 30:
        raise ValueError("bounded E0 G5 benchmark requires 500/5000 paths, 1/2 hops")
    candidates, policy = _fixture(n, hops)
    aliases = (("case status",),)
    winner = f"target_{n - 1:05d}.read"
    expected = (winner,) + tuple(f"target_{i:05d}.read" for i in range(4))
    wall_times: list[float] = []
    cpu_times: list[float] = []
    output: tuple[str, ...] = ()
    for _ in range(samples):
        t0, c0 = time.perf_counter(), time.process_time()
        if hops == 1:
            one_hop = cast(tuple[NativeIndexedGraphCandidate, ...], candidates)
            selected = rank_authorized_paper_graph_one_hop(
                one_hop, concept_aliases=aliases, policy=policy,
            )
            output = tuple(one_hop[i].consumer_route_id for i in selected)
        else:
            two_hop = cast(tuple[NativeIndexedTwoHopCandidate, ...], candidates)
            selected = rank_authorized_paper_graph_two_hop(
                two_hop, concept_aliases=aliases, policy=policy,
            )
            output = tuple(two_hop[i].route_ids[-1] for i in selected)
        wall_times.append(time.perf_counter() - t0)
        cpu_times.append(time.process_time() - c0)
        # Independent fixed fixture oracle: every concept match and field
        # count is identical, all routes are non-web, so the owner priority
        # wins first and the remaining exact routes order lexically.
        if output != expected:
            raise AssertionError("G5 Rank disagreed with independent fixture oracle")
    receipt = json.dumps({"selected_target_routes": output}, separators=(",", ":"))
    return {
        "tier": "E0-synthetic-comparator-only",
        "registered_path_receipts": n,
        "hops": hops,
        "samples": samples,
        "oracle_exact_top_k5": True,
        "wall_ms": {
            "p50": round(statistics.median(wall_times) * 1_000, 4),
            "p95": _percentile_ms(wall_times, 0.95),
            "p99": _percentile_ms(wall_times, 0.99),
        },
        "cpu_ms": {
            "p50": round(statistics.median(cpu_times) * 1_000, 4),
            "p95": _percentile_ms(cpu_times, 0.95),
            "p99": _percentile_ms(cpu_times, 0.99),
        },
        "receipt_bytes": len(receipt.encode("utf-8")),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=int, default=7)
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()
    result = {
        "methodology": "E0 synthetic already-qualified comparator; no providers or E2",
        "measurements": [
            benchmark(n=n, hops=hops, samples=args.samples)
            for hops in (1, 2) for n in (500, 5000)
        ],
    }
    rendered = json.dumps(result, sort_keys=True, indent=2)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
