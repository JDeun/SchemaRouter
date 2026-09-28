"""Evaluate the frozen 0.12-C hierarchical capability ontology on DEV only."""

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

from benchmarks.hierarchical_capability_ontology import (  # noqa: E402
    MODEL_NAME,
    MODEL_REVISION,
    HierarchicalCapabilityOntologyRouter,
)
from benchmarks.operation_routing_v5c_catalog import development_registry  # noqa: E402


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


def _load_model() -> Any:
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(
        MODEL_NAME,
        revision=MODEL_REVISION,
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
    model = _load_model()
    embed = _embedder(model)
    registry = development_registry()

    static_started = time.perf_counter_ns()
    router = HierarchicalCapabilityOntologyRouter(registry, embed)
    static_ms = (time.perf_counter_ns() - static_started) / 1_000_000

    allowed = set(router.route_ids)
    result_rows: list[dict[str, Any]] = []
    latencies: list[float] = []
    authority_violations = 0
    execution_errors = 0
    empty_count = 0

    raw_supported_correct = 0
    raw_supported_tool_correct = 0

    for case in rows:
        started = time.perf_counter_ns()
        try:
            result = router.route(str(case["query"]))
            elapsed_ms = (time.perf_counter_ns() - started) / 1_000_000
            latencies.append(elapsed_ms)

            predicted = result["predicted"]
            raw_top = str(result["raw_top_route"])
            expected = case.get("expected")

            if predicted is not None and predicted not in allowed:
                authority_violations += 1
            if predicted is None:
                empty_count += 1

            if expected is not None:
                if raw_top == expected:
                    raw_supported_correct += 1
                expected_tool = str(expected).split(".", 1)[0]
                raw_tool = raw_top.split(".", 1)[0]
                if raw_tool == expected_tool:
                    raw_supported_tool_correct += 1

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
                    "request": result["request"],
                    "request_facts": result["request_facts"],
                    "compatible_routes": result["compatible_routes"],
                    "reason": result["reason"],
                    "latency_ms": elapsed_ms,
                    "error": None,
                }
            )
        except Exception as exc:  # noqa: BLE001 -- evidence must record failures.
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
                    "request": None,
                    "request_facts": [],
                    "compatible_routes": [],
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
    false_routes = sum(row["predicted"] is not None for row in unsupported)

    metrics = {
        "supported_exact_route_accuracy": supported_correct / len(supported),
        "raw_supported_exact_route_accuracy": raw_supported_correct / len(supported),
        "raw_supported_tool_accuracy": raw_supported_tool_correct / len(supported),
        "near_domain_unsupported_rejection": near_rejected / len(near),
        "out_of_domain_rejection": ood_rejected / len(ood),
        "false_routes": false_routes,
        "false_route_rate": false_routes / len(unsupported),
        "empty_ontology_capability_set_count": empty_count,
        "authority_violations": authority_violations,
        "execution_errors": execution_errors,
        "static_embedding_ms": static_ms,
        "latency_ms": _distribution(latencies),
    }

    per_language: dict[str, dict[str, float | int]] = {}
    for language in sorted({str(row["language"]) for row in result_rows}):
        language_rows = [
            row for row in result_rows
            if row["language"] == language
        ]
        language_supported = [
            row for row in language_rows
            if row["category"] == "supported"
        ]
        language_unsupported = [
            row for row in language_rows
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
    gates = {
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
        "execution_errors": execution_errors == 0,
        "p95_latency": p95 is not None and float(p95) <= 250.0,
    }

    return {
        "experiment": "hierarchical-capability-ontology-v1",
        "issue": 354,
        "model": {"name": MODEL_NAME, "revision": MODEL_REVISION},
        "surface": "0.12-C-development",
        "metrics": metrics,
        "gates": gates,
        "surface_pass": all(gates.values()),
        "policy": {
            "confirmation_scored": False,
            "prior_dev_used_for_tuning": False,
            "route_specific_thresholds": False,
            "learned_veto": False,
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
                "surface_pass": result["surface_pass"],
                "metrics": result["metrics"],
                "gates": result["gates"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
