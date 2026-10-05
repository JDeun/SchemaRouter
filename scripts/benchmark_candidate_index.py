from __future__ import annotations

import argparse
import statistics
import time
import tracemalloc
from dataclasses import dataclass

from schemarouter import (
    EndpointSpec,
    FieldSpec,
    InMemoryRegistry,
    PlanRequest,
    QueryIntent,
    SchemaPlanner,
    ToolSpec,
)


@dataclass(frozen=True)
class Sample:
    mode: str
    durations_ms: list[float]
    score_calls: list[int]
    index_build_ms: float
    index_peak_kib: float

    def summary(self) -> dict[str, float | int | str]:
        return {
            "mode": self.mode,
            "iterations": len(self.durations_ms),
            "index_build_ms": self.index_build_ms,
            "index_peak_kib": self.index_peak_kib,
            "mean_ms": statistics.fmean(self.durations_ms),
            "median_ms": statistics.median(self.durations_ms),
            "min_ms": min(self.durations_ms),
            "max_ms": max(self.durations_ms),
            "mean_score_calls": statistics.fmean(self.score_calls),
        }


class CountingPlanner(SchemaPlanner):
    def __init__(self, *args, **kwargs) -> None:
        self.score_calls = 0
        super().__init__(*args, **kwargs)

    def _score_endpoint(self, *args, **kwargs):
        self.score_calls += 1
        return super()._score_endpoint(*args, **kwargs)


class StaticAnalyzer:
    def analyze(
        self,
        request: PlanRequest,
        registry: InMemoryRegistry,
    ) -> QueryIntent:
        del request, registry
        return QueryIntent(concepts=["conductivity"])


def make_registry(size: int) -> InMemoryRegistry:
    registry = InMemoryRegistry()
    registry.update_many(
        [
            ToolSpec(
                name=f"tool_{index}",
                description=f"synthetic tool number {index}",
                endpoints=[
                    EndpointSpec(
                        name="search",
                        description=f"synthetic endpoint number {index}",
                        output_fields=[
                            FieldSpec(
                                name=(
                                    "thermal_conductivity"
                                    if index == size - 1
                                    else f"metric_{index}_value"
                                ),
                            )
                        ],
                        read_only=True,
                    )
                ],
            )
            for index in range(size)
        ]
    )
    return registry


def run(
    registry: InMemoryRegistry,
    *,
    indexed: bool,
    iterations: int,
) -> Sample:
    planner = CountingPlanner(
        registry,
        analyzer=StaticAnalyzer(),
        candidate_index=indexed,
    )

    index_build_ms = 0.0
    index_peak_kib = 0.0
    if indexed:
        tracemalloc.start()
        started = time.perf_counter()
        planner._index()
        index_build_ms = (time.perf_counter() - started) * 1000
        _, peak_bytes = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        index_peak_kib = peak_bytes / 1024

    # Warm the scoring path independently from index construction.
    planner.plan("unrelated")
    planner.score_calls = 0

    durations: list[float] = []
    score_calls: list[int] = []

    for _ in range(iterations):
        before_calls = planner.score_calls
        started = time.perf_counter()
        plan = planner.plan("unrelated")
        elapsed_ms = (time.perf_counter() - started) * 1000
        if not plan.calls:
            raise RuntimeError("benchmark concept unexpectedly produced no calls")
        durations.append(elapsed_ms)
        score_calls.append(planner.score_calls - before_calls)

    return Sample(
        mode="indexed" if indexed else "exhaustive",
        durations_ms=durations,
        score_calls=score_calls,
        index_build_ms=index_build_ms,
        index_peak_kib=index_peak_kib,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Compare indexed semantic-substring candidate recall with exhaustive "
            "endpoint scoring while reporting index construction cost."
        )
    )
    parser.add_argument("--tools", type=int, default=1000)
    parser.add_argument("--iterations", type=int, default=50)
    args = parser.parse_args()

    if args.tools < 1:
        raise ValueError("--tools must be >= 1")
    if args.iterations < 1:
        raise ValueError("--iterations must be >= 1")

    registry = make_registry(args.tools)
    indexed = run(registry, indexed=True, iterations=args.iterations)
    exhaustive = run(registry, indexed=False, iterations=args.iterations)

    print(indexed.summary())
    print(exhaustive.summary())


if __name__ == "__main__":
    main()
