"""Evaluate the behavior-preserving graph static-option embedding cache ablation."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import statistics
from pathlib import Path
from typing import Any

BASELINE = (
    "keyword+semantic-recall+capability-fit+operation-fit+endpoint-disambiguation"
)
CANDIDATE = (
    "keyword+graph-operation+graph-semantic-seed+graph-propagation+"
    "graph-corroboration+graph-static-option-cache+selective-semantic-recall+"
    "selective-capability-fit+selective-operation-fit+"
    "selective-endpoint-disambiguation"
)
REFERENCE_PREDICTION_DIGEST = (
    "7972d4f4260e5f5138c8735b8e8d0d781bb9d7ea157c17b930e7220690f38bc7"
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
    if left <= 0.0 or right <= 0.0:
        return 0.0
    return 2.0 * left * right / (left + right)


def _finite(value: object, *, label: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f"{label} must be numeric, got {value!r}")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{label} must be finite, got {value!r}")
    return result


def _percentile(values: list[float], fraction: float) -> float:
    if not values:
        raise ValueError("percentile requires values")
    ordered = sorted(values)
    index = (len(ordered) - 1) * fraction
    lower = int(index)
    upper = min(lower + 1, len(ordered) - 1)
    weight = index - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def prediction_digest(rows: list[dict[str, Any]]) -> str:
    pairs = sorted(
        (str(row.get("case_id", "")), row.get("predicted"))
        for row in rows
    )
    payload = json.dumps(
        pairs,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


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
    taxonomy = summary.get("error_taxonomy", {})

    supported_accuracy = _fraction(
        sum(bool(row.get("correct")) for row in supported),
        len(supported),
    )
    near_rejection = _fraction(
        sum(row.get("predicted") is None for row in near),
        len(near),
    )
    return {
        "cases": len(rows),
        "prediction_digest_sha256": prediction_digest(rows),
        "supported_operation_routed_accuracy": supported_accuracy,
        "near_domain_unsupported_operation_rejection": near_rejection,
        "out_of_domain_rejection": _fraction(
            sum(row.get("predicted") is None for row in ood),
            len(ood),
        ),
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
    }


def _paired(report: dict[str, Any]) -> dict[str, Any]:
    baseline = {row["case_id"]: row for row in _rows(report, BASELINE)}
    candidate = {row["case_id"]: row for row in _rows(report, CANDIDATE)}
    if set(baseline) != set(candidate):
        raise ValueError("paired analysis requires identical case IDs")

    deltas: list[float] = []
    baseline_latencies: list[float] = []
    candidate_latencies: list[float] = []
    gains = losses = 0
    for case_id in sorted(baseline):
        left = baseline[case_id]
        right = candidate[case_id]
        left_correct = bool(left.get("correct"))
        right_correct = bool(right.get("correct"))
        if not left_correct and right_correct:
            gains += 1
        elif left_correct and not right_correct:
            losses += 1

        if left.get("error") is not None or right.get("error") is not None:
            continue
        left_latency = _finite(
            left.get("latency_ms"),
            label=f"{case_id} baseline latency",
        )
        right_latency = _finite(
            right.get("latency_ms"),
            label=f"{case_id} candidate latency",
        )
        baseline_latencies.append(left_latency)
        candidate_latencies.append(right_latency)
        deltas.append(right_latency - left_latency)

    if not deltas:
        raise ValueError("paired latency has no successful case pairs")

    rng = random.Random(104729)
    count = len(deltas)
    bootstrap_means = [
        statistics.fmean(deltas[rng.randrange(count)] for _ in range(count))
        for _ in range(2000)
    ]
    return {
        "paired_cases": count,
        "baseline_mean_ms": statistics.fmean(baseline_latencies),
        "candidate_mean_ms": statistics.fmean(candidate_latencies),
        "mean_delta_ms": statistics.fmean(deltas),
        "mean_delta_bootstrap_ci95_ms": [
            _percentile(bootstrap_means, 0.025),
            _percentile(bootstrap_means, 0.975),
        ],
        "baseline_p95_ms": _percentile(baseline_latencies, 0.95),
        "candidate_p95_ms": _percentile(candidate_latencies, 0.95),
        "p95_delta_ms": (
            _percentile(candidate_latencies, 0.95)
            - _percentile(baseline_latencies, 0.95)
        ),
        "candidate_gains": gains,
        "candidate_losses": losses,
    }


def evaluate(path: Path) -> dict[str, Any]:
    report = _load(path)
    measurement = report.get("measurement", {})
    if measurement.get("mode") != "counterbalanced":
        raise ValueError("static-cache evidence must be counterbalanced")
    if int(measurement.get("warmup_cases", 0)) <= 0:
        raise ValueError("static-cache evidence requires warmup cases")

    cache = report.get("graph_static_option_embedding_cache", {})
    if cache.get("enabled") is not True:
        raise ValueError("graph static option embedding cache must be enabled")

    candidate = _profile(report, CANDIDATE)
    baseline = _profile(report, BASELINE)
    paired = _paired(report)
    gates = {
        "prediction_digest_parity": (
            candidate["prediction_digest_sha256"]
            == REFERENCE_PREDICTION_DIGEST
        ),
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
        "paired_mean_latency_improvement": paired["mean_delta_ms"] < 0.0,
        "paired_p95_latency_non_regression": (
            paired["candidate_p95_ms"] <= paired["baseline_p95_ms"]
        ),
    }
    return {
        "cycle": "0.10-operation-graph-projection-v3",
        "stage": "graph_static_option_embedding_cache_development",
        "source_revision": report.get("reproducibility", {}).get("source_revision"),
        "corpus_sha256": report.get("reproducibility", {}).get("corpus_sha256"),
        "reference_prediction_digest_sha256": REFERENCE_PREDICTION_DIGEST,
        "baseline": baseline,
        "profile": candidate,
        "paired": paired,
        "gates": gates,
        "all_gates_passed": all(gates.values()),
        "freeze_allowed": all(gates.values()),
        "calibration_allowed": False,
        "blind_v15_allowed": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    result = evaluate(args.report)
    result["status"] = (
        "development_static_cache_candidate_selected"
        if result["all_gates_passed"]
        else "development_static_cache_candidate_rejected"
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
                "freeze_allowed": result["freeze_allowed"],
                "prediction_digest_parity": result["gates"][
                    "prediction_digest_parity"
                ],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
