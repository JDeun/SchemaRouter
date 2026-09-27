"""Analyze fresh v4 development baselines without selecting a candidate."""

from __future__ import annotations

import argparse
import json
import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

BASELINE = (
    "keyword+semantic-recall+capability-fit+operation-fit+endpoint-disambiguation"
)
HISTORICAL_GRAPH = (
    "keyword+graph-operation+graph-semantic-seed+graph-propagation+"
    "graph-corroboration+graph-static-option-cache+selective-semantic-recall+"
    "selective-capability-fit+selective-operation-fit+"
    "selective-endpoint-disambiguation"
)


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("benchmark report must be a JSON object")
    return value


def _rows(report: dict[str, Any], backend: str) -> list[dict[str, Any]]:
    rows = [
        row
        for row in report.get("rows", [])
        if isinstance(row, dict) and row.get("backend") == backend
    ]
    if not rows:
        raise ValueError(f"report has no rows for backend {backend!r}")
    return rows


def _summary(report: dict[str, Any], backend: str) -> dict[str, Any]:
    value = report.get("summary", {}).get(backend)
    if not isinstance(value, dict):
        raise ValueError(f"report has no summary for backend {backend!r}")
    return value


def _fraction(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def _finite(value: object, *, label: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f"{label} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{label} must be finite")
    return result


def _supported_slice(
    rows: list[dict[str, Any]],
    key: str,
) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row.get("expected") is None:
            continue
        value = row.get(key)
        if isinstance(value, str) and value:
            grouped[value].append(row)
    return {
        name: {
            "cases": len(group),
            "exact_route_accuracy": _fraction(
                sum(bool(row.get("correct")) for row in group),
                len(group),
            ),
        }
        for name, group in sorted(grouped.items())
    }


def _unsupported_family_slice(
    rows: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        family = row.get("unsupported_family")
        if isinstance(family, str) and family:
            grouped[family].append(row)

    result: dict[str, dict[str, Any]] = {}
    for family, group in sorted(grouped.items()):
        false_destinations = Counter(
            str(row["predicted"])
            for row in group
            if row.get("predicted") is not None
        )
        result[family] = {
            "cases": len(group),
            "rejection": _fraction(
                sum(row.get("predicted") is None for row in group),
                len(group),
            ),
            "false_routes": sum(false_destinations.values()),
            "false_route_destinations": dict(
                sorted(false_destinations.items())
            ),
        }
    return result


def _profile(report: dict[str, Any], backend: str) -> dict[str, Any]:
    rows = _rows(report, backend)
    summary = _summary(report, backend)
    supported = [row for row in rows if row.get("expected") is not None]
    near = [
        row
        for row in rows
        if row.get("category") == "near_domain_unsupported_operation"
    ]
    ood = [row for row in rows if row.get("category") == "out_of_domain"]
    no_route = [row for row in rows if row.get("expected") is None]
    taxonomy = summary.get("error_taxonomy", {})

    language_slices = _supported_slice(rows, "language")
    route_slices = _supported_slice(rows, "expected")
    family_slices = _unsupported_family_slice(rows)

    language_values = [
        item["exact_route_accuracy"] for item in language_slices.values()
    ]
    route_values = [
        item["exact_route_accuracy"] for item in route_slices.values()
    ]
    family_values = [item["rejection"] for item in family_slices.values()]

    return {
        "cases": len(rows),
        "supported_cases": len(supported),
        "near_domain_unsupported_cases": len(near),
        "out_of_domain_cases": len(ood),
        "supported_exact_route_accuracy": _fraction(
            sum(bool(row.get("correct")) for row in supported),
            len(supported),
        ),
        "near_domain_unsupported_rejection": _fraction(
            sum(row.get("predicted") is None for row in near),
            len(near),
        ),
        "out_of_domain_rejection": _fraction(
            sum(row.get("predicted") is None for row in ood),
            len(ood),
        ),
        "false_route_rate": _fraction(
            sum(row.get("predicted") is not None for row in no_route),
            len(no_route),
        ),
        "false_routes": int(taxonomy.get("false_route", 0)),
        "missed_routes": int(taxonomy.get("missed_route", 0)),
        "wrong_tools": int(taxonomy.get("wrong_tool", 0)),
        "wrong_endpoints": int(taxonomy.get("wrong_endpoint", 0)),
        "invalid_plan_rate": float(summary.get("invalid_plan_rate", 0.0)),
        "errors": int(summary.get("errors", 0)),
        "mean_latency_ms": _finite(
            summary.get("mean_latency_ms"),
            label=f"{backend} mean latency",
        ),
        "p50_latency_ms": _finite(
            summary.get("p50_latency_ms"),
            label=f"{backend} p50 latency",
        ),
        "p95_latency_ms": _finite(
            summary.get("p95_latency_ms"),
            label=f"{backend} p95 latency",
        ),
        "worst_language_supported_accuracy": (
            min(language_values) if language_values else None
        ),
        "worst_route_supported_accuracy": (
            min(route_values) if route_values else None
        ),
        "worst_unsupported_family_rejection": (
            min(family_values) if family_values else None
        ),
        "language_slices": language_slices,
        "route_slices": route_slices,
        "unsupported_family_slices": family_slices,
    }


def _paired(
    report: dict[str, Any],
    left_backend: str,
    right_backend: str,
) -> dict[str, Any]:
    left = {row["case_id"]: row for row in _rows(report, left_backend)}
    right = {row["case_id"]: row for row in _rows(report, right_backend)}
    if set(left) != set(right):
        raise ValueError("paired development comparison requires identical case IDs")

    gains = losses = both_correct = both_wrong = 0
    latency_deltas: list[float] = []
    for case_id in sorted(left):
        left_row = left[case_id]
        right_row = right[case_id]
        left_correct = bool(left_row.get("correct"))
        right_correct = bool(right_row.get("correct"))
        if left_correct and right_correct:
            both_correct += 1
        elif left_correct:
            losses += 1
        elif right_correct:
            gains += 1
        else:
            both_wrong += 1

        if left_row.get("error") is None and right_row.get("error") is None:
            latency_deltas.append(
                _finite(
                    right_row.get("latency_ms"),
                    label=f"{case_id} right latency",
                )
                - _finite(
                    left_row.get("latency_ms"),
                    label=f"{case_id} left latency",
                )
            )

    return {
        "candidate_gains": gains,
        "candidate_losses": losses,
        "both_correct": both_correct,
        "both_wrong": both_wrong,
        "mean_latency_delta_ms": (
            statistics.fmean(latency_deltas) if latency_deltas else None
        ),
    }


def analyze(report: dict[str, Any]) -> dict[str, Any]:
    baseline = _profile(report, BASELINE)
    historical = _profile(report, HISTORICAL_GRAPH)
    return {
        "cycle": "0.11-operation-routing-quality-v4",
        "stage": "fresh_development_baseline",
        "status": "development_diagnostic_only",
        "source_revision": report.get("reproducibility", {}).get("source_revision"),
        "corpus_sha256": report.get("reproducibility", {}).get("corpus_sha256"),
        "tuning_eligible": True,
        "baseline": baseline,
        "historical_graph_candidate": historical,
        "paired_historical_vs_baseline": _paired(
            report,
            BASELINE,
            HISTORICAL_GRAPH,
        ),
        "standing_cycle_gates": {
            "supported_exact_route_accuracy_min": 0.70,
            "near_domain_unsupported_rejection_min": 0.96,
            "false_route_rate_max": 0.02,
        },
        "policy": (
            "This report establishes the fresh v4 development starting point. "
            "It does not freeze or promote a candidate. Only this fresh "
            "development corpus may be used to select v4 architecture or thresholds."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    result = analyze(_load(args.report))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": result["status"],
                "baseline_supported": result["baseline"][
                    "supported_exact_route_accuracy"
                ],
                "historical_supported": result["historical_graph_candidate"][
                    "supported_exact_route_accuracy"
                ],
                "historical_rejection": result["historical_graph_candidate"][
                    "near_domain_unsupported_rejection"
                ],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
