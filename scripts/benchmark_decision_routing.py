"""Benchmark schema routing across deterministic and optional decision backends."""

from __future__ import annotations

import argparse
import asyncio
import csv
import importlib
import inspect
import json
import os
import statistics
import time
from dataclasses import asdict, dataclass
from pathlib import Path
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
    id: str
    query: str
    expected: str | None
    category: str = "smoke"
    expect_abstain: bool = False


@dataclass
class BenchmarkRow:
    backend: str
    case_id: str
    category: str
    query: str
    expected: str | None
    predicted: str | None
    correct: bool
    invalid_plan: bool
    latency_ms: float
    abstained: bool = False
    fallback_used: bool = False
    input_tokens: int | None = None
    output_tokens: int | None = None
    estimated_cost: float | None = None
    error: str | None = None


SMOKE_CASES = [
    BenchmarkCase("smoke-weather", "current temperature in Seoul", "weather.current"),
    BenchmarkCase("smoke-material", "find the band gap for silicon", "materials.search"),
    BenchmarkCase(
        "smoke-paper",
        "search papers about retrieval augmented generation",
        "papers.search",
    ),
]


def _endpoint(name: str, description: str, *fields: str, read_only: bool = True) -> EndpointSpec:
    return EndpointSpec(
        name=name,
        description=description,
        read_only=read_only,
        output_fields=[
            FieldSpec(name=field, identifier=field in {"id", "doi", "symbol", "sku"})
            for field in fields
        ],
    )


def reference_registry() -> InMemoryRegistry:
    """Return a stable catalog shared by smoke and checked-in benchmark corpora."""
    registry = InMemoryRegistry()
    registry.register(
        ToolSpec(
            name="weather",
            description="Weather observations and forecasts for cities",
            endpoints=[
                _endpoint(
                    "current",
                    "Get current city temperature and conditions",
                    "city",
                    "temperature",
                ),
                _endpoint("forecast", "Get future weather forecast for a city", "city", "forecast"),
            ],
        )
    )
    registry.register(
        ToolSpec(
            name="materials",
            description="Materials property and crystal structure database",
            endpoints=[
                _endpoint(
                    "search",
                    "Search materials by properties such as band gap",
                    "material_id",
                    "band_gap",
                ),
                _endpoint(
                    "structure",
                    "Retrieve crystal structure and lattice information",
                    "material_id",
                    "structure",
                ),
            ],
        )
    )
    registry.register(
        ToolSpec(
            name="papers",
            description="Scientific literature and citation database",
            endpoints=[
                _endpoint("search", "Search research papers and article metadata", "doi", "title"),
                _endpoint(
                    "citations",
                    "Find papers that cite a DOI or article",
                    "doi",
                    "citations",
                ),
            ],
        )
    )
    registry.register(
        ToolSpec(
            name="finance",
            description="Market quotes and historical price data",
            endpoints=[
                _endpoint("quote", "Get the latest market quote for a ticker", "symbol", "price"),
                _endpoint(
                    "history",
                    "Get historical prices for a ticker and date range",
                    "symbol",
                    "history",
                ),
            ],
        )
    )
    registry.register(
        ToolSpec(
            name="calendar",
            description="Calendar event listing and creation",
            endpoints=[
                _endpoint("list", "List scheduled calendar events", "id", "title"),
                _endpoint("create", "Create a new calendar event", "id", "title", read_only=False),
            ],
        )
    )
    registry.register(
        ToolSpec(
            name="support",
            description="Customer support knowledge and ticket operations",
            endpoints=[
                _endpoint("search", "Search support knowledge base articles", "id", "title"),
                _endpoint(
                    "create_ticket",
                    "Create a customer support ticket",
                    "id",
                    "status",
                    read_only=False,
                ),
            ],
        )
    )
    registry.register(
        ToolSpec(
            name="inventory",
            description="Inventory lookup and stock update operations",
            endpoints=[
                _endpoint("search", "Search inventory and stock by SKU", "sku", "quantity"),
                _endpoint(
                    "update",
                    "Update inventory quantity for a SKU",
                    "sku",
                    "quantity",
                    read_only=False,
                ),
            ],
        )
    )
    registry.register(
        ToolSpec(
            name="users",
            description="User directory lookup and profile update operations",
            endpoints=[
                _endpoint("lookup", "Look up a user profile or account", "id", "name"),
                _endpoint("update", "Update a user profile", "id", "name", read_only=False),
            ],
        )
    )
    return registry


def load_corpus(path: str | os.PathLike[str], *, allowed_routes: set[str]) -> list[BenchmarkCase]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, list) or not value:
        raise ValueError("benchmark corpus must be a non-empty JSON array")

    cases: list[BenchmarkCase] = []
    seen_ids: set[str] = set()
    for index, raw in enumerate(value):
        if not isinstance(raw, dict):
            raise ValueError(f"corpus item {index} must be an object")
        case = BenchmarkCase(
            id=str(raw.get("id", "")).strip(),
            query=str(raw.get("query", "")).strip(),
            expected=raw.get("expected"),
            category=str(raw.get("category", "uncategorized")).strip() or "uncategorized",
            expect_abstain=bool(raw.get("expect_abstain", False)),
        )
        if not case.id or case.id in seen_ids:
            raise ValueError(f"corpus item {index} has a missing or duplicate id")
        if not case.query:
            raise ValueError(f"corpus item {case.id!r} has an empty query")
        if case.expect_abstain:
            if case.expected is not None:
                raise ValueError(f"abstention case {case.id!r} must use expected=null")
        elif not isinstance(case.expected, str) or case.expected not in allowed_routes:
            raise ValueError(f"case {case.id!r} references unknown route {case.expected!r}")
        seen_ids.add(case.id)
        cases.append(case)
    return cases


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


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = (len(ordered) - 1) * percentile
    lower = int(index)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = index - lower
    return round(ordered[lower] * (1 - fraction) + ordered[upper] * fraction, 3)


async def benchmark_planner(
    name: str,
    planner: SchemaPlanner,
    cases: list[BenchmarkCase],
    *,
    allowed_routes: set[str],
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
            invalid_plan = predicted is not None and predicted not in allowed_routes
            correct = (
                predicted is None
                if case.expect_abstain
                else predicted == case.expected
            )

            rows.append(
                BenchmarkRow(
                    backend=name,
                    case_id=case.id,
                    category=case.category,
                    query=case.query,
                    expected=case.expected,
                    predicted=predicted,
                    correct=correct and not invalid_plan,
                    invalid_plan=invalid_plan,
                    latency_ms=round(latency_ms, 3),
                    abstained=abstained,
                    fallback_used=abstained and predicted is not None,
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
                    case_id=case.id,
                    category=case.category,
                    query=case.query,
                    expected=case.expected,
                    predicted=None,
                    correct=False,
                    invalid_plan=False,
                    latency_ms=round(latency_ms, 3),
                    error=f"{type(exc).__name__}: {exc}",
                )
            )
    return rows


def summarize(rows: list[BenchmarkRow]) -> dict[str, Any]:
    total = len(rows)
    successful = [row for row in rows if row.error is None]
    latencies = [row.latency_ms for row in successful]
    categories = sorted({row.category for row in rows})
    expected_abstentions = [row for row in rows if row.expected is None]
    return {
        "cases": total,
        "accuracy": sum(row.correct for row in rows) / total if total else 0.0,
        "invalid_plan_rate": (
            sum(row.invalid_plan for row in rows) / total if total else 0.0
        ),
        "errors": sum(row.error is not None for row in rows),
        "abstentions": sum(row.abstained for row in rows),
        "abstention_rate": sum(row.abstained for row in rows) / total if total else 0.0,
        "expected_abstention_recall": (
            sum(row.abstained for row in expected_abstentions) / len(expected_abstentions)
            if expected_abstentions
            else None
        ),
        "fallbacks": sum(row.fallback_used for row in rows),
        "mean_latency_ms": (
            round(statistics.fmean(latencies), 3) if latencies else None
        ),
        "p50_latency_ms": _percentile(latencies, 0.50),
        "p95_latency_ms": _percentile(latencies, 0.95),
        "category_accuracy": {
            category: (
                sum(row.correct for row in rows if row.category == category)
                / sum(row.category == category for row in rows)
            )
            for category in categories
        },
        "input_tokens": sum(row.input_tokens or 0 for row in rows),
        "output_tokens": sum(row.output_tokens or 0 for row in rows),
        "estimated_cost": (
            sum(row.estimated_cost or 0.0 for row in rows)
            if any(row.estimated_cost is not None for row in rows)
            else None
        ),
    }


def _write_csv(path: str | os.PathLike[str], rows: list[BenchmarkRow]) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(asdict(rows[0]).keys()) if rows else [])
        if rows:
            writer.writeheader()
            writer.writerows(asdict(row) for row in rows)


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", help="JSON corpus path. Omit for the three-case smoke set.")
    parser.add_argument("--max-cases", type=int, default=None)
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--json-out", default=None)
    parser.add_argument("--csv-out", default=None)
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

    if args.repeat < 1:
        raise ValueError("--repeat must be >= 1")
    if args.max_cases is not None and args.max_cases < 1:
        raise ValueError("--max-cases must be >= 1")

    registry = reference_registry()
    allowed_routes = {
        f"{tool.key}.{endpoint.name}"
        for tool in registry.tools()
        for endpoint in tool.endpoints
    }
    cases = (
        load_corpus(args.corpus, allowed_routes=allowed_routes)
        if args.corpus
        else list(SMOKE_CASES)
    )
    if args.max_cases is not None:
        cases = cases[: args.max_cases]
    if args.repeat > 1:
        cases = [
            BenchmarkCase(
                id=f"{case.id}#run-{iteration + 1}",
                query=case.query,
                expected=case.expected,
                category=case.category,
                expect_abstain=case.expect_abstain,
            )
            for iteration in range(args.repeat)
            for case in cases
        ]

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

    report: dict[str, Any] = {
        "corpus": args.corpus or "smoke",
        "case_count": len(cases),
        "allowed_routes": sorted(allowed_routes),
        "rows": [],
        "summary": {},
    }
    all_rows: list[BenchmarkRow] = []
    for name, planner, recorder in planners:
        rows = await benchmark_planner(
            name,
            planner,
            cases,
            allowed_routes=allowed_routes,
            recorder=recorder,
            input_cost_per_million=args.input_cost_per_million,
            output_cost_per_million=args.output_cost_per_million,
        )
        all_rows.extend(rows)
        report["rows"].extend(asdict(row) for row in rows)
        report["summary"][name] = summarize(rows)

    output = json.dumps(report, indent=2, ensure_ascii=False)
    if args.json_out:
        destination = Path(args.json_out)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(output + "\n", encoding="utf-8")
    if args.csv_out:
        _write_csv(args.csv_out, all_rows)
    print(output)


if __name__ == "__main__":
    asyncio.run(main())
