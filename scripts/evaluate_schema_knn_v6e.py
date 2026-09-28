"""Evaluate frozen V6E non-parametric kNN capability membership on DEV only.

Confirmation remains unopened unless DEV passes every preregistered quality
and runtime gate.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmarks.operation_routing_v6e_catalog import development_registry  # noqa: E402
from benchmarks.schema_adb_baseline import BGE_MODEL, BGE_REVISION  # noqa: E402
from benchmarks.schema_knn_membership import (  # noqa: E402
    BACKGROUND_ANCHORS,
    K_NEIGHBORS,
    SchemaKNNMembershipRouter,
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


def _load_model() -> Any:
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
    model = _load_model()
    registry = development_registry()

    compile_started = time.perf_counter_ns()
    router = SchemaKNNMembershipRouter(registry, _embedder(model))
    knn_compile_ms = (time.perf_counter_ns() - compile_started) / 1_000_000

    allowed = set(router.route_ids)
    result_rows: list[dict[str, Any]] = []
    latencies: list[float] = []
    authority_violations = 0
    positive_route_switches = 0
    execution_errors = 0
    raw_supported_correct = 0
    raw_supported_tool_correct = 0
    raw_correct_winner_vetoed = 0
    total_vetoes = 0
    true_unsupported_vetoes = 0

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
                authority_violations += 1
                positive_route_switches += 1

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
                    "tool_has_unknown_knn": result["tool_has_unknown_knn"],
                    "d_pos": result["d_pos"],
                    "d_comp": result["d_comp"],
                    "d_bg": result["d_bg"],
                    "nearest_positive": result["nearest_positive"],
                    "nearest_complement": result["nearest_complement"],
                    "nearest_background": result["nearest_background"],
                    "reason": result["reason"],
                    "latency_ms": elapsed_ms,
                    "error": None,
                }
            )
        except Exception as exc:  # noqa: BLE001
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
                    "tool_has_unknown_knn": None,
                    "d_pos": None,
                    "d_comp": None,
                    "d_bg": None,
                    "nearest_positive": [],
                    "nearest_complement": [],
                    "nearest_background": [],
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
        row["predicted"] == row["expected"] for row in supported
    )
    near_rejected = sum(row["predicted"] is None for row in near)
    ood_rejected = sum(row["predicted"] is None for row in ood)
    false_routes = sum(row["predicted"] is not None for row in unsupported)

    def values(category_rows: list[dict[str, Any]], key: str) -> list[float]:
        return [
            float(row[key])
            for row in category_rows
            if row[key] is not None
        ]

    reason_counts = Counter(str(row["reason"]) for row in result_rows)
    supported_reason_counts = Counter(str(row["reason"]) for row in supported)
    near_reason_counts = Counter(str(row["reason"]) for row in near)
    ood_reason_counts = Counter(str(row["reason"]) for row in ood)

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
        "d_pos": {
            "supported": _distribution(values(supported, "d_pos")),
            "near_domain": _distribution(values(near, "d_pos")),
            "ood": _distribution(values(ood, "d_pos")),
        },
        "d_comp": {
            "supported": _distribution(values(supported, "d_comp")),
            "near_domain": _distribution(values(near, "d_comp")),
            "ood": _distribution(values(ood, "d_comp")),
        },
        "d_bg": {
            "supported": _distribution(values(supported, "d_bg")),
            "near_domain": _distribution(values(near, "d_bg")),
            "ood": _distribution(values(ood, "d_bg")),
        },
        "reason_counts": dict(sorted(reason_counts.items())),
        "reason_counts_by_category": {
            "supported": dict(sorted(supported_reason_counts.items())),
            "near_domain": dict(sorted(near_reason_counts.items())),
            "ood": dict(sorted(ood_reason_counts.items())),
        },
        "background_vetoes": reason_counts.get(
            "background_neighborhood_closer",
            0,
        ),
        "complement_vetoes": reason_counts.get(
            "complement_neighborhood_closer",
            0,
        ),
        "knn_compile_ms": knn_compile_ms,
        "positive_route_switches": positive_route_switches,
        "authority_violations": authority_violations,
        "execution_errors": execution_errors,
        "latency_ms": _distribution(latencies),
    }

    per_language: dict[str, dict[str, float | int]] = {}
    for language in sorted({str(row["language"]) for row in result_rows}):
        lang_rows = [row for row in result_rows if row["language"] == language]
        lang_supported = [
            row for row in lang_rows if row["category"] == "supported"
        ]
        lang_unsupported = [
            row for row in lang_rows if row["category"] != "supported"
        ]
        per_language[language] = {
            "cases": len(lang_rows),
            "supported_exact": (
                sum(
                    row["predicted"] == row["expected"]
                    for row in lang_supported
                )
                / len(lang_supported)
            ),
            "unsupported_rejection": (
                sum(row["predicted"] is None for row in lang_unsupported)
                / len(lang_unsupported)
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
        "out_of_domain_rejection": metrics["out_of_domain_rejection"] == 1.0,
        "false_route_rate": metrics["false_route_rate"] <= 0.01,
        "authority_violations": authority_violations == 0,
        "positive_route_switches": positive_route_switches == 0,
        "execution_errors": execution_errors == 0,
    }
    runtime_gate = p95 is not None and float(p95) <= 250.0

    return {
        "experiment": "schema-derived-nonparametric-knn-capability-membership-v1",
        "issue": 401,
        "surface": "V6E-development",
        "models": {
            "bge": {
                "name": BGE_MODEL,
                "revision": BGE_REVISION,
            },
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
            "knn_veto_only": True,
            "schema_derived_positive_bank": True,
            "schema_derived_complement_bank": True,
            "frozen_background_bank": True,
            "background_anchor_count": len(BACKGROUND_ANCHORS),
            "benchmark_rows_used_for_knn_fit": False,
            "positive_rerank": False,
            "endpoint_switch": False,
            "rank2_fallback": False,
            "pseudo_route": False,
            "k": K_NEIGHBORS,
            "weighted_knn": False,
            "distance_threshold": None,
            "margin_threshold": None,
            "ratio_threshold": None,
            "decision_order": [
                "d_bg < d_pos",
                "d_comp < d_pos",
                "preserve_raw_top1",
            ],
            "dev_selected_hyperparameters": False,
        },
        "knn_models": {
            tool_key: {
                "positive_point_count": len(knn_model.positive_points),
                "complement_point_count": len(knn_model.complement_points),
                "width": knn_model.width,
            }
            for tool_key, knn_model in sorted(router.models.items())
        },
        "background_point_count": len(router.background_points),
        "unknown_tools": sorted(router.unknown_tools),
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
