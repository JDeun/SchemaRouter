"""Analyze cheap action-only multilingual evidence on the v4 development corpus.

This is a research-only diagnostic. It does not modify planner behavior or create
execution authority. Static option texts contain only normalized endpoint action
names and trusted operation_aliases.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import time
from collections import Counter
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

SCORE_THRESHOLDS = (
    0.30,
    0.35,
    0.40,
    0.45,
    0.50,
    0.55,
    0.60,
    0.65,
    0.70,
    0.75,
    0.80,
)
MARGIN_THRESHOLDS = (0.00, 0.02, 0.05, 0.08, 0.10, 0.15, 0.20)
PRECISION_FLOORS = (0.90, 0.95, 0.97, 0.98, 0.99, 0.995, 1.00)


def normalize_action_name(name: str) -> str:
    """Normalize an endpoint action token without adding tool/domain context."""
    return " ".join(re.sub(r"[_\-]+", " ", name).split())


def action_text(endpoint_name: str, aliases: Iterable[str]) -> str:
    """Build the frozen action-only representation."""
    parts = [normalize_action_name(endpoint_name)]
    parts.extend(" ".join(alias.split()) for alias in aliases)
    return " ; ".join(dict.fromkeys(part for part in parts if part))


def build_action_options() -> list[dict[str, str]]:
    """Build registered route IDs plus action-only texts from the benchmark registry."""
    from benchmark_decision_routing import reference_registry

    options: list[dict[str, str]] = []
    for tool in reference_registry().tools():
        for endpoint in tool.endpoints:
            options.append(
                {
                    "route_id": f"{tool.key}.{endpoint.name}",
                    "action_text": action_text(
                        endpoint.name,
                        endpoint.operation_aliases,
                    ),
                }
            )
    options.sort(key=lambda item: item["route_id"])
    if len(options) != 16:
        raise ValueError(f"expected 16 registered v4 routes, found {len(options)}")
    return options


def dot(left: list[float], right: list[float]) -> float:
    if len(left) != len(right):
        raise ValueError("embedding dimensions must match")
    return float(sum(a * b for a, b in zip(left, right, strict=True)))


def percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    if not 0 <= q <= 1:
        raise ValueError("q must be between 0 and 1")
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * q
    low = math.floor(position)
    high = math.ceil(position)
    if low == high:
        return ordered[low]
    weight = position - low
    return ordered[low] * (1 - weight) + ordered[high] * weight


def distribution(values: list[float]) -> dict[str, float | int | None]:
    return {
        "count": len(values),
        "min": min(values) if values else None,
        "p05": percentile(values, 0.05),
        "p10": percentile(values, 0.10),
        "p25": percentile(values, 0.25),
        "p50": percentile(values, 0.50),
        "p75": percentile(values, 0.75),
        "p90": percentile(values, 0.90),
        "p95": percentile(values, 0.95),
        "max": max(values) if values else None,
        "mean": (sum(values) / len(values)) if values else None,
    }


def _accepted(row: dict[str, Any], score_threshold: float, margin_threshold: float) -> bool:
    return (
        float(row["top_score"]) >= score_threshold
        and float(row["top_margin"]) >= margin_threshold
    )


def fast_accept_frontier(rows: list[dict[str, Any]]) -> dict[str, Any]:
    supported = [row for row in rows if row["expected"] is not None]
    points: list[dict[str, Any]] = []
    for score_threshold in SCORE_THRESHOLDS:
        for margin_threshold in MARGIN_THRESHOLDS:
            accepted = [
                row
                for row in rows
                if _accepted(row, score_threshold, margin_threshold)
            ]
            true_accepts = [
                row
                for row in accepted
                if row["expected"] is not None and row["top_route"] == row["expected"]
            ]
            false_accepts = len(accepted) - len(true_accepts)
            points.append(
                {
                    "score_threshold": score_threshold,
                    "margin_threshold": margin_threshold,
                    "accepted": len(accepted),
                    "true_accepts": len(true_accepts),
                    "false_accepts": false_accepts,
                    "precision": (
                        len(true_accepts) / len(accepted) if accepted else None
                    ),
                    "overall_coverage": len(accepted) / len(rows),
                    "supported_correct_coverage": (
                        len(true_accepts) / len(supported) if supported else 0.0
                    ),
                }
            )

    best_by_precision_floor: dict[str, dict[str, Any] | None] = {}
    for floor in PRECISION_FLOORS:
        eligible = [
            point
            for point in points
            if point["precision"] is not None and point["precision"] >= floor
        ]
        best = max(
            eligible,
            key=lambda point: (
                point["supported_correct_coverage"],
                point["precision"],
                -point["score_threshold"],
                -point["margin_threshold"],
            ),
            default=None,
        )
        best_by_precision_floor[f"{floor:.3f}"] = best

    return {
        "score_thresholds": list(SCORE_THRESHOLDS),
        "margin_thresholds": list(MARGIN_THRESHOLDS),
        "points": points,
        "best_by_precision_floor": best_by_precision_floor,
    }


def reject_veto_frontier(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    supported = [row for row in rows if row["expected"] is not None]
    near = [
        row
        for row in rows
        if row["category"] == "near_domain_unsupported_operation"
    ]
    ood = [row for row in rows if row["category"] == "out_of_domain"]
    points: list[dict[str, Any]] = []
    for score_threshold in SCORE_THRESHOLDS:
        for margin_threshold in MARGIN_THRESHOLDS:
            supported_passes = [
                _accepted(row, score_threshold, margin_threshold)
                for row in supported
            ]
            near_passes = [
                _accepted(row, score_threshold, margin_threshold)
                for row in near
            ]
            ood_passes = [
                _accepted(row, score_threshold, margin_threshold)
                for row in ood
            ]
            points.append(
                {
                    "score_threshold": score_threshold,
                    "margin_threshold": margin_threshold,
                    "supported_signal_pass_rate": (
                        sum(supported_passes) / len(supported) if supported else 0.0
                    ),
                    "supported_correct_signal_rate": (
                        sum(
                            passed and row["top_route"] == row["expected"]
                            for row, passed in zip(
                                supported, supported_passes, strict=True
                            )
                        )
                        / len(supported)
                        if supported
                        else 0.0
                    ),
                    "near_domain_rejection_rate": (
                        sum(not passed for passed in near_passes) / len(near)
                        if near
                        else 0.0
                    ),
                    "ood_rejection_rate": (
                        sum(not passed for passed in ood_passes) / len(ood)
                        if ood
                        else 0.0
                    ),
                }
            )
    return points


def summarize_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    supported = [row for row in rows if row["expected"] is not None]
    near = [
        row
        for row in rows
        if row["category"] == "near_domain_unsupported_operation"
    ]
    ood = [row for row in rows if row["category"] == "out_of_domain"]

    per_language: dict[str, Any] = {}
    for language in sorted({str(row["language"]) for row in supported}):
        subset = [row for row in supported if row["language"] == language]
        per_language[language] = {
            "cases": len(subset),
            "raw_top_exact_rate": (
                sum(row["top_route"] == row["expected"] for row in subset) / len(subset)
                if subset
                else 0.0
            ),
            "expected_route_similarity": distribution(
                [float(row["expected_score"]) for row in subset]
            ),
        }

    per_route: dict[str, Any] = {}
    for route in sorted({str(row["expected"]) for row in supported}):
        subset = [row for row in supported if row["expected"] == route]
        per_route[route] = {
            "cases": len(subset),
            "raw_top_exact_rate": (
                sum(row["top_route"] == row["expected"] for row in subset) / len(subset)
                if subset
                else 0.0
            ),
            "expected_route_similarity": distribution(
                [float(row["expected_score"]) for row in subset]
            ),
        }

    false_family_slices: dict[str, Any] = {}
    families = sorted(
        {
            str(row["unsupported_family"])
            for row in near
            if row.get("unsupported_family") is not None
        }
    )
    for family in families:
        subset = [row for row in near if row.get("unsupported_family") == family]
        top_routes = Counter(str(row["top_route"]) for row in subset)
        false_family_slices[family] = {
            "cases": len(subset),
            "top_score": distribution([float(row["top_score"]) for row in subset]),
            "top_margin": distribution([float(row["top_margin"]) for row in subset]),
            "dominant_top_routes": [
                {"route": route, "count": count}
                for route, count in top_routes.most_common(3)
            ],
        }

    return {
        "cases": len(rows),
        "supported_cases": len(supported),
        "near_domain_cases": len(near),
        "ood_cases": len(ood),
        "supported_raw_top_exact": (
            sum(row["top_route"] == row["expected"] for row in supported)
            / len(supported)
            if supported
            else 0.0
        ),
        "per_language": per_language,
        "per_route": per_route,
        "supported_expected_route_similarity": distribution(
            [float(row["expected_score"]) for row in supported]
        ),
        "near_domain_top_score": distribution(
            [float(row["top_score"]) for row in near]
        ),
        "near_domain_top_margin": distribution(
            [float(row["top_margin"]) for row in near]
        ),
        "ood_top_score": distribution([float(row["top_score"]) for row in ood]),
        "ood_top_margin": distribution([float(row["top_margin"]) for row in ood]),
        "false_family_slices": false_family_slices,
        "fast_accept_frontier": fast_accept_frontier(rows),
        "reject_veto_frontier": reject_veto_frontier(rows),
        "query_embedding_plus_cosine_latency_ms": distribution(
            [float(row["latency_ms"]) for row in rows]
        ),
    }


def analyze(
    cases: list[dict[str, Any]],
    *,
    embed_fn: Callable[[list[str]], list[list[float]]],
) -> dict[str, Any]:
    options = build_action_options()
    route_ids = [option["route_id"] for option in options]
    action_texts = [option["action_text"] for option in options]

    # Warm model initialization before measuring static option caching or per-query cost.
    embed_fn(["warmup action evidence query"])

    option_start = time.perf_counter_ns()
    option_vectors = embed_fn(action_texts)
    option_embedding_ms = (time.perf_counter_ns() - option_start) / 1_000_000

    rows: list[dict[str, Any]] = []
    for case in cases:
        started = time.perf_counter_ns()
        query_vector = embed_fn([str(case["query"])])[0]
        scores = [dot(query_vector, vector) for vector in option_vectors]
        ranked = sorted(
            zip(route_ids, scores, strict=True),
            key=lambda item: (-item[1], item[0]),
        )
        elapsed_ms = (time.perf_counter_ns() - started) / 1_000_000
        top_route, top_score = ranked[0]
        second_score = ranked[1][1]
        expected = case.get("expected")
        expected_score = (
            scores[route_ids.index(str(expected))] if expected is not None else None
        )
        rows.append(
            {
                "case_id": case["id"],
                "category": case.get("category"),
                "language": case.get("language"),
                "unsupported_family": case.get("unsupported_family"),
                "expected": expected,
                "top_route": top_route,
                "top_score": top_score,
                "second_score": second_score,
                "top_margin": top_score - second_score,
                "expected_score": expected_score,
                "raw_top_correct": expected is not None and top_route == expected,
                "latency_ms": elapsed_ms,
            }
        )

    summary = summarize_rows(rows)
    summary["static_option_embedding_ms"] = option_embedding_ms
    summary["static_option_count"] = len(options)
    return {
        "representation": {
            "surface": "endpoint_action_name_plus_trusted_operation_aliases",
            "tool_name_included": False,
            "tool_description_included": False,
            "endpoint_description_included": False,
            "fields_included": False,
            "parameters_included": False,
            "unsupported_labels_included": False,
        },
        "options": options,
        "rows": rows,
        "summary": summary,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    from benchmarks.multilingual_embedder import embed

    cases = json.loads(args.corpus.read_text(encoding="utf-8"))
    if not isinstance(cases, list):
        raise ValueError("corpus must be a JSON list")
    result = analyze(cases, embed_fn=embed)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result["summary"], ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
