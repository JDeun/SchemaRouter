"""Validate decision parity between a frozen routing reference and a runtime variant."""

from __future__ import annotations

import argparse
import json
import math
import statistics
from pathlib import Path
from typing import Any


class RuntimeParityError(ValueError):
    """Raised when a runtime variant changes frozen routing semantics."""


def _load(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise RuntimeParityError(f"{path}: analysis root must be an object")
    rows = data.get("rows")
    if not isinstance(rows, list) or not rows:
        raise RuntimeParityError(f"{path}: rows must be a non-empty list")
    return data


def _index_rows(data: dict[str, Any], label: str) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for index, row in enumerate(data["rows"]):
        if not isinstance(row, dict):
            raise RuntimeParityError(f"{label}: row {index} must be an object")
        case_id = row.get("case_id")
        if not isinstance(case_id, str) or not case_id:
            raise RuntimeParityError(f"{label}: row {index} has invalid case_id")
        if case_id in indexed:
            raise RuntimeParityError(f"{label}: duplicate case_id {case_id!r}")
        if row.get("error") not in (None, ""):
            raise RuntimeParityError(
                f"{label}: row {case_id!r} contains error {row.get('error')!r}"
            )
        indexed[case_id] = row
    return indexed


def _numeric_probability(row: dict[str, Any], field: str, label: str) -> float:
    value = row.get(field)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RuntimeParityError(
            f"{label}: field {field!r} must be numeric for {row.get('case_id')!r}"
        )
    result = float(value)
    if not math.isfinite(result) or not 0.0 <= result <= 1.0:
        raise RuntimeParityError(
            f"{label}: field {field!r} must be finite in [0, 1] "
            f"for {row.get('case_id')!r}"
        )
    return result


def _route(row: dict[str, Any], field: str, label: str) -> str:
    value = row.get(field)
    if not isinstance(value, str) or not value:
        raise RuntimeParityError(
            f"{label}: route field {field!r} must be a non-empty string "
            f"for {row.get('case_id')!r}"
        )
    return value


def _summary_zero(data: dict[str, Any], key: str, label: str) -> None:
    summary = data.get("summary")
    if not isinstance(summary, dict):
        raise RuntimeParityError(f"{label}: missing summary object")
    value = summary.get(key)
    if value != 0:
        raise RuntimeParityError(f"{label}: summary.{key} must be 0, got {value!r}")


def _percentile(values: list[float], q: float) -> float:
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


def validate_runtime_parity(
    reference: dict[str, Any],
    candidate: dict[str, Any],
    *,
    route_field: str,
    score_field: str,
    threshold: float,
) -> dict[str, Any]:
    if not math.isfinite(threshold) or not 0.0 <= threshold <= 1.0:
        raise RuntimeParityError("threshold must be finite in [0, 1]")

    _summary_zero(reference, "execution_errors", "reference")
    _summary_zero(reference, "authority_violations", "reference")
    _summary_zero(candidate, "execution_errors", "candidate")
    _summary_zero(candidate, "authority_violations", "candidate")

    ref_rows = _index_rows(reference, "reference")
    cand_rows = _index_rows(candidate, "candidate")
    if set(ref_rows) != set(cand_rows):
        missing = sorted(set(ref_rows) - set(cand_rows))
        extra = sorted(set(cand_rows) - set(ref_rows))
        raise RuntimeParityError(
            "candidate case IDs differ from reference: "
            f"missing={missing[:10]!r}, extra={extra[:10]!r}"
        )

    route_mismatches: list[dict[str, Any]] = []
    decision_mismatches: list[dict[str, Any]] = []
    drifts: list[float] = []
    margins: list[float] = []

    for case_id in sorted(ref_rows):
        ref = ref_rows[case_id]
        cand = cand_rows[case_id]

        ref_route = _route(ref, route_field, "reference")
        cand_route = _route(cand, route_field, "candidate")
        if ref_route != cand_route:
            route_mismatches.append(
                {
                    "case_id": case_id,
                    "reference_route": ref_route,
                    "candidate_route": cand_route,
                }
            )

        ref_score = _numeric_probability(ref, score_field, "reference")
        cand_score = _numeric_probability(cand, score_field, "candidate")
        ref_accept = ref_score >= threshold
        cand_accept = cand_score >= threshold
        drift = abs(cand_score - ref_score)
        drifts.append(drift)
        margins.append(abs(ref_score - threshold))

        if ref_accept != cand_accept:
            decision_mismatches.append(
                {
                    "case_id": case_id,
                    "reference_score": ref_score,
                    "candidate_score": cand_score,
                    "threshold": threshold,
                    "reference_accept": ref_accept,
                    "candidate_accept": cand_accept,
                    "reference_route": ref_route,
                    "candidate_route": cand_route,
                }
            )

    result = {
        "valid": not route_mismatches and not decision_mismatches,
        "case_count": len(ref_rows),
        "route_field": route_field,
        "score_field": score_field,
        "threshold": threshold,
        "route_mismatch_count": len(route_mismatches),
        "decision_mismatch_count": len(decision_mismatches),
        "probability_drift": {
            "max_abs": max(drifts),
            "mean_abs": statistics.fmean(drifts),
            "p50_abs": _percentile(drifts, 0.50),
            "p95_abs": _percentile(drifts, 0.95),
        },
        "reference_boundary_margin": {
            "min_abs": min(margins),
            "p05_abs": _percentile(margins, 0.05),
            "p50_abs": _percentile(margins, 0.50),
        },
        "route_mismatches": route_mismatches[:100],
        "decision_mismatches": decision_mismatches[:100],
    }

    if route_mismatches:
        raise RuntimeParityError(
            f"runtime variant changed selected route for {len(route_mismatches)} cases"
        )
    if decision_mismatches:
        raise RuntimeParityError(
            "runtime variant crossed the frozen decision boundary for "
            f"{len(decision_mismatches)} cases"
        )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--route-field", required=True)
    parser.add_argument("--score-field", required=True)
    parser.add_argument("--threshold", type=float, required=True)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    reference = _load(args.reference)
    candidate = _load(args.candidate)
    result = validate_runtime_parity(
        reference,
        candidate,
        route_field=args.route_field,
        score_field=args.score_field,
        threshold=args.threshold,
    )

    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
    print(text, end="")


if __name__ == "__main__":
    main()
