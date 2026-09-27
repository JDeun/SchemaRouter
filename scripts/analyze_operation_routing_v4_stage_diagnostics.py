"""Analyze candidate-fit signal geometry on the fresh v4 development corpus."""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

BASELINE = (
    "keyword+semantic-recall+capability-fit+operation-fit+endpoint-disambiguation"
)


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("benchmark report must be a JSON object")
    return value


def _rows(report: dict[str, Any]) -> list[dict[str, Any]]:
    rows = [
        row
        for row in report.get("rows", [])
        if isinstance(row, dict) and row.get("backend") == BASELINE
    ]
    if not rows:
        raise ValueError(f"report has no rows for backend {BASELINE!r}")
    return rows


def _finite(value: object) -> float | None:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None
    result = float(value)
    return result if math.isfinite(result) else None


def _quantiles(values: list[float]) -> dict[str, float | None]:
    ordered = sorted(values)
    if not ordered:
        return {
            "min": None,
            "p10": None,
            "p25": None,
            "p50": None,
            "p75": None,
            "p90": None,
            "max": None,
        }

    def q(p: float) -> float:
        index = (len(ordered) - 1) * p
        lower = int(index)
        upper = min(lower + 1, len(ordered) - 1)
        fraction = index - lower
        return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction

    return {
        "min": ordered[0],
        "p10": q(0.10),
        "p25": q(0.25),
        "p50": q(0.50),
        "p75": q(0.75),
        "p90": q(0.90),
        "max": ordered[-1],
    }


def _slice(rows: list[dict[str, Any]]) -> dict[str, Any]:
    similarities = [
        value
        for row in rows
        if (value := _finite(row.get("candidate_fit_top_similarity"))) is not None
    ]
    margins = [
        value
        for row in rows
        if (value := _finite(row.get("candidate_fit_top_margin"))) is not None
    ]
    invoked = [row for row in rows if bool(row.get("candidate_fit_invoked"))]
    abstained = [row for row in invoked if bool(row.get("candidate_fit_abstained"))]
    return {
        "cases": len(rows),
        "invocations": len(invoked),
        "abstentions": len(abstained),
        "top_similarity": _quantiles(similarities),
        "top_margin": _quantiles(margins),
    }


def _supported_route_slices(rows: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        expected = row.get("expected")
        if isinstance(expected, str):
            grouped[expected].append(row)

    result: dict[str, Any] = {}
    for route, group in sorted(grouped.items()):
        invoked = [row for row in group if bool(row.get("candidate_fit_invoked"))]
        abstained = [row for row in invoked if bool(row.get("candidate_fit_abstained"))]
        top_exact = [
            row
            for row in invoked
            if row.get("candidate_fit_top_route_label") == row.get("expected")
        ]
        result[route] = {
            "cases": len(group),
            "candidate_fit_invocations": len(invoked),
            "candidate_fit_abstentions": len(abstained),
            "candidate_fit_top_route_exact": len(top_exact),
            "candidate_fit_top_route_exact_rate": (
                len(top_exact) / len(invoked) if invoked else None
            ),
        }
    return result


def _threshold_diagnostic(
    rows: list[dict[str, Any]],
    thresholds: tuple[float, ...],
) -> list[dict[str, Any]]:
    supported = [row for row in rows if row.get("expected") is not None]
    near = [
        row
        for row in rows
        if row.get("category") == "near_domain_unsupported_operation"
    ]
    output: list[dict[str, Any]] = []
    for threshold in thresholds:
        supported_pass = [
            row
            for row in supported
            if (
                bool(row.get("candidate_fit_invoked"))
                and (value := _finite(row.get("candidate_fit_top_similarity")))
                is not None
                and value >= threshold
            )
        ]
        near_pass = [
            row
            for row in near
            if (
                bool(row.get("candidate_fit_invoked"))
                and (value := _finite(row.get("candidate_fit_top_similarity")))
                is not None
                and value >= threshold
            )
        ]
        top_exact = [
            row
            for row in supported_pass
            if row.get("candidate_fit_top_route_label") == row.get("expected")
        ]
        output.append(
            {
                "min_similarity": threshold,
                "supported_gate_pass_rate": (
                    len(supported_pass) / len(supported) if supported else None
                ),
                "supported_top_route_exact_rate_over_all_supported": (
                    len(top_exact) / len(supported) if supported else None
                ),
                "near_domain_gate_rejection_rate": (
                    1.0 - len(near_pass) / len(near) if near else None
                ),
            }
        )
    return output


def analyze(report: dict[str, Any]) -> dict[str, Any]:
    rows = _rows(report)
    supported = [row for row in rows if row.get("expected") is not None]
    near = [
        row
        for row in rows
        if row.get("category") == "near_domain_unsupported_operation"
    ]
    ood = [row for row in rows if row.get("category") == "out_of_domain"]

    supported_abstained = [
        row
        for row in supported
        if bool(row.get("candidate_fit_invoked"))
        and bool(row.get("candidate_fit_abstained"))
    ]
    supported_abstained_top_expected = [
        row
        for row in supported_abstained
        if row.get("candidate_fit_top_route_label") == row.get("expected")
    ]

    supported_top_exact = [
        row
        for row in supported
        if bool(row.get("candidate_fit_invoked"))
        and row.get("candidate_fit_top_route_label") == row.get("expected")
    ]

    return {
        "cycle": "0.11-operation-routing-quality-v4",
        "diagnostic": "routing-stage-signal-observability-v1",
        "status": "development_diagnostic_only",
        "source_revision": report.get("reproducibility", {}).get("source_revision"),
        "corpus_sha256": report.get("reproducibility", {}).get("corpus_sha256"),
        "candidate_fit": {
            "all": _slice(rows),
            "supported": _slice(supported),
            "near_domain_unsupported": _slice(near),
            "out_of_domain": _slice(ood),
            "supported_abstentions": len(supported_abstained),
            "supported_abstentions_where_top_route_was_expected": len(
                supported_abstained_top_expected
            ),
            "supported_top_route_exact_rate_over_all_supported": (
                len(supported_top_exact) / len(supported) if supported else None
            ),
            "route_slices": _supported_route_slices(supported),
            "threshold_diagnostic": _threshold_diagnostic(
                rows,
                (0.15, 0.20, 0.225, 0.25, 0.275, 0.30, 0.35),
            ),
        },
        "policy": (
            "This report is tuning-eligible development diagnostics only. "
            "It changes no routing behavior and must not use calibration or blind evidence."
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
                "supported_abstentions": result["candidate_fit"][
                    "supported_abstentions"
                ],
                "recoverable_top_expected": result["candidate_fit"][
                    "supported_abstentions_where_top_route_was_expected"
                ],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
