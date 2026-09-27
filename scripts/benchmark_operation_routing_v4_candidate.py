from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import statistics
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from schemarouter import (  # noqa: E402
    EmbeddingDecisionBackend,
    PairwiseDecisionBackend,
    SchemaPlanner,
)

from scripts.benchmark_decision_routing import (  # noqa: E402
    BenchmarkRow,
    RecordingDecisionBackend,
    _corpus_sha256,
    load_callable,
    load_corpus,
    reference_registry,
    summarize,
    benchmark_planner,
)


BASELINE_NAME = (
    "v4-baseline:"
    "semantic-recall2+capability-fit025+primary-tool-bge001+endpoint-disambiguation003"
)
CANDIDATE_NAME = "v4-bounded-rerank-candidate"


def _finite_float(value: object, *, label: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f"{label} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{label} must be finite")
    return result


def _load_thresholds(raw: str) -> dict[str, float]:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("--candidate-thresholds-json must be valid JSON") from exc
    if not isinstance(value, dict) or not value:
        raise ValueError("--candidate-thresholds-json must be a non-empty object")

    result: dict[str, float] = {}
    for route, threshold in value.items():
        if not isinstance(route, str) or not route.strip():
            raise ValueError("candidate threshold keys must be non-empty route IDs")
        number = _finite_float(threshold, label=f"threshold for {route}")
        if not 0.0 <= number <= 1.0:
            raise ValueError("candidate thresholds must be between 0 and 1")
        result[route] = number
    return result


def _percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = q * (len(ordered) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def _quality_profile(rows: list[BenchmarkRow]) -> dict[str, Any]:
    supported = [row for row in rows if row.expected is not None]
    near = [
        row
        for row in rows
        if row.category == "near_domain_unsupported_operation"
    ]
    ood = [row for row in rows if row.category == "out_of_domain"]
    no_route = [row for row in rows if row.expected is None]
    summary = summarize(rows)
    return {
        "cases": len(rows),
        "supported_cases": len(supported),
        "near_domain_unsupported_cases": len(near),
        "out_of_domain_cases": len(ood),
        "supported_exact_route_accuracy": (
            sum(row.correct for row in supported) / len(supported)
            if supported
            else 0.0
        ),
        "near_domain_unsupported_rejection": (
            sum(row.predicted is None for row in near) / len(near)
            if near
            else 0.0
        ),
        "out_of_domain_rejection": (
            sum(row.predicted is None for row in ood) / len(ood)
            if ood
            else 0.0
        ),
        "false_routes": sum(
            row.expected is None and row.predicted is not None
            for row in rows
        ),
        "false_route_rate": (
            sum(row.predicted is not None for row in no_route) / len(no_route)
            if no_route
            else 0.0
        ),
        "invalid_plan_rate": summary["invalid_plan_rate"],
        "errors": summary["errors"],
        "mean_latency_ms": summary["mean_latency_ms"],
        "p50_latency_ms": summary["p50_latency_ms"],
        "p95_latency_ms": summary["p95_latency_ms"],
        "error_taxonomy": summary["error_taxonomy"],
    }


def paired_metrics(
    baseline_rows: list[BenchmarkRow],
    candidate_rows: list[BenchmarkRow],
) -> dict[str, Any]:
    baseline = {row.case_id: row for row in baseline_rows}
    candidate = {row.case_id: row for row in candidate_rows}
    if set(baseline) != set(candidate):
        raise ValueError("paired comparison requires identical case IDs")

    gains = losses = both_correct = both_wrong = 0
    latency_deltas: list[float] = []
    for case_id in sorted(baseline):
        left = baseline[case_id]
        right = candidate[case_id]
        if left.correct and right.correct:
            both_correct += 1
        elif not left.correct and right.correct:
            gains += 1
        elif left.correct and not right.correct:
            losses += 1
        else:
            both_wrong += 1

        if left.error is None and right.error is None:
            latency_deltas.append(right.latency_ms - left.latency_ms)

    return {
        "candidate_gains": gains,
        "candidate_losses": losses,
        "both_correct": both_correct,
        "both_wrong": both_wrong,
        "latency_delta_mean_ms": (
            statistics.fmean(latency_deltas) if latency_deltas else None
        ),
        "latency_delta_p50_ms": _percentile(latency_deltas, 0.50),
        "latency_delta_p95_ms": _percentile(latency_deltas, 0.95),
    }


async def _run(args: argparse.Namespace) -> dict[str, Any]:
    if args.candidate_recall_limit < 1:
        raise ValueError("--candidate-recall-limit must be >= 1")
    if args.warmup_cases < 0:
        raise ValueError("--warmup-cases must be >= 0")

    thresholds = _load_thresholds(args.candidate_thresholds_json)
    registry = reference_registry()
    allowed_routes = {
        f"{tool.key}.{endpoint.name}"
        for tool in registry.tools()
        for endpoint in tool.endpoints
    }
    unknown_threshold_routes = sorted(set(thresholds) - allowed_routes)
    if unknown_threshold_routes:
        raise ValueError(
            "candidate thresholds reference unknown routes: "
            + ", ".join(unknown_threshold_routes)
        )

    cases = load_corpus(args.corpus, allowed_routes=allowed_routes)

    embed = load_callable(
        args.embedding_callable,
        option_name="--embedding-callable",
    )
    score_pairs = load_callable(
        args.pairwise_callable,
        option_name="--pairwise-callable",
    )

    baseline_recall = EmbeddingDecisionBackend(
        embed,
        min_similarity=-1.0,
        min_margin=0.0,
    )
    baseline_fit = EmbeddingDecisionBackend(
        embed,
        min_similarity=0.25,
        min_margin=0.0,
    )
    baseline_operation_recorder = RecordingDecisionBackend(
        PairwiseDecisionBackend(
            score_pairs,
            min_score=0.01,
            min_margin=0.0,
        )
    )
    baseline_disambiguation = EmbeddingDecisionBackend(
        embed,
        min_similarity=-1.0,
        min_margin=0.03,
    )
    baseline_planner = SchemaPlanner(
        registry,
        candidate_recall_backend=baseline_recall,
        candidate_recall_limit=2,
        candidate_fit_backend=baseline_fit,
        operation_fit_backend=baseline_operation_recorder,
        endpoint_disambiguation_backend=baseline_disambiguation,
    )

    candidate_recall = EmbeddingDecisionBackend(
        embed,
        min_similarity=-1.0,
        min_margin=0.0,
    )
    candidate_operation_recorder = RecordingDecisionBackend(
        PairwiseDecisionBackend(
            score_pairs,
            min_score=0.0,
            min_margin=0.0,
            min_score_by_option=thresholds,
            threshold_application="rank_then_gate",
        )
    )
    candidate_planner = SchemaPlanner(
        registry,
        candidate_recall_backend=candidate_recall,
        candidate_recall_limit=args.candidate_recall_limit,
        operation_fit_backend=candidate_operation_recorder,
        operation_fit_scope="all_candidates",
        operation_fit_select_accepted=True,
    )

    warmup = cases[: min(args.warmup_cases, len(cases))]
    for planner in (baseline_planner, candidate_planner):
        for case in warmup:
            try:
                await planner.aplan(case.query)
            except Exception:
                pass

    baseline_rows: list[BenchmarkRow] = []
    candidate_rows: list[BenchmarkRow] = []
    for index, case in enumerate(cases):
        if index % 2 == 0:
            order = (
                (
                    BASELINE_NAME,
                    baseline_planner,
                    baseline_operation_recorder,
                    baseline_rows,
                ),
                (
                    CANDIDATE_NAME,
                    candidate_planner,
                    candidate_operation_recorder,
                    candidate_rows,
                ),
            )
        else:
            order = (
                (
                    CANDIDATE_NAME,
                    candidate_planner,
                    candidate_operation_recorder,
                    candidate_rows,
                ),
                (
                    BASELINE_NAME,
                    baseline_planner,
                    baseline_operation_recorder,
                    baseline_rows,
                ),
            )

        for name, planner, recorder, destination in order:
            row = (
                await benchmark_planner(
                    name,
                    planner,
                    [case],
                    allowed_routes=allowed_routes,
                    operation_fit_recorder=recorder,
                )
            )[0]
            destination.append(row)

    baseline_profile = _quality_profile(baseline_rows)
    candidate_profile = _quality_profile(candidate_rows)
    paired = paired_metrics(baseline_rows, candidate_rows)

    gates = {
        "supported_exact_route_accuracy": (
            candidate_profile["supported_exact_route_accuracy"] >= 0.70
        ),
        "near_domain_unsupported_rejection": (
            candidate_profile["near_domain_unsupported_rejection"] >= 0.96
        ),
        "false_route_rate": candidate_profile["false_route_rate"] <= 0.02,
        "invalid_plan_rate": candidate_profile["invalid_plan_rate"] == 0.0,
        "execution_errors": candidate_profile["errors"] == 0,
        "mean_latency_non_regression": (
            candidate_profile["mean_latency_ms"]
            <= baseline_profile["mean_latency_ms"]
        ),
        "p95_latency_non_regression": (
            candidate_profile["p95_latency_ms"]
            <= baseline_profile["p95_latency_ms"]
        ),
    }

    return {
        "cycle": "0.11-operation-routing-quality-v4",
        "stage": "paired_executable_candidate_development",
        "source_revision": (
            args.source_revision
            or os.environ.get("SCHEMAROUTER_SOURCE_REVISION")
            or os.environ.get("GITHUB_SHA")
        ),
        "corpus": args.corpus,
        "corpus_sha256": _corpus_sha256(args.corpus),
        "hardware_label": args.hardware_label,
        "measurement": {
            "counterbalanced": True,
            "warmup_cases": args.warmup_cases,
            "baseline_name": BASELINE_NAME,
            "candidate_name": CANDIDATE_NAME,
        },
        "candidate_configuration": {
            "candidate_recall_limit": args.candidate_recall_limit,
            "threshold_application": "rank_then_gate",
            "operation_fit_scope": "all_candidates",
            "operation_fit_select_accepted": True,
            "route_local_min_score": thresholds,
        },
        "baseline": baseline_profile,
        "candidate": candidate_profile,
        "paired": paired,
        "gates": gates,
        "all_gates_passed": all(gates.values()),
        "rows": [
            *[asdict(row) for row in baseline_rows],
            *[asdict(row) for row in candidate_rows],
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", required=True)
    parser.add_argument("--candidate-recall-limit", type=int, required=True)
    parser.add_argument("--candidate-thresholds-json", required=True)
    parser.add_argument(
        "--embedding-callable",
        default="benchmarks.multilingual_embedder:embed",
    )
    parser.add_argument(
        "--pairwise-callable",
        default="benchmarks.bge_contrastive:score_pairs",
    )
    parser.add_argument("--warmup-cases", type=int, default=24)
    parser.add_argument("--source-revision", default=None)
    parser.add_argument("--hardware-label", default=None)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    result = asyncio.run(_run(args))
    destination = Path(args.out)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "all_gates_passed": result["all_gates_passed"],
                "candidate": result["candidate"],
                "baseline": result["baseline"],
                "paired": result["paired"],
                "gates": result["gates"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
