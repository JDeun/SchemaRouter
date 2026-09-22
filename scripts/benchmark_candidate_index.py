from __future__ import annotations

import argparse
import statistics
import time
from dataclasses import dataclass

from schemarouter import EndpointSpec, FieldSpec, InMemoryRegistry, SchemaPlanner, ToolSpec


@dataclass(frozen=True)
class Sample:
    mode: str
    durations_ms: list[float]
    score_calls: list[int]

    def summary(self) -> dict[str, float | int | str]:
        return {
            "mode": self.mode,
            "iterations": len(self.durations_ms),
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
                                name=f"value_{index}",
                                aliases=["benchmark-needle"] if index == size - 1 else [],
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
    planner = CountingPlanner(registry, candidate_index=indexed)

    planner.plan("benchmark-needle")
    planner.score_calls = 0

    durations: list[float] = []
    score_calls: list[int] = []

    for _ in range(iterations):
        before_calls = planner.score_calls
        started = time.perf_counter()
        plan = planner.plan("benchmark-needle")
        elapsed_ms = (time.perf_counter() - started) * 1000
        if not plan.calls:
            raise RuntimeError("benchmark query unexpectedly produced no calls")
        durations.append(elapsed_ms)
        score_calls.append(planner.score_calls - before_calls)

    return Sample(
        mode="indexed" if indexed else "exhaustive",
        durations_ms=durations,
        score_calls=score_calls,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare exact-recall candidate indexing with exhaustive endpoint scoring."
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
