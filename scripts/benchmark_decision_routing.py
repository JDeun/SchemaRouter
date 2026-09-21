"""Benchmark bounded decision routing against deterministic/model-assisted baselines."""

from __future__ import annotations

import argparse
import asyncio
import importlib
import inspect
import json
import os
import time
from dataclasses import asdict, dataclass
from typing import Any

from schemarouter import (
    DecisionPolicy,
    EndpointSpec,
    FieldSpec,
    InMemoryRegistry,
    PlanRequest,
    SchemaPlanner,
    ToolSpec,
)
from schemarouter.analyzers import ModelQueryAnalyzer
from schemarouter.integrations import JevDecisionBackend


@dataclass(frozen=True)
class BenchmarkCase:
    query: str
    expected: str


@dataclass
class BenchmarkRow:
    backend: str
    query: str
    expected: str
    predicted: str | None
    correct: bool
    latency_ms: float
    abstained: bool = False
    input_tokens: int | None = None
    output_tokens: int | None = None
    estimated_cost: float | None = None
    error: str | None = None


REFERENCE_CASES = [
    BenchmarkCase("current temperature in Seoul", "weather.current"),
    BenchmarkCase("find the band gap for silicon", "materials.search"),
    BenchmarkCase("search papers about retrieval augmented generation", "papers.search"),
]


def reference_registry() -> InMemoryRegistry:
    registry = InMemoryRegistry()
    registry.register(
        ToolSpec(
            name="weather",
            description="Current weather observations",
            endpoints=[
                EndpointSpec(
                    name="current",
                    description="Get current city temperature",
                    output_fields=[
                        FieldSpec(name="city", identifier=True),
                        FieldSpec(name="temperature"),
                    ],
                )
            ],
        )
    )
    registry.register(
        ToolSpec(
            name="materials",
            description="Materials property database",
            endpoints=[
                EndpointSpec(
                    name="search",
                    description="Search material band gap and structure properties",
                    output_fields=[
                        FieldSpec(name="material_id", identifier=True),
                        FieldSpec(name="band_gap"),
                    ],
                )
            ],
        )
    )
    registry.register(
        ToolSpec(
            name="papers",
            description="Scientific literature search",
            endpoints=[
                EndpointSpec(
                    name="search",
                    description="Search research papers and article metadata",
                    output_fields=[
                        FieldSpec(name="doi", identifier=True),
                        FieldSpec(name="title"),
                    ],
                )
            ],
        )
    )
    return registry


class RecordingDecisionBackend:
    def __init__(self, backend: Any) -> None:
        self.backend = backend
        self.last_result: Any | None = None

    def decide(self, request: Any) -> Any:
        value = self.backend.decide(request)
        if inspect.isawaitable(value):
            async def resolve() -> Any:
                result = await value
                self.last_result = result
                return result

            return resolve()
        self.last_result = value
        return value


def load_callable(spec: str) -> Any:
    module_name, separator, attr = spec.partition(":")
    if not separator or not module_name or not attr:
        raise ValueError("--model-callable must use module:function syntax")
    module = importlib.import_module(module_name)
    value = getattr(module, attr)
    if not callable(value):
        raise TypeError(f"{spec} is not callable")
    return value


def estimate_cost(
    input_tokens: int | None,
    output_tokens: int | None,
    input_cost_per_million: float | None,
    output_cost_per_million: float | None,
) -> float | None:
    if input_cost_per_million is None and output_cost_per_million is None:
        return None
    return (
        (input_tokens or 0) * (input_cost_per_million or 0.0)
        + (output_tokens or 0) * (output_cost_per_million or 0.0)
    ) / 1_000_000


async def benchmark_planner(
    name: str,
    planner: SchemaPlanner,
    cases: list[BenchmarkCase],
    *,
    recorder: RecordingDecisionBackend | None = None,
    input_cost_per_million: float | None = None,
    output_cost_per_million: float | None = None,
) -> list[BenchmarkRow]:
    rows: list[BenchmarkRow] = []
    for case in cases:
        if recorder is not None:
            recorder.last_result = None

        started = time.perf_counter()
        try:
            plan = await planner.aplan(PlanRequest(query=case.query, max_calls=1))
            latency_ms = (time.perf_counter() - started) * 1000
            predicted = (
                f"{plan.calls[0].tool}.{plan.calls[0].endpoint}"
                if plan.calls
                else None
            )

            result = recorder.last_result if recorder is not None else None
            metadata = getattr(result, "metadata", {}) if result is not None else {}
            input_tokens = metadata.get("input_tokens")
            output_tokens = metadata.get("output_tokens")
            abstained = bool(getattr(result, "abstained", False))

            rows.append(
                BenchmarkRow(
                    backend=name,
                    query=case.query,
                    expected=case.expected,
                    predicted=predicted,
                    correct=predicted == case.expected,
                    latency_ms=round(latency_ms, 3),
                    abstained=abstained,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    estimated_cost=estimate_cost(
                        input_tokens,
                        output_tokens,
                        input_cost_per_million,
                        output_cost_per_million,
                    ),
                )
            )
        except Exception as exc:  # noqa: BLE001 - benchmark records provider failures.
            latency_ms = (time.perf_counter() - started) * 1000
            rows.append(
                BenchmarkRow(
                    backend=name,
                    query=case.query,
                    expected=case.expected,
                    predicted=None,
                    correct=False,
                    latency_ms=round(latency_ms, 3),
                    error=f"{type(exc).__name__}: {exc}",
                )
            )
    return rows


def summarize(rows: list[BenchmarkRow]) -> dict[str, Any]:
    total = len(rows)
    successful = [row for row in rows if row.error is None]
    return {
        "cases": total,
        "accuracy": (
            sum(row.correct for row in rows) / total
            if total
            else 0.0
        ),
        "errors": sum(row.error is not None for row in rows),
        "abstentions": sum(row.abstained for row in rows),
        "mean_latency_ms": (
            round(sum(row.latency_ms for row in successful) / len(successful), 3)
            if successful
            else None
        ),
        "input_tokens": sum(row.input_tokens or 0 for row in rows),
        "output_tokens": sum(row.output_tokens or 0 for row in rows),
        "estimated_cost": (
            sum(row.estimated_cost or 0.0 for row in rows)
            if any(row.estimated_cost is not None for row in rows)
            else None
        ),
    }


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--model-callable",
        help="Optional ModelQueryAnalyzer callable in module:function form.",
    )
    parser.add_argument(
        "--jev",
        action="store_true",
        help="Run the Jev backend. Requires TYPESAFE_API_KEY.",
    )
    parser.add_argument("--jev-model", default=None)
    parser.add_argument("--min-confidence", type=float, default=0.0)
    parser.add_argument("--input-cost-per-million", type=float, default=None)
    parser.add_argument("--output-cost-per-million", type=float, default=None)
    args = parser.parse_args()

    registry = reference_registry()
    planners: list[tuple[str, SchemaPlanner, RecordingDecisionBackend | None]] = [
        ("keyword", SchemaPlanner(registry), None)
    ]

    if args.model_callable:
        model_callable = load_callable(args.model_callable)
        planners.append(
            (
                "model-query-analyzer",
                SchemaPlanner(registry, analyzer=ModelQueryAnalyzer(model_callable)),
                None,
            )
        )

    if args.jev:
        if not os.environ.get("TYPESAFE_API_KEY"):
            raise RuntimeError("--jev requires TYPESAFE_API_KEY")
        recorder = RecordingDecisionBackend(
            JevDecisionBackend(
                model=args.jev_model,
                min_confidence=args.min_confidence,
            )
        )
        planners.append(
            (
                "jev",
                SchemaPlanner(
                    registry,
                    decision_backend=recorder,
                    decision_policy=DecisionPolicy(
                        enabled=True,
                        endpoint_selection=True,
                        fallback="deterministic",
                    ),
                ),
                recorder,
            )
        )

    report: dict[str, Any] = {"rows": [], "summary": {}}
    for name, planner, recorder in planners:
        rows = await benchmark_planner(
            name,
            planner,
            REFERENCE_CASES,
            recorder=recorder,
            input_cost_per_million=args.input_cost_per_million,
            output_cost_per_million=args.output_cost_per_million,
        )
        report["rows"].extend(asdict(row) for row in rows)
        report["summary"][name] = summarize(rows)

    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
