"""Evaluate frozen 0.13-A schema-derived ADB baseline on DEV only."""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmarks.operation_routing_v6a_catalog import (  # noqa: E402
    development_registry,
)
from benchmarks.schema_derived_adb import (  # noqa: E402
    BGE_MODEL,
    BGE_REVISION,
    SchemaDerivedADBRouter,
)


def _quantile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = q * (len(ordered) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def _distribution(values: list[float]) -> dict[str, float | int | None]:
    return {
        "count": len(values),
        "min": min(values) if values else None,
        "p50": _quantile(values, 0.50),
        "p90": _quantile(values, 0.90),
        "p95": _quantile(values, 0.95),
        "max": max(values) if values else None,
        "mean": statistics.fmean(values) if values else None,
    }


def _load_bge() -> Any:
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(
        BGE_MODEL,
        revision=BGE_REVISION,
        trust_remote_code=False,
    )


def _embedder(model: Any):
    def embed(texts: list[str]) -> list[list[float]]:
        vectors = model.encode(
            texts,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return vectors.tolist()

    return embed


def evaluate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    model = _load_bge()
    registry = development_registry()

    build_started = time.perf_counter_ns()
    router = SchemaDerivedADBRouter(registry, _embedder(model))
    boundary_build_ms = (time.perf_counter_ns() - build_started) / 1_000_000

    allowed = set(router.route_ids)
    radii = [
        boundary.radius
        for boundary in router.boundaries.values()
        if boundary is not None
    ]
    view_counts = [
        float(boundary.view_count)
        for boundary in router.boundaries.values()
        if boundary is not None
    ]

    result_rows: list[dict[str, Any]] = []
    latencies: list[float] = []
    min_boundary_ratios: list[float] = []
    inside_endpoint_counts: list[float] = []

    authority_violations = 0
    execution_errors = 0
    positive_route_switches = 0
    raw_supported_correct = 0
    raw_supported_tool_correct = 0
    raw_correct_winner_vetoed = 0
    total_vetoes = 0
    true_unsupported_vetoes = 0
    unknown_boundary_preserves = 0

    for case in rows:
        started = time.perf_counter_ns()
        try:
            result = router.route(str(case["query"]))
            elapsed_ms = (time.perf_counter_ns() - started) / 1_000_000
            latencies.append(elapsed_ms)

            predicted = result["predicted"]
            raw_top = str(result["raw_top_route"])
            expected = case.get("expected")
            vetoed = predicted is None

            if predicted is not None and predicted not in allowed:
                authority_violations += 1
            if predicted is not None and predicted != raw_top:
                positive_route_switches += 1
                authority_violations += 1

            if expected is not None:
                if raw_top == expected:
                    raw_supported_correct += 1
                    if vetoed:
                        raw_correct_winner_vetoed += 1
                expected_tool = str(expected).split(".", 1)[0]
                raw_tool = raw_top.split(".", 1)[0]
                if expected_tool == raw_tool:
                    raw_supported_tool_correct += 1

            if vetoed:
                total_vetoes += 1
                if expected is None:
                    true_unsupported_vetoes += 1

            if result["reason"] == "unknown_boundary_preserve":
                unknown_boundary_preserves += 1

            diagnostics = result["boundary_diagnostics"]
            ratios = [
                float(item["boundary_ratio"])
                for item in diagnostics
            ]
            min_ratio = min(ratios) if ratios else None
            if min_ratio is not None:
                min_boundary_ratios.append(min_ratio)
            inside_count = len(result["inside_routes"])
            inside_endpoint_counts.append(float(inside_count))

            result_rows.append(
                {
                    "id": case["id"],
                    "query": case["query"],
                    "category": case["category"],
                    "language": case["language"],
                    "expected": expected,
                    "predicted": predicted,
                    "raw_top_route": raw_top,
                    "raw_tool": result["raw_tool"],
                    "inside_routes": result["inside_routes"],
                    "inside_endpoint_count": inside_count,
                    "min_boundary_ratio": min_ratio,
                    "missing_boundary": result["missing_boundary"],
                    "reason": result["reason"],
                    "latency_ms": elapsed_ms,
                    "error": None,
                }
            )
        except Exception as exc:  # noqa: BLE001 -- evidence records failures.
            elapsed_ms = (time.perf_counter_ns() - started) / 1_000_000
            latencies.append(elapsed_ms)
            execution_errors += 1
            result_rows.append(
                {
                    "id": case["id"],
                    "query": case["query"],
                    "category": case["category"],
                    "language": case["language"],
                    "expected": case.get("expected"),
                    "predicted": None,
                    "raw_top_route": None,
                    "raw_tool": None,
                    "inside_routes": [],
                    "inside_endpoint_count": None,
                    "min_boundary_ratio": None,
                    "missing_boundary": None,
                    "reason": "exception",
                    "latency_ms": elapsed_ms,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )

    supported = [row for row in result_rows if row["category"] == "supported"]
    near = [
        row
        for row in result_rows
        if row["category"] == "near_domain_unsupported_operation"
    ]
    ood = [row for row in result_rows if row["category"] == "out_of_domain"]
    unsupported = [*near, *ood]

    supported_correct = sum(
        row["predicted"] == row["expected"]
        for row in supported
    )
    near_rejected = sum(row["predicted"] is None for row in near)
    ood_rejected = sum(row["predicted"] is None for row in ood)
    false_routes = sum(
        row["predicted"] is not None
        for row in unsupported
    )

    metrics: dict[str, Any] = {
        "supported_exact_route_accuracy": supported_correct / len(supported),
        "raw_supported_exact_route_accuracy": raw_supported_correct / len(supported),
        "raw_supported_tool_accuracy": raw_supported_tool_correct / len(supported),
        "near_domain_unsupported_rejection": near_rejected / len(near),
        "out_of_domain_rejection": ood_rejected / len(ood),
        "false_routes": false_routes,
        "false_route_rate": false_routes / len(unsupported),
        "vetoes": total_vetoes,
        "true_unsupported_vetoes": true_unsupported_vetoes,
        "veto_precision": (
            true_unsupported_vetoes / total_vetoes
            if total_vetoes
            else 0.0
        ),
        "veto_recall": (
            true_unsupported_vetoes / len(unsupported)
            if unsupported
            else 0.0
        ),
        "raw_correct_winner_vetoed": raw_correct_winner_vetoed,
        "raw_correct_winner_veto_rate": (
            raw_correct_winner_vetoed / raw_supported_correct
            if raw_supported_correct
            else 0.0
        ),
        "positive_route_switches": positive_route_switches,
        "authority_violations": authority_violations,
        "execution_errors": execution_errors,
        "unknown_boundary_preserves": unknown_boundary_preserves,
        "boundary_build_ms": boundary_build_ms,
        "boundary_radius": _distribution(radii),
        "boundary_view_count": _distribution(view_counts),
        "min_boundary_ratio": _distribution(min_boundary_ratios),
        "inside_endpoint_count": _distribution(inside_endpoint_counts),
        "latency_ms": _distribution(latencies),
    }

    per_language: dict[str, dict[str, float | int]] = {}
    for language in sorted({str(row["language"]) for row in result_rows}):
        language_rows = [
            row
            for row in result_rows
            if row["language"] == language
        ]
        language_supported = [
            row
            for row in language_rows
            if row["category"] == "supported"
        ]
        language_unsupported = [
            row
            for row in language_rows
            if row["category"] != "supported"
        ]
        per_language[language] = {
            "cases": len(language_rows),
            "supported_exact": (
                sum(
                    row["predicted"] == row["expected"]
                    for row in language_supported
                )
                / len(language_supported)
            ),
            "unsupported_rejection": (
                sum(row["predicted"] is None for row in language_unsupported)
                / len(language_unsupported)
            ),
        }
    metrics["per_language"] = per_language

    p95 = metrics["latency_ms"]["p95"]
    quality_gates = {
        "supported_exact_route_accuracy": (
            metrics["supported_exact_route_accuracy"] >= 0.85
        ),
        "near_domain_unsupported_rejection": (
            metrics["near_domain_unsupported_rejection"] >= 0.97
        ),
        "out_of_domain_rejection": (
            metrics["out_of_domain_rejection"] == 1.0
        ),
        "false_route_rate": metrics["false_route_rate"] <= 0.01,
        "authority_violations": authority_violations == 0,
        "positive_route_switches": positive_route_switches == 0,
        "execution_errors": execution_errors == 0,
    }
    runtime_gate = p95 is not None and float(p95) <= 250.0

    return {
        "experiment": "schema-derived-adb-baseline-v1",
        "issue": 383,
        "surface": "0.13-A-development",
        "models": {
            "bge": {
                "name": BGE_MODEL,
                "revision": BGE_REVISION,
            }
        },
        "metrics": metrics,
        "quality_gates": quality_gates,
        "runtime_gate": runtime_gate,
        "quality_pass": all(quality_gates.values()),
        "surface_pass": all(quality_gates.values()) and runtime_gate,
        "policy": {
            "confirmation_scored": False,
            "prior_failed_rows_used_for_tuning": False,
            "raw_bge_is_sole_positive_selector": True,
            "adb_veto_only": True,
            "adb_positive_rerank": False,
            "endpoint_switch": False,
            "benchmark_labels_used_for_boundary_fit": False,
            "oos_examples_used_for_boundary_fit": False,
            "confidence_or_margin_threshold_grid": False,
            "cross_tool_fallback": False,
            "pseudo_route": False,
        },
        "rows": result_rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--development", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    rows = json.loads(args.development.read_text(encoding="utf-8"))
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise ValueError("development corpus must be a list of objects")

    result = evaluate(rows)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "surface": result["surface"],
                "quality_pass": result["quality_pass"],
                "runtime_gate": result["runtime_gate"],
                "surface_pass": result["surface_pass"],
                "metrics": result["metrics"],
                "quality_gates": result["quality_gates"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
