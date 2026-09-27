"""Evaluate preregistered zero-extra-inference graph corroboration candidates."""

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
    "keyword+graph-operation+graph-semantic-seed+graph-propagation+"
    "graph-corroboration+selective-semantic-recall+selective-capability-fit+"
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
    corroboration_accepts = [
        row
        for row in rows
        if row.get("graph_corroboration_decision") == "accept"
    ]
    disagreement_rejects = [
        row
        for row in rows
        if row.get("graph_corroboration_decision") == "disagree_reject"
    ]
    propagation_accepts = [
        row
        for row in rows
        if row.get("graph_propagation_decision") == "accept"
    ]
    direct_seed_accepts = [
        row
        for row in rows
        if row.get("graph_semantic_seed_decision") == "accept"
    ]

    supported_accuracy = _fraction(
        sum(bool(row.get("correct")) for row in supported),
        len(supported),
    )
    near_rejection = _fraction(
        sum(row.get("predicted") is None for row in near),
        len(near),
    )
    taxonomy = summary.get("error_taxonomy", {})
    return {
        "cases": len(rows),
        "supported_cases": len(supported),
        "supported_operation_routed_accuracy": supported_accuracy,
        "near_domain_unsupported_cases": len(near),
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
        "direct_seed_accepts": len(direct_seed_accepts),
        "direct_seed_accept_precision": (
            _fraction(
                sum(bool(row.get("correct")) for row in direct_seed_accepts),
                len(direct_seed_accepts),
            )
            if direct_seed_accepts
            else None
        ),
        "propagation_accepts": len(propagation_accepts),
        "propagation_accept_precision": (
            _fraction(
                sum(bool(row.get("correct")) for row in propagation_accepts),
                len(propagation_accepts),
            )
            if propagation_accepts
            else None
        ),
        "corroboration_accepts": len(corroboration_accepts),
        "corroboration_accept_precision": (
            _fraction(
                sum(bool(row.get("correct")) for row in corroboration_accepts),
                len(corroboration_accepts),
            )
            if corroboration_accepts
            else None
        ),
        "corroboration_unsupported_accepts": sum(
            row.get("expected") is None for row in corroboration_accepts
        ),
        "corroboration_disagreement_rejects": len(disagreement_rejects),
    }


def _paired(report: dict[str, Any]) -> dict[str, Any]:
    baseline = {row["case_id"]: row for row in _rows(report, BASELINE)}
    candidate = {row["case_id"]: row for row in _rows(report, CANDIDATE)}
    if set(baseline) != set(candidate):
        raise ValueError("paired analysis requires identical baseline/candidate case IDs")

    latency_deltas: list[float] = []
    baseline_latencies: list[float] = []
    candidate_latencies: list[float] = []
    gains = losses = both_correct = both_wrong = 0
    for case_id in sorted(baseline):
        left = baseline[case_id]
        right = candidate[case_id]
        left_correct = bool(left.get("correct"))
        right_correct = bool(right.get("correct"))
        if left_correct and right_correct:
            both_correct += 1
        elif left_correct and not right_correct:
            losses += 1
        elif not left_correct and right_correct:
            gains += 1
        else:
            both_wrong += 1

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
        latency_deltas.append(right_latency - left_latency)

    if not latency_deltas:
        raise ValueError("paired latency has no successful case pairs")

    rng = random.Random(104729)
    count = len(latency_deltas)
    bootstrap_means = [
        statistics.fmean(
            latency_deltas[rng.randrange(count)]
            for _ in range(count)
        )
        for _ in range(2000)
    ]

    discordant = gains + losses
    if discordant:
        extreme = min(gains, losses)
        tail = sum(
            math.comb(discordant, index)
            for index in range(extreme + 1)
        ) / (2**discordant)
        mcnemar_p = min(1.0, 2.0 * tail)
    else:
        mcnemar_p = 1.0

    return {
        "paired_cases": count,
        "baseline_mean_ms": statistics.fmean(baseline_latencies),
        "candidate_mean_ms": statistics.fmean(candidate_latencies),
        "mean_delta_ms": statistics.fmean(latency_deltas),
        "mean_delta_bootstrap_ci95_ms": [
            _percentile(bootstrap_means, 0.025),
            _percentile(bootstrap_means, 0.975),
        ],
        "candidate_faster_fraction": _fraction(
            sum(delta < 0.0 for delta in latency_deltas),
            count,
        ),
        "baseline_p95_ms": _percentile(baseline_latencies, 0.95),
        "candidate_p95_ms": _percentile(candidate_latencies, 0.95),
        "p95_delta_ms": (
            _percentile(candidate_latencies, 0.95)
            - _percentile(baseline_latencies, 0.95)
        ),
        "correctness": {
            "candidate_gains": gains,
            "candidate_losses": losses,
            "both_correct": both_correct,
            "both_wrong": both_wrong,
            "mcnemar_exact_two_sided_p": mcnemar_p,
        },
    }


def evaluate(path: Path) -> dict[str, Any]:
    report = _load(path)
    measurement = report.get("measurement", {})
    if measurement.get("mode") != "counterbalanced":
        raise ValueError("corroboration promotion evidence must be counterbalanced")
    if int(measurement.get("warmup_cases", 0)) <= 0:
        raise ValueError("corroboration promotion evidence requires warmup cases")

    seed = report.get("graph_semantic_seed", {})
    propagation = report.get("graph_propagation", {})
    expected_geometry = {
        "min_similarity": 0.45,
        "min_margin": 0.10,
        "direct_min_similarity": 0.55,
        "direct_min_margin": 0.15,
    }
    for key, expected in expected_geometry.items():
        actual = seed.get(key)
        if not isinstance(actual, (int, float)) or float(actual) != expected:
            raise ValueError(f"unexpected graph semantic geometry {key}: {actual!r}")

    if propagation.get("enabled") is not True:
        raise ValueError("bounded graph propagation must be enabled")
    if propagation.get("ranked_limit") != 2:
        raise ValueError("corroboration candidates require ranked_limit=2")
    if propagation.get("on_abstain") != "reject":
        raise ValueError("corroboration candidates require fail-closed propagation")
    if propagation.get("corroborate_abstain") is not True:
        raise ValueError("corroboration candidates must enable abstention corroboration")
    scope = propagation.get("scope")
    if scope not in {"ranked", "ranked_only"}:
        raise ValueError(f"unexpected corroboration scope: {scope!r}")

    baseline = _profile(report, BASELINE)
    candidate = _profile(report, CANDIDATE)
    paired = _paired(report)
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
            paired["candidate_p95_ms"] <= paired["baseline_p95_ms"]
        ),
    }
    return {
        "report": str(path),
        "source_revision": report.get("reproducibility", {}).get("source_revision"),
        "corpus_sha256": report.get("reproducibility", {}).get("corpus_sha256"),
        "candidate": {"propagation_scope": scope},
        "baseline": baseline,
        "profile": candidate,
        "paired": paired,
        "gates": gates,
        "all_gates_passed": all(gates.values()),
    }


def compare(paths: list[Path]) -> dict[str, Any]:
    if not paths:
        raise ValueError("at least one corroboration report is required")
    candidates = [evaluate(path) for path in paths]
    hashes = {item["corpus_sha256"] for item in candidates}
    if len(hashes) != 1:
        raise ValueError("corroboration candidates must use the same development corpus")

    eligible = [item for item in candidates if item["all_gates_passed"]]
    winner: dict[str, Any] | None = None
    if eligible:
        winner = min(
            eligible,
            key=lambda item: (
                -float(item["profile"]["harmonic_mean_supported_rejection"]),
                float(item["paired"]["candidate_p95_ms"]),
                float(item["paired"]["candidate_mean_ms"]),
                -float(item["profile"]["corroboration_accept_precision"] or 0.0),
            ),
        )

    return {
        "cycle": "0.10-operation-graph-projection-v3",
        "stage": "graph_corroboration_development",
        "status": (
            "development_corroboration_candidate_selected"
            if winner is not None
            else "development_corroboration_no_candidate_passed"
        ),
        "selection_data": "fresh graph-v1 development corpus only",
        "corpus_sha256": next(iter(hashes)),
        "candidates": candidates,
        "winner": winner["candidate"] if winner is not None else None,
        "winner_profile": winner["profile"] if winner is not None else None,
        "winner_paired": winner["paired"] if winner is not None else None,
        "winner_gates": winner["gates"] if winner is not None else None,
        "candidate_frozen": False,
        "freeze_allowed": winner is not None,
        "calibration_allowed": False,
        "blind_v15_allowed": False,
        "policy": (
            "Only preregistered graph corroboration scopes may be selected on fresh "
            "development data. A winner must be committed as frozen before fresh "
            "calibration. v15 remains prohibited."
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
