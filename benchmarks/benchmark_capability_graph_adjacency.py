from __future__ import annotations

import argparse
import time

from schemarouter import (
    CapabilityComposition,
    CapabilityDependencyEdge,
    CapabilityDependencyGraph,
)


def build_graph(size: int, fanout: int) -> CapabilityDependencyGraph:
    ids = tuple(f"node-{index:06d}" for index in range(size))
    compatibility = CapabilityComposition(status="compatible")
    edges = [
        CapabilityDependencyEdge(
            producer_id=ids[index],
            consumer_id=ids[(index + offset) % size],
            compatibility=compatibility,
        )
        for index in range(size)
        for offset in range(1, fanout + 1)
    ]
    return CapabilityDependencyGraph(capability_ids=ids, edges=edges)


def reference_successors(
    graph: CapabilityDependencyGraph,
    capability_id: str,
) -> tuple[str, ...]:
    return tuple(
        edge.consumer_id
        for edge in graph.edges
        if edge.producer_id == capability_id
    )


def benchmark(size: int, fanout: int, lookups: int) -> None:
    graph = build_graph(size, fanout)
    ids = graph.capability_ids

    started = time.perf_counter()
    for index in range(lookups):
        graph.successors(ids[index % size])
    indexed_seconds = time.perf_counter() - started

    started = time.perf_counter()
    for index in range(lookups):
        reference_successors(graph, ids[index % size])
    scan_seconds = time.perf_counter() - started

    speedup = scan_seconds / indexed_seconds if indexed_seconds else float("inf")
    print(
        f"V={size} E={len(graph.edges)} lookups={lookups} "
        f"indexed={indexed_seconds:.6f}s scan={scan_seconds:.6f}s "
        f"speedup={speedup:.2f}x"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare indexed capability adjacency against full edge scans."
    )
    parser.add_argument("--size", type=int, default=5_000)
    parser.add_argument("--fanout", type=int, default=4)
    parser.add_argument("--lookups", type=int, default=20_000)
    args = parser.parse_args()
    if args.size < 2:
        raise ValueError("--size must be >= 2")
    if args.fanout < 1 or args.fanout >= args.size:
        raise ValueError("--fanout must satisfy 1 <= fanout < size")
    if args.lookups < 1:
        raise ValueError("--lookups must be >= 1")
    benchmark(args.size, args.fanout, args.lookups)


if __name__ == "__main__":
    main()
