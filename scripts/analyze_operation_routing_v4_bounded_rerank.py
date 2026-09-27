"""Analyze the preregistered v4 bounded retrieve-rerank diagnostic."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

TARGET_PLANNER_TOKEN = "operation-fit-all-candidates+accepted-selector"


def _quantile(values: list[float], q: float) -> float | None:
    if not values:
        return None
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


def _distribution(values: list[float]) -> dict[str, float | int | None]:
    return {
        "count": len(values),
        "p05": _quantile(values, 0.05),
        "p10": _quantile(values, 0.10),
        "p25": _quantile(values, 0.25),
        "p50": _quantile(values, 0.50),
        "p75": _quantile(values, 0.75),
        "p90": _quantile(values, 0.90),
        "p95": _quantile(values, 0.95),
    }


def _planner_name(report: dict[str, Any]) -> str:
    matches = [
        name
        for name in report.get("summary", {})
        if TARGET_PLANNER_TOKEN in name
    ]
    if len(matches) != 1:
        raise ValueError(
            "expected exactly one bounded rerank accepted-selector planner; "
            f"found {matches}"
        )
    return matches[0]


def _threshold_options(
    rows: list[dict[str, Any]],
    route: str,
) -> list[dict[str, Any]]:
    routed = [
        row
        for row in rows
        if row.get("operation_fit_invoked")
        and row.get("operation_fit_top_option_id") == route
        and row.get("operation_fit_top_score") is not None
    ]
    scores = sorted({float(row["operation_fit_top_score"]) for row in routed})
    thresholds = [0.0, *scores]
    if scores:
        thresholds.append(math.nextafter(scores[-1], math.inf))

    states: dict[int, dict[str, Any]] = {}
    for threshold in thresholds:
        true_positive = 0
        false_route = 0
        wrong_supported = 0
        for row in routed:
            score = float(row["operation_fit_top_score"])
            if score < threshold:
                continue
            expected = row.get("expected")
            if expected == route:
                true_positive += 1
            elif expected is None:
                false_route += 1
            else:
                wrong_supported += 1
        candidate = {
            "threshold": threshold,
            "supported_correct": true_positive,
            "false_routes": false_route,
            "wrong_supported": wrong_supported,
        }
        previous = states.get(false_route)
        if previous is None or (
            true_positive,
            -wrong_supported,
            threshold,
        ) > (
            previous["supported_correct"],
            -previous["wrong_supported"],
            previous["threshold"],
        ):
            states[false_route] = candidate
    return sorted(states.values(), key=lambda item: item["false_routes"])


def _optimize_route_thresholds(
    rows: list[dict[str, Any]],
    routes: list[str],
    false_budget: int,
) -> dict[str, Any]:
    route_options = {
        route: _threshold_options(rows, route)
        for route in routes
    }
    dp: dict[int, tuple[int, int, list[tuple[str, dict[str, Any]]]]] = {
        0: (0, 0, [])
    }
    for route in routes:
        next_dp: dict[int, tuple[int, int, list[tuple[str, dict[str, Any]]]]] = {}
        for used_false, (supported_correct, wrong_supported, selected) in dp.items():
            for option in route_options[route]:
                new_false = used_false + int(option["false_routes"])
                if new_false > false_budget:
                    continue
                candidate = (
                    supported_correct + int(option["supported_correct"]),
                    wrong_supported + int(option["wrong_supported"]),
                    [*selected, (route, option)],
                )
                previous = next_dp.get(new_false)
                if previous is None or (
                    candidate[0],
                    -candidate[1],
                    -new_false,
                ) > (
                    previous[0],
                    -previous[1],
                    -new_false,
                ):
                    next_dp[new_false] = candidate
        dp = next_dp

    if not dp:
        raise ValueError(f"no threshold solution for false budget {false_budget}")

    used_false, best = max(
        dp.items(),
        key=lambda item: (item[1][0], -item[0], -item[1][1]),
    )
    supported_correct, wrong_supported, selected = best
    return {
        "false_budget": false_budget,
        "false_routes": used_false,
        "supported_correct": supported_correct,
        "wrong_supported": wrong_supported,
        "thresholds": {
            route: option["threshold"]
            for route, option in selected
        },
    }


def analyze(report: dict[str, Any]) -> dict[str, Any]:
    planner = _planner_name(report)
    rows = [row for row in report["rows"] if row["backend"] == planner]
    supported = [row for row in rows if row["expected"] is not None]
    no_route = [row for row in rows if row["expected"] is None]
    near = [
        row
        for row in rows
        if row["category"] == "near_domain_unsupported_operation"
    ]
    ood = [row for row in rows if row["category"] == "out_of_domain"]

    raw_top_correct = [
        row
        for row in supported
        if row.get("operation_fit_invoked")
        and row.get("operation_fit_top_option_id") == row.get("expected")
    ]
    invoked = [row for row in rows if row.get("operation_fit_invoked")]

    grouped: dict[str, list[dict[str, Any]]] = {
        "supported_top_correct": raw_top_correct,
        "supported_top_wrong": [
            row
            for row in supported
            if row.get("operation_fit_invoked")
            and row.get("operation_fit_top_option_id") != row.get("expected")
        ],
        "near_domain_unsupported": [
            row for row in near if row.get("operation_fit_invoked")
        ],
        "out_of_domain": [
            row for row in ood if row.get("operation_fit_invoked")
        ],
    }

    route_stats: dict[str, dict[str, Any]] = {}
    for route in sorted({row["expected"] for row in supported if row["expected"]}):
        route_rows = [row for row in supported if row["expected"] == route]
        top_correct = sum(
            row.get("operation_fit_top_option_id") == route
            for row in route_rows
        )
        route_stats[route] = {
            "cases": len(route_rows),
            "raw_top_correct": top_correct,
            "raw_top_exact_rate": top_correct / len(route_rows),
        }

    language_stats: dict[str, dict[str, Any]] = {}
    for language in sorted({row["language"] for row in supported}):
        language_rows = [row for row in supported if row["language"] == language]
        top_correct = sum(
            row.get("operation_fit_top_option_id") == row.get("expected")
            for row in language_rows
        )
        language_stats[language] = {
            "cases": len(language_rows),
            "raw_top_correct": top_correct,
            "raw_top_exact_rate": top_correct / len(language_rows),
        }

    routes = sorted(
        {
            str(row["operation_fit_top_option_id"])
            for row in invoked
            if row.get("operation_fit_top_option_id")
        }
    )
    frontiers = []
    for budget in (0, 6, 12, 13, 24, 36):
        solution = _optimize_route_thresholds(rows, routes, budget)
        solution["supported_exact_route_accuracy"] = (
            solution["supported_correct"] / len(supported)
        )
        solution["canonical_false_route_rate"] = (
            solution["false_routes"] / len(no_route)
        )
        solution["near_domain_rejection_lower_bound"] = (
            1.0 - solution["false_routes"] / len(near)
        )
        frontiers.append(solution)

    summary = report["summary"][planner]
    return {
        "planner": planner,
        "source_revision": report.get("reproducibility", {}).get("source_revision"),
        "corpus_sha256": report.get("reproducibility", {}).get("corpus_sha256"),
        "cases": len(rows),
        "supported_cases": len(supported),
        "no_route_cases": len(no_route),
        "near_domain_unsupported_cases": len(near),
        "out_of_domain_cases": len(ood),
        "operation_fit_invocations": len(invoked),
        "supported_raw_top_correct": len(raw_top_correct),
        "supported_raw_top_exact_rate": len(raw_top_correct) / len(supported),
        "zero_threshold_observed": {
            "supported_exact_route_accuracy": summary["category_accuracy"][
                "v4_supported_natural"
            ],
            "near_domain_unsupported_rejection": summary["category_accuracy"][
                "near_domain_unsupported_operation"
            ],
            "out_of_domain_rejection": summary["category_accuracy"]["out_of_domain"],
            "false_routes": summary["error_taxonomy"]["false_route"],
            "canonical_false_route_rate": (
                summary["error_taxonomy"]["false_route"] / len(no_route)
            ),
            "wrong_tool": summary["error_taxonomy"]["wrong_tool"],
            "wrong_endpoint": summary["error_taxonomy"]["wrong_endpoint"],
            "missed_route": summary["error_taxonomy"]["missed_route"],
            "invalid_plan_rate": summary["invalid_plan_rate"],
            "execution_errors": summary["errors"],
            "mean_latency_ms": summary["mean_latency_ms"],
            "p95_latency_ms": summary["p95_latency_ms"],
        },
        "score_geometry": {
            name: {
                "top_score": _distribution(
                    [
                        float(row["operation_fit_top_score"])
                        for row in group
                        if row.get("operation_fit_top_score") is not None
                    ]
                ),
                "top_margin": _distribution(
                    [
                        float(row["operation_fit_top_margin"])
                        for row in group
                        if row.get("operation_fit_top_margin") is not None
                    ]
                ),
            }
            for name, group in grouped.items()
        },
        "supported_by_language": language_stats,
        "supported_by_route": route_stats,
        "winner_only_route_local_frontier": frontiers,
        "interpretation": {
            "canonical_dev_false_budget": 12,
            "production_target_false_budget": 6,
            "note": (
                "Frontier simulation is development-only and assumes rank-then-gate "
                "semantics: fix the raw top route first, apply only that route's threshold, "
                "and abstain rather than falling through to a lower-ranked route."
            ),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    report = json.loads(Path(args.report).read_text(encoding="utf-8"))
    result = analyze(report)
    destination = Path(args.out)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
