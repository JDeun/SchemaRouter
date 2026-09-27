"""Analyze the preregistered v4 route-local safety ablation."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

SELECTOR = (
    "keyword+semantic-recall+capability-fit+operation-fit+"
    "accepted-selector+endpoint-disambiguation"
)


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _rows(report: dict[str, Any]) -> list[dict[str, Any]]:
    rows = [
        row
        for row in report.get("rows", [])
        if isinstance(row, dict) and row.get("backend") == SELECTOR
    ]
    if not rows:
        raise ValueError(f"report has no rows for backend {SELECTOR!r}")
    return rows


def _summary(report: dict[str, Any]) -> dict[str, Any]:
    value = report.get("summary", {}).get(SELECTOR)
    if not isinstance(value, dict):
        raise ValueError(f"report has no summary for backend {SELECTOR!r}")
    return value


def _fraction(n: int, d: int) -> float:
    return n / d if d else 0.0


def _finite(value: object, *, label: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f"{label} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{label} must be finite")
    return result


def _profile(report: dict[str, Any]) -> dict[str, Any]:
    rows = _rows(report)
    summary = _summary(report)
    supported = [row for row in rows if row.get("expected") is not None]
    near = [
        row
        for row in rows
        if row.get("category") == "near_domain_unsupported_operation"
    ]
    no_route = [row for row in rows if row.get("expected") is None]
    taxonomy = summary.get("error_taxonomy", {})

    return {
        "cases": len(rows),
        "supported_exact_route_accuracy": _fraction(
            sum(row.get("predicted") == row.get("expected") for row in supported),
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
            label="mean latency",
        ),
        "p50_latency_ms": _finite(
            summary.get("p50_latency_ms"),
            label="p50 latency",
        ),
        "p95_latency_ms": _finite(
            summary.get("p95_latency_ms"),
            label="p95 latency",
        ),
    }


def _paired(
    baseline_report: dict[str, Any],
    candidate_report: dict[str, Any],
) -> dict[str, Any]:
    baseline = {row["case_id"]: row for row in _rows(baseline_report)}
    candidate = {row["case_id"]: row for row in _rows(candidate_report)}
    if set(baseline) != set(candidate):
        raise ValueError("paired reports must contain identical case IDs")

    gains = losses = both_correct = both_wrong = route_changes = 0
    false_route_gains = false_route_losses = 0
    for case_id in sorted(baseline):
        left = baseline[case_id]
        right = candidate[case_id]
        lc = bool(left.get("correct"))
        rc = bool(right.get("correct"))
        if lc and rc:
            both_correct += 1
        elif lc:
            losses += 1
        elif rc:
            gains += 1
        else:
            both_wrong += 1

        if left.get("predicted") != right.get("predicted"):
            route_changes += 1

        if left.get("expected") is None:
            if left.get("predicted") is not None and right.get("predicted") is None:
                false_route_gains += 1
            elif left.get("predicted") is None and right.get("predicted") is not None:
                false_route_losses += 1

    return {
        "candidate_gains": gains,
        "candidate_losses": losses,
        "both_correct": both_correct,
        "both_wrong": both_wrong,
        "route_changes": route_changes,
        "false_routes_removed": false_route_gains,
        "new_false_routes": false_route_losses,
    }


def analyze(
    baseline_report: dict[str, Any],
    dev_report: dict[str, Any],
    prod_report: dict[str, Any],
) -> dict[str, Any]:
    profiles = {
        "accepted_selector_baseline": _profile(baseline_report),
        "dev_safety_budget_12": _profile(dev_report),
        "production_safety_budget_6": _profile(prod_report),
    }
    gates = {
        "supported_exact_route_accuracy_min": 0.70,
        "near_domain_unsupported_rejection_min": 0.96,
        "false_route_rate_max": 0.02,
        "invalid_plan_rate_max": 0.0,
        "execution_errors_max": 0,
    }

    def gate_result(profile: dict[str, Any]) -> dict[str, bool]:
        return {
            "supported_exact_route_accuracy": (
                profile["supported_exact_route_accuracy"]
                >= gates["supported_exact_route_accuracy_min"]
            ),
            "near_domain_unsupported_rejection": (
                profile["near_domain_unsupported_rejection"]
                >= gates["near_domain_unsupported_rejection_min"]
            ),
            "false_route_rate": (
                profile["false_route_rate"] <= gates["false_route_rate_max"]
            ),
            "invalid_plan_rate": (
                profile["invalid_plan_rate"] <= gates["invalid_plan_rate_max"]
            ),
            "execution_errors": profile["errors"] <= gates["execution_errors_max"],
        }

    candidate_gates = {
        name: gate_result(profile)
        for name, profile in profiles.items()
        if name != "accepted_selector_baseline"
    }
    all_passed = {
        name: all(values.values())
        for name, values in candidate_gates.items()
    }

    return {
        "cycle": "0.11-operation-routing-quality-v4",
        "ablation": "route-local-operation-fit-safety-v1",
        "status": (
            "development_candidate_passed"
            if any(all_passed.values())
            else "development_candidates_failed"
        ),
        "profiles": profiles,
        "paired_vs_accepted_selector": {
            "dev_safety_budget_12": _paired(baseline_report, dev_report),
            "production_safety_budget_6": _paired(baseline_report, prod_report),
        },
        "development_gates": gates,
        "candidate_gate_results": candidate_gates,
        "all_gates_passed": all_passed,
        "source_revisions": {
            "baseline": baseline_report.get("reproducibility", {}).get(
                "source_revision"
            ),
            "dev_safety": dev_report.get("reproducibility", {}).get(
                "source_revision"
            ),
            "production_safety": prod_report.get("reproducibility", {}).get(
                "source_revision"
            ),
        },
        "corpus_sha256": baseline_report.get("reproducibility", {}).get(
            "corpus_sha256"
        ),
        "policy": (
            "This is tuning-eligible development evidence. Route-local thresholds "
            "are not calibration or production claims. A candidate may advance only "
            "after all development gates pass and the complete configuration is frozen."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline-report", type=Path, required=True)
    parser.add_argument("--dev-safety-report", type=Path, required=True)
    parser.add_argument("--production-safety-report", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    result = analyze(
        _load(args.baseline_report),
        _load(args.dev_safety_report),
        _load(args.production_safety_report),
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": result["status"],
                "profiles": result["profiles"],
                "all_gates_passed": result["all_gates_passed"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
