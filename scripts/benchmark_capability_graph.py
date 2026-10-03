from __future__ import annotations

import argparse
import json
import time
import tracemalloc
from dataclasses import asdict, dataclass
from pathlib import Path

from schemarouter import (
    CapabilityContract,
    CapabilityFieldContract,
    build_capability_dependency_graph,
    update_capability_dependency_graph,
)


@dataclass(frozen=True)
class Measurement:
    mode: str
    capabilities: int
    edges: int | None
    build_seconds: float | None
    update_seconds: float | None
    peak_bytes: int | None
    skipped: str | None = None


def _field(semantic_id: str) -> CapabilityFieldContract:
    return CapabilityFieldContract(
        semantic_id=semantic_id,
        json_schema={"type": "string"},
    )


def sparse_contracts(size: int) -> list[CapabilityContract]:
    contracts: list[CapabilityContract] = []
    for index in range(size):
        requires = [] if index == 0 else [_field(f"state.{index - 1}")]
        contracts.append(
            CapabilityContract(
                capability_id=f"cap-{index:06d}",
                requires=requires,
                produces=[_field(f"state.{index}")],
            )
        )
    return contracts


def dense_contracts(size: int) -> list[CapabilityContract]:
    return [
        CapabilityContract(
            capability_id=f"dense-{index:06d}",
            requires=[_field("shared")],
            produces=[_field("shared")],
        )
        for index in range(size)
    ]


def mutate_one(
    contracts: list[CapabilityContract],
) -> list[CapabilityContract]:
    updated = [item.model_copy(deep=True) for item in contracts]
    if not updated:
        return updated
    index = len(updated) // 2
    item = updated[index]
    updated[index] = CapabilityContract(
        capability_id=item.capability_id,
        requires=list(item.requires),
        produces=[*item.produces, _field("incremental.extra")],
        effects=item.effects,
        preconditions=list(item.preconditions),
    )
    return updated


def measure(mode: str, size: int) -> Measurement:
    factory = sparse_contracts if mode == "sparse" else dense_contracts
    contracts = factory(size)

    tracemalloc.start()
    started = time.perf_counter()
    graph = build_capability_dependency_graph(contracts)
    build_seconds = time.perf_counter() - started
    _, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    updated = mutate_one(contracts)
    update_started = time.perf_counter()
    incremental = update_capability_dependency_graph(
        graph,
        contracts,
        updated,
    )
    update_seconds = time.perf_counter() - update_started

    rebuilt = build_capability_dependency_graph(updated)
    if incremental != rebuilt:
        raise RuntimeError("incremental graph differs from full rebuild")

    return Measurement(
        mode=mode,
        capabilities=size,
        edges=len(graph.edges),
        build_seconds=round(build_seconds, 6),
        update_seconds=round(update_seconds, 6),
        peak_bytes=peak_bytes,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Benchmark indexed capability dependency graph construction."
    )
    parser.add_argument(
        "--sizes",
        default="1000,10000,50000",
        help="Comma-delimited sparse registry sizes.",
    )
    parser.add_argument(
        "--dense-limit",
        type=int,
        default=2000,
        help=(
            "Run dense all-compatible cases only at or below this size. "
            "Dense 50k graphs are intentionally skipped because the edge set itself is O(N^2)."
        ),
    )
    parser.add_argument("--json-out", default=None)
    args = parser.parse_args()

    sizes = [
        int(value)
        for value in args.sizes.split(",")
        if value.strip()
    ]
    if any(size < 1 for size in sizes):
        raise SystemExit("all sizes must be positive")

    results: list[Measurement] = []
    for size in sizes:
        results.append(measure("sparse", size))
        if size <= args.dense_limit:
            results.append(measure("dense", size))
        else:
            results.append(
                Measurement(
                    mode="dense",
                    capabilities=size,
                    edges=None,
                    build_seconds=None,
                    update_seconds=None,
                    peak_bytes=None,
                    skipped=(
                        "edge cardinality is quadratic; raise --dense-limit explicitly "
                        "for a deliberate stress run"
                    ),
                )
            )

    payload = {
        "benchmark": "capability_dependency_graph",
        "results": [asdict(item) for item in results],
    }
    rendered = json.dumps(payload, indent=2, sort_keys=True)
    if args.json_out:
        path = Path(args.json_out)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
