"""Evaluate graph semantic-seed development candidates on fresh dev data only."""

from __future__ import annotations

import argparse
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
    "keyword+graph-operation+graph-semantic-seed+selective-semantic-recall+"
    "selective-capability-fit+selective-operation-fit+"
    "selective-endpoint-disambiguation"
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


def _percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = (len(ordered) - 1) * fraction
    lower = int(index)
    upper = min(lower + 1, len(ordered) - 1)
    weight = index - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def _finite(value: object, *, label: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f"{label} must be numeric, got {value!r}")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{label} must be finite, got {value!r}")
    return result


def _profile(
    report: dict[str, Any],
    backend: str,
) -> dict[str, Any]:
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
    taxonomy = summary.get("error_taxonomy", {})

    seed_accepts = [
        row
        for row in rows
        if row.get("graph_semantic_seed_decision") == "accept"
    ]
    hard_accepts = [
        row
        for row in rows
        if row.get("graph_operation_decision") == "accept"
    ]

    return {
        "cases": len(rows),
        "supported_cases": len(supported),
        "supported_operation_routed_accuracy": _fraction(
            supported_correct,
            len(supported),
        ),
        "near_domain_unsupported_cases": len(near),
        "near_domain_unsupported_operation_rejection": _fraction(
            near_rejected,
            len(near),
        ),
        "out_of_domain_cases": len(ood),
        "out_of_domain_rejection": _fraction(ood_rejected, len(ood)),
        "harmonic_mean_supported_rejection": _harmonic(
            _fraction(supported_correct, len(supported)),
            _fraction(near_rejected, len(near)),
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
        "hard_graph_accepts": len(hard_accepts),
        "hard_graph_accept_precision": (
            _fraction(
                sum(bool(row.get("correct")) for row in hard_accepts),
                len(hard_accepts),
            )
            if hard_accepts
            else None
        ),
        "semantic_seed_accepts": len(seed_accepts),
        "semantic_seed_accept_precision": (
            _fraction(
                sum(bool(row.get("correct")) for row in seed_accepts),
                len(seed_accepts),
            )
            if seed_accepts
            else None
        ),
        "semantic_seed_supported_accepts": sum(
            row.get("expected") is not None for row in seed_accepts
        ),
        "semantic_seed_unsupported_accepts": sum(
            row.get("expected") is None for row in seed_accepts
        ),
    }


def _paired_latency(
    report: dict[str, Any],
) -> dict[str, Any]:
    baseline_rows = {row["case_id"]: row for row in _rows(report, BASELINE)}
    candidate_rows = {row["case_id"]: row for row in _rows(report, CANDIDATE)}
    if set(baseline_rows) != set(candidate_rows):
        raise ValueError("paired latency requires identical baseline/candidate case IDs")

    deltas: list[float] = []
    baseline_latencies: list[float] = []
    candidate_latencies: list[float] = []
    for case_id in sorted(baseline_rows):
        baseline = baseline_rows[case_id]
        candidate = candidate_rows[case_id]
        if baseline.get("error") is not None or candidate.get("error") is not None:
            continue
        baseline_latency = _finite(
            baseline.get("latency_ms"),
            label=f"{case_id} baseline latency",
        )
        candidate_latency = _finite(
            candidate.get("latency_ms"),
            label=f"{case_id} candidate latency",
        )
        baseline_latencies.append(baseline_latency)
        candidate_latencies.append(candidate_latency)
        deltas.append(candidate_latency - baseline_latency)

    if not deltas:
        raise ValueError("paired latency has no successful case pairs")

    rng = random.Random(104729)
    bootstrap_means: list[float] = []
    count = len(deltas)
    for _ in range(2000):
        sample = [deltas[rng.randrange(count)] for _ in range(count)]
        bootstrap_means.append(statistics.fmean(sample))

    return {
        "paired_cases": count,
        "baseline_mean_ms": statistics.fmean(baseline_latencies),
        "candidate_mean_ms": statistics.fmean(candidate_latencies),
        "mean_delta_ms": statistics.fmean(deltas),
        "mean_delta_bootstrap_ci95_ms": [
            _percentile(bootstrap_means, 0.025),
            _percentile(bootstrap_means, 0.975),
        ],
        "candidate_faster_fraction": _fraction(
            sum(delta < 0.0 for delta in deltas),
            count,
        ),
        "baseline_p95_ms": _percentile(baseline_latencies, 0.95),
        "candidate_p95_ms": _percentile(candidate_latencies, 0.95),
        "p95_delta_ms": (
            (_percentile(candidate_latencies, 0.95) or 0.0)
            - (_percentile(baseline_latencies, 0.95) or 0.0)
        ),
    }


def evaluate(path: Path) -> dict[str, Any]:
    report = _load(path)
    measurement = report.get("measurement", {})
    if measurement.get("mode") != "counterbalanced":
        raise ValueError("semantic-seed promotion evidence must be counterbalanced")
    if int(measurement.get("warmup_cases", 0)) <= 0:
        raise ValueError("semantic-seed promotion evidence requires warmup cases")

    baseline = _profile(report, BASELINE)
    candidate = _profile(report, CANDIDATE)
    paired = _paired_latency(report)
    config = report.get("graph_semantic_seed", {})
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
        "paired_mean_latency_improvement": paired["mean_delta_ms"] < 0.0,
        "paired_p95_latency_non_regression": (
            candidate["p95_latency_ms"] <= baseline["p95_latency_ms"]
        ),
    }

    return {
        "report": str(path),
        "source_revision": report.get("reproducibility", {}).get("source_revision"),
        "corpus_sha256": report.get("reproducibility", {}).get("corpus_sha256"),
        "candidate": {
            "min_similarity": config.get("min_similarity"),
            "min_margin": config.get("min_margin"),
        },
        "baseline": baseline,
        "profile": candidate,
        "paired_latency": paired,
        "gates": gates,
        "all_gates_passed": all(gates.values()),
    }


def compare(paths: list[Path]) -> dict[str, Any]:
    if not paths:
        raise ValueError("at least one report is required")
    candidates = [evaluate(path) for path in paths]
    corpus_hashes = {item["corpus_sha256"] for item in candidates}
    if len(corpus_hashes) != 1:
        raise ValueError("semantic-seed candidates must use the same development corpus")

    eligible = [item for item in candidates if item["all_gates_passed"]]
    winner: dict[str, Any] | None = None
    if eligible:
        winner = min(
            eligible,
            key=lambda item: (
                -float(item["profile"]["harmonic_mean_supported_rejection"]),
                float(item["profile"]["mean_latency_ms"]),
                -float(item["profile"]["semantic_seed_accept_precision"] or 0.0),
            ),
        )

    return {
        "cycle": "0.10-operation-graph-projection-v3",
        "stage": "graph_semantic_seed_development",
        "status": (
            "development_semantic_seed_candidate_selected"
            if winner is not None
            else "development_semantic_seed_no_candidate_passed"
        ),
        "selection_data": "fresh graph-v1 development corpus only",
        "corpus_sha256": next(iter(corpus_hashes)),
        "candidates": candidates,
        "winner": winner["candidate"] if winner is not None else None,
        "winner_profile": winner["profile"] if winner is not None else None,
        "winner_paired_latency": winner["paired_latency"] if winner is not None else None,
        "winner_gates": winner["gates"] if winner is not None else None,
        "candidate_frozen": False,
        "freeze_allowed": winner is not None,
        "calibration_allowed": False,
        "blind_v15_allowed": False,
        "policy": (
            "Only fresh development data may select this semantic-seed candidate. "
            "A selected candidate must be committed as frozen before generating or "
            "running the fresh calibration corpus. v15 remains prohibited."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path, action="append", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    result = compare(args.report)
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
                "freeze_allowed": result["freeze_allowed"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
