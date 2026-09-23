"""Calibrate bounded-decision confidence thresholds from one benchmark report."""

from __future__ import annotations

import argparse
import csv
import json
from html import escape
from pathlib import Path
from typing import Any


def _rows_for_backend(report: dict[str, Any], backend: str) -> list[dict[str, Any]]:
    rows = report.get("rows")
    if not isinstance(rows, list):
        raise ValueError("benchmark report rows must be an array")
    selected = [
        row for row in rows
        if isinstance(row, dict) and row.get("backend") == backend
    ]
    if not selected:
        raise ValueError(f"benchmark report has no rows for backend {backend!r}")
    return selected


def _row_index(report: dict[str, Any], backend: str) -> dict[str, dict[str, Any]]:
    rows = _rows_for_backend(report, backend)
    index: dict[str, dict[str, Any]] = {}
    for row in rows:
        case_id = row.get("case_id")
        if not isinstance(case_id, str) or not case_id:
            raise ValueError(f"{backend!r} row has invalid case_id")
        if case_id in index:
            raise ValueError(f"{backend!r} contains duplicate case_id {case_id!r}")
        index[case_id] = row
    return index


def parse_thresholds(value: str) -> list[float]:
    thresholds: list[float] = []
    for raw in value.split(","):
        raw = raw.strip()
        if not raw:
            continue
        threshold = float(raw)
        if not 0.0 <= threshold <= 1.0:
            raise ValueError("thresholds must be between 0 and 1")
        thresholds.append(threshold)
    if not thresholds:
        raise ValueError("at least one threshold is required")
    return sorted(set(thresholds))


def calibrate(
    report: dict[str, Any],
    *,
    backend: str,
    fallback_backend: str = "keyword",
    thresholds: list[float],
) -> dict[str, Any]:
    backend_rows = _row_index(report, backend)
    fallback_rows = _row_index(report, fallback_backend)
    if set(backend_rows) != set(fallback_rows):
        raise ValueError("backend and fallback rows must cover the same case IDs")

    results: list[dict[str, Any]] = []
    for threshold in thresholds:
        total = 0
        correct = 0
        backend_abstentions = 0
        final_no_routes = 0
        expected_no_route_total = 0
        expected_no_route_correct = 0
        confidence_rows = 0
        expanded_total = 0
        expanded_selected = 0
        category_totals: dict[str, int] = {}
        category_correct: dict[str, int] = {}

        for case_id, row in backend_rows.items():
            fallback = fallback_rows[case_id]
            total += 1
            category = str(row.get("category") or "uncategorized")
            category_totals[category] = category_totals.get(category, 0) + 1

            confidence = row.get("confidence")
            has_confidence = (
                isinstance(confidence, (int, float))
                and not isinstance(confidence, bool)
            )
            if has_confidence:
                confidence_rows += 1

            fallback_predicted = fallback.get("predicted")
            expanded = fallback_predicted is None and bool(row.get("backend_invoked"))
            if expanded:
                expanded_total += 1

            backend_selected = bool(has_confidence and float(confidence) >= threshold)
            if backend_selected:
                predicted = row.get("predicted")
                if expanded:
                    expanded_selected += 1
            elif has_confidence:
                backend_abstentions += 1
                predicted = fallback_predicted
            else:
                predicted = row.get("predicted")

            expected = row.get("expected")
            is_correct = predicted is None if expected is None else predicted == expected
            if is_correct:
                correct += 1
                category_correct[category] = category_correct.get(category, 0) + 1

            if predicted is None:
                final_no_routes += 1
            if expected is None:
                expected_no_route_total += 1
                if predicted is None:
                    expected_no_route_correct += 1

        results.append(
            {
                "threshold": threshold,
                "cases": total,
                "accuracy": correct / total if total else 0.0,
                "confidence_coverage": confidence_rows / total if total else 0.0,
                "backend_abstention_rate": (
                    backend_abstentions / confidence_rows if confidence_rows else 0.0
                ),
                "final_no_route_rate": final_no_routes / total if total else 0.0,
                "expected_no_route_recall": (
                    expected_no_route_correct / expected_no_route_total
                    if expected_no_route_total
                    else None
                ),
                "expanded_candidate_cases": expanded_total,
                "expanded_selection_rate": (
                    expanded_selected / expanded_total if expanded_total else 0.0
                ),
                "category_accuracy": {
                    category: category_correct.get(category, 0) / count
                    for category, count in sorted(category_totals.items())
                },
            }
        )

    return {
        "schema_version": 1,
        "source_generated_at": report.get("generated_at"),
        "schemarouter_version": report.get("schemarouter_version"),
        "corpus": report.get("corpus"),
        "environment": report.get("environment"),
        "backend": backend,
        "fallback_backend": fallback_backend,
        "results": results,
    }


def render_html(calibration: dict[str, Any]) -> str:
    results = calibration.get("results")
    if not isinstance(results, list):
        raise ValueError("calibration results must be an array")

    categories = sorted(
        {
            category
            for row in results
            if isinstance(row, dict)
            for category in (
                row.get("category_accuracy", {}).keys()
                if isinstance(row.get("category_accuracy"), dict)
                else ()
            )
        }
    )

    header = "".join(f"<th>{escape(category)}</th>" for category in categories)
    rows: list[str] = []
    for row in results:
        if not isinstance(row, dict):
            continue
        category_accuracy = row.get("category_accuracy", {})
        category_cells = "".join(
            f"<td>{float(category_accuracy.get(category, 0.0)) * 100:.2f}%</td>"
            for category in categories
        )
        expected_recall = row.get("expected_no_route_recall")
        expected_recall_text = (
            "—" if expected_recall is None else f"{float(expected_recall) * 100:.2f}%"
        )
        rows.append(
            "<tr>"
            f"<td>{float(row['threshold']):.2f}</td>"
            f"<td>{float(row['accuracy']) * 100:.2f}%</td>"
            f"<td>{float(row['confidence_coverage']) * 100:.2f}%</td>"
            f"<td>{float(row['backend_abstention_rate']) * 100:.2f}%</td>"
            f"<td>{float(row['final_no_route_rate']) * 100:.2f}%</td>"
            f"<td>{expected_recall_text}</td>"
            f"<td>{float(row['expanded_selection_rate']) * 100:.2f}%</td>"
            f"{category_cells}"
            "</tr>"
        )

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SchemaRouter threshold calibration</title>
<style>
:root {{ color-scheme: light dark; font-family: Inter, ui-sans-serif, system-ui, sans-serif; }}
body {{ max-width: 1800px; margin: 0 auto; padding: 32px; line-height: 1.45; }}
.table-wrap {{ overflow-x: auto; }}
table {{ width: 100%; border-collapse: collapse; font-size: .88rem; }}
th, td {{ text-align: left; padding: 9px 8px; border-bottom: 1px solid #8884; }}
th {{ white-space: nowrap; }}
</style>
</head>
<body>
<h1>SchemaRouter confidence threshold calibration</h1>
<p>
Backend: <strong>{escape(str(calibration.get("backend")))}</strong>.
Low-confidence decisions are replayed through the recorded deterministic fallback path; no model
inference is repeated.
</p>
<div class="table-wrap">
<table>
<thead>
<tr>
<th>Threshold</th><th>Accuracy</th><th>Confidence coverage</th><th>Backend abstention</th>
<th>Final no-route</th><th>Expected no-route recall</th><th>Expanded selection</th>{header}
</tr>
</thead>
<tbody>{"".join(rows)}</tbody>
</table>
</div>
</body>
</html>
"""


def write_outputs(
    calibration: dict[str, Any],
    *,
    json_out: Path | None,
    csv_out: Path | None,
    html_out: Path | None,
) -> None:
    if json_out is not None:
        json_out.parent.mkdir(parents=True, exist_ok=True)
        json_out.write_text(
            json.dumps(calibration, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    if csv_out is not None:
        results = calibration["results"]
        categories = sorted(
            {
                category
                for row in results
                for category in row.get("category_accuracy", {})
            }
        )
        csv_out.parent.mkdir(parents=True, exist_ok=True)
        fieldnames = [
            "threshold",
            "cases",
            "accuracy",
            "confidence_coverage",
            "backend_abstention_rate",
            "final_no_route_rate",
            "expected_no_route_recall",
            "expanded_candidate_cases",
            "expanded_selection_rate",
            *[f"category:{category}" for category in categories],
        ]
        with csv_out.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=fieldnames)
            writer.writeheader()
            for row in results:
                flat = {key: value for key, value in row.items() if key != "category_accuracy"}
                for category in categories:
                    flat[f"category:{category}"] = row["category_accuracy"].get(category)
                writer.writerow(flat)
    if html_out is not None:
        html_out.parent.mkdir(parents=True, exist_ok=True)
        html_out.write_text(render_html(calibration), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Replay recorded decision confidence across thresholds without re-running models."
    )
    parser.add_argument("report", type=Path)
    parser.add_argument("--backend", required=True)
    parser.add_argument("--fallback-backend", default="keyword")
    parser.add_argument(
        "--thresholds",
        default=",".join(f"{index / 20:.2f}" for index in range(20)),
        help="Comma-separated confidence thresholds in [0,1]. Default: 0.00..0.95 by 0.05.",
    )
    parser.add_argument("--json-out", type=Path, default=None)
    parser.add_argument("--csv-out", type=Path, default=None)
    parser.add_argument("--html-out", type=Path, default=None)
    args = parser.parse_args()

    report = json.loads(args.report.read_text(encoding="utf-8"))
    if not isinstance(report, dict):
        raise ValueError("benchmark report must be a JSON object")
    calibrated = calibrate(
        report,
        backend=args.backend,
        fallback_backend=args.fallback_backend,
        thresholds=parse_thresholds(args.thresholds),
    )
    write_outputs(
        calibrated,
        json_out=args.json_out,
        csv_out=args.csv_out,
        html_out=args.html_out,
    )
    print(json.dumps(calibrated, ensure_ascii=False))


if __name__ == "__main__":
    main()
