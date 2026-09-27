"""Analyze the preregistered v4 accepted-operation selector ablation."""

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
SELECTOR = (
    "keyword+semantic-recall+capability-fit+operation-fit+"
    "accepted-selector+endpoint-disambiguation"
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
        destinations = Counter(
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
            "false_routes": sum(destinations.values()),
            "false_route_destinations": dict(sorted(destinations.items())),
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
    no_route = [row for row in rows if row.get("expected") is None]
    taxonomy = summary.get("error_taxonomy", {})

    language_slices = _supported_slice(rows, "language")
    route_slices = _supported_slice(rows, "expected")
    family_slices = _unsupported_family_slice(rows)

    operation_invoked = [
        row for row in rows if bool(row.get("operation_fit_invoked"))
    ]
    operation_accepted = [
        row
        for row in operation_invoked
        if not bool(row.get("operation_fit_abstained"))
        and isinstance(row.get("operation_fit_top_option_id"), str)
    ]
    top_controls_prediction = [
        row
        for row in operation_accepted
        if row.get("predicted") == row.get("operation_fit_top_option_id")
    ]

    return {
        "cases": len(rows),
        "supported_cases": len(supported),
        "supported_exact_route_accuracy": _fraction(
            sum(bool(row.get("correct")) for row in supported),
            len(supported),
        ),
        "near_domain_unsupported_rejection": _fraction(
            sum(row.get("predicted") is None for row in near),
            len(near),
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
        "operation_fit_invocations": len(operation_invoked),
        "operation_fit_accepts": len(operation_accepted),
        "operation_fit_abstentions": len(operation_invoked) - len(operation_accepted),
        "accepted_top_controls_prediction": len(top_controls_prediction),
        "language_slices": language_slices,
        "route_slices": route_slices,
        "unsupported_family_slices": family_slices,
    }


def _paired(report: dict[str, Any]) -> dict[str, Any]:
    baseline = {row["case_id"]: row for row in _rows(report, BASELINE)}
    selector = {row["case_id"]: row for row in _rows(report, SELECTOR)}
    if set(baseline) != set(selector):
        raise ValueError("selector comparison requires identical case IDs")

    gains = losses = both_correct = both_wrong = route_changes = 0
    top_driven_changes = 0
    latency_deltas: list[float] = []
    for case_id in sorted(baseline):
        left = baseline[case_id]
        right = selector[case_id]
        left_correct = bool(left.get("correct"))
        right_correct = bool(right.get("correct"))
        if left_correct and right_correct:
            both_correct += 1
        elif left_correct:
            losses += 1
        elif right_correct:
            gains += 1
        else:
            both_wrong += 1

        if left.get("predicted") != right.get("predicted"):
            route_changes += 1
            if right.get("predicted") == right.get("operation_fit_top_option_id"):
                top_driven_changes += 1

        if left.get("error") is None and right.get("error") is None:
            latency_deltas.append(
                _finite(right.get("latency_ms"), label=f"{case_id} selector latency")
                - _finite(left.get("latency_ms"), label=f"{case_id} baseline latency")
            )

    return {
        "candidate_gains": gains,
        "candidate_losses": losses,
        "both_correct": both_correct,
        "both_wrong": both_wrong,
        "route_changes": route_changes,
        "top_driven_route_changes": top_driven_changes,
        "mean_latency_delta_ms": (
            statistics.fmean(latency_deltas) if latency_deltas else None
        ),
    }


def analyze(report: dict[str, Any]) -> dict[str, Any]:
    baseline = _profile(report, BASELINE)
    selector = _profile(report, SELECTOR)
    paired = _paired(report)
    gates = {
        "supported_exact_route_accuracy_min": 0.70,
        "near_domain_unsupported_rejection_min": 0.96,
        "false_route_rate_max": 0.02,
        "invalid_plan_rate_max": 0.0,
        "execution_errors_max": 0,
    }
    passed = (
        selector["supported_exact_route_accuracy"]
        >= gates["supported_exact_route_accuracy_min"]
        and selector["near_domain_unsupported_rejection"]
        >= gates["near_domain_unsupported_rejection_min"]
        and selector["false_route_rate"] <= gates["false_route_rate_max"]
        and selector["invalid_plan_rate"] <= gates["invalid_plan_rate_max"]
        and selector["errors"] <= gates["execution_errors_max"]
    )
    return {
        "cycle": "0.11-operation-routing-quality-v4",
        "ablation": "operation-fit-accepted-selector-v1",
        "status": "development_candidate_passed" if passed else "development_candidate_failed",
        "source_revision": report.get("reproducibility", {}).get("source_revision"),
        "corpus_sha256": report.get("reproducibility", {}).get("corpus_sha256"),
        "tuning_eligible": True,
        "baseline": baseline,
        "selector_candidate": selector,
        "paired_selector_vs_baseline": paired,
        "standing_cycle_gates": gates,
        "all_quality_gates_passed": passed,
        "policy": (
            "This is tuning-eligible development evidence. The selector may advance "
            "only if every standing quality gate passes; otherwise diagnose and "
            "preregister the next development change without using calibration data."
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
                "selector_supported": result["selector_candidate"][
                    "supported_exact_route_accuracy"
                ],
                "selector_rejection": result["selector_candidate"][
                    "near_domain_unsupported_rejection"
                ],
                "selector_false_route_rate": result["selector_candidate"][
                    "false_route_rate"
                ],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
