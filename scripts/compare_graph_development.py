"""Compare fresh graph-v1 development candidates against paired full-BGE baselines."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

BASELINE = (
    "keyword+semantic-recall+capability-fit+operation-fit+endpoint-disambiguation"
)
GRAPH = (
    "keyword+semantic-recall+capability-fit+graph-operation+"
    "selective-operation-fit+selective-endpoint-disambiguation"
)


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"benchmark report must be an object: {path}")
    return value


def _rows(report: dict[str, Any], backend: str) -> list[dict[str, Any]]:
    rows = [
        row
        for row in report.get("rows", [])
        if isinstance(row, dict) and row.get("backend") == backend
    ]
    if not rows:
        raise ValueError(f"benchmark report has no rows for {backend!r}")
    return rows


def _summary(report: dict[str, Any], backend: str) -> dict[str, Any]:
    summary = report.get("summary", {}).get(backend)
    if not isinstance(summary, dict):
        raise ValueError(f"benchmark report has no summary for {backend!r}")
    return summary


def _fraction(successes: int, total: int) -> float:
    return successes / total if total else 0.0


def _harmonic(left: float, right: float) -> float:
    if left <= 0 or right <= 0:
        return 0.0
    return 2.0 * left * right / (left + right)


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

    supported_correct = sum(bool(row.get("correct")) for row in supported)
    near_rejected = sum(row.get("predicted") is None for row in near)
    ood_rejected = sum(row.get("predicted") is None for row in ood)

    supported_accuracy = _fraction(supported_correct, len(supported))
    near_rejection = _fraction(near_rejected, len(near))
    ood_rejection = _fraction(ood_rejected, len(ood))

    taxonomy = summary.get("error_taxonomy", {})
    graph_counts = summary.get("graph_operation_counts", {})

    return {
        "cases": len(rows),
        "supported_cases": len(supported),
        "supported_operation_routed_accuracy": supported_accuracy,
        "near_domain_unsupported_cases": len(near),
        "near_domain_unsupported_operation_rejection": near_rejection,
        "out_of_domain_cases": len(ood),
        "out_of_domain_rejection": ood_rejection,
        "harmonic_mean_supported_rejection": _harmonic(
            supported_accuracy,
            near_rejection,
        ),
        "false_routes": int(taxonomy.get("false_route", 0)),
        "missed_routes": int(taxonomy.get("missed_route", 0)),
        "wrong_tools": int(taxonomy.get("wrong_tool", 0)),
        "wrong_endpoints": int(taxonomy.get("wrong_endpoint", 0)),
        "invalid_plan_rate": float(summary.get("invalid_plan_rate", 0.0)),
        "errors": int(summary.get("errors", 0)),
        "mean_latency_ms": summary.get("mean_latency_ms"),
        "p50_latency_ms": summary.get("p50_latency_ms"),
        "p95_latency_ms": summary.get("p95_latency_ms"),
        "graph_operation_counts": {
            "accept": int(graph_counts.get("accept", 0)),
            "reject": int(graph_counts.get("reject", 0)),
            "escalate": int(graph_counts.get("escalate", 0)),
        },
        "graph_operation_resolution_rate": float(
            summary.get("graph_operation_resolution_rate", 0.0)
        ),
    }


def _finite_number(value: object) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f"expected finite numeric latency, got {value!r}")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"expected finite numeric latency, got {value!r}")
    return result


def _evaluate(
    *,
    name: str,
    baseline: dict[str, Any],
    candidate: dict[str, Any],
) -> dict[str, Any]:
    baseline_mean = _finite_number(baseline["mean_latency_ms"])
    candidate_mean = _finite_number(candidate["mean_latency_ms"])
    baseline_p95 = _finite_number(baseline["p95_latency_ms"])
    candidate_p95 = _finite_number(candidate["p95_latency_ms"])

    gates = {
        "supported_operation_floor": (
            candidate["supported_operation_routed_accuracy"] >= 0.60
        ),
        "near_domain_unsupported_rejection_floor": (
            candidate["near_domain_unsupported_operation_rejection"] >= 0.95
        ),
        "false_route_non_regression": (
            candidate["false_routes"] <= baseline["false_routes"]
        ),
        "invalid_plan_zero": candidate["invalid_plan_rate"] == 0.0,
        "execution_errors_zero": candidate["errors"] == 0,
        "paired_mean_latency_improvement": candidate_mean < baseline_mean,
        "paired_p95_latency_non_regression": candidate_p95 <= baseline_p95,
    }
    return {
        "name": name,
        "baseline": baseline,
        "candidate": candidate,
        "mean_latency_reduction_fraction": (
            (baseline_mean - candidate_mean) / baseline_mean
        ),
        "p95_latency_change_fraction": (
            (candidate_p95 - baseline_p95) / baseline_p95
        ),
        "gates": gates,
        "all_gates_passed": all(gates.values()),
    }


def compare(alias_report: Path, field_report: Path) -> dict[str, Any]:
    alias = _load(alias_report)
    field = _load(field_report)

    alias_eval = _evaluate(
        name="graph-alias-only",
        baseline=_profile(alias, BASELINE),
        candidate=_profile(alias, GRAPH),
    )
    field_eval = _evaluate(
        name="graph-field-path",
        baseline=_profile(field, BASELINE),
        candidate=_profile(field, GRAPH),
    )
    evaluations = [alias_eval, field_eval]
    eligible = [item for item in evaluations if item["all_gates_passed"]]

    winner: dict[str, Any] | None = None
    if eligible:
        winner = min(
            eligible,
            key=lambda item: (
                _finite_number(item["candidate"]["mean_latency_ms"]),
                -float(item["candidate"]["harmonic_mean_supported_rejection"]),
            ),
        )

    alias_sha = alias.get("reproducibility", {}).get("corpus_sha256")
    field_sha = field.get("reproducibility", {}).get("corpus_sha256")
    if alias_sha != field_sha:
        raise ValueError("graph development reports used different corpora")

    return {
        "cycle": "0.10-operation-graph-projection-v3",
        "status": (
            "development_candidate_selected"
            if winner is not None
            else "development_no_candidate_passed"
        ),
        "selection_data": "fresh graph-v1 development corpus only",
        "corpus_sha256": alias_sha,
        "candidates": evaluations,
        "winner": winner["name"] if winner is not None else None,
        "winner_profile": winner["candidate"] if winner is not None else None,
        "winner_gates": winner["gates"] if winner is not None else None,
        "candidate_frozen": False,
        "calibration_allowed": winner is not None,
        "blind_v15_allowed": False,
        "policy": (
            "A dev winner must be committed as a frozen candidate before fresh "
            "calibration. Development results never authorize v15 generation."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--alias-report", type=Path, required=True)
    parser.add_argument("--field-report", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    result = compare(args.alias_report, args.field_report)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": result["status"],
                "winner": result["winner"],
                "calibration_allowed": result["calibration_allowed"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
