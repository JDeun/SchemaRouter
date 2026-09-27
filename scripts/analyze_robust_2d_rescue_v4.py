"""Diagnose 2D same-winner rescue using validator score + base score deficit."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_SCRIPTS_DIR = Path(__file__).resolve().parent
for _path in (_PROJECT_ROOT, _SCRIPTS_DIR):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import analyze_winner_rescue_validator_v4 as one_d  # noqa: E402

from benchmarks.bge_m3_frozen_candidate import FROZEN_THRESHOLDS  # noqa: E402
from benchmarks.bge_winner_validator import unload  # noqa: E402

RESCUE_FALSE_BUDGETS = (0, 1, 2, 3)


def _decorate_score_deficit(rows: list[dict[str, Any]]) -> None:
    for row in rows:
        route = str(row["top_route"])
        boundary = FROZEN_THRESHOLDS[route]
        row["base_min_score"] = float(boundary["min_score"])
        row["score_deficit"] = max(
            0.0,
            float(boundary["min_score"]) - float(row["base_top_score"]),
        )


def _route_2d_options(
    rows: list[dict[str, Any]],
    route: str,
) -> list[dict[str, Any]]:
    routed = [
        row
        for row in rows
        if not row["base_accepted"] and row["top_route"] == route
    ]
    if not routed:
        return [
            {
                "min_validator_score": math.inf,
                "max_score_deficit": -1.0,
                "additional_supported_correct": 0,
                "additional_false_routes": 0,
                "additional_wrong_supported": 0,
            }
        ]

    validator_thresholds = sorted(
        {float(row["validator_score"]) for row in routed}
    )
    deficit_thresholds = sorted(
        {float(row["score_deficit"]) for row in routed}
    )
    validator_thresholds.append(math.inf)
    deficit_thresholds = [-1.0, *deficit_thresholds]

    states: dict[tuple[int, int], dict[str, Any]] = {}
    for min_validator in validator_thresholds:
        for max_deficit in deficit_thresholds:
            rescued = [
                row
                for row in routed
                if float(row["validator_score"]) >= min_validator
                and float(row["score_deficit"]) <= max_deficit
            ]
            extra_correct = sum(
                row["expected"] is not None
                and row["expected"] == route
                for row in rescued
            )
            extra_false = sum(row["expected"] is None for row in rescued)
            extra_wrong = sum(
                row["expected"] is not None
                and row["expected"] != route
                for row in rescued
            )
            key = (extra_false, extra_wrong)
            candidate = {
                "min_validator_score": min_validator,
                "max_score_deficit": max_deficit,
                "additional_supported_correct": extra_correct,
                "additional_false_routes": extra_false,
                "additional_wrong_supported": extra_wrong,
            }
            previous = states.get(key)
            if previous is None or (
                extra_correct,
                min_validator,
                -max_deficit,
            ) > (
                int(previous["additional_supported_correct"]),
                float(previous["min_validator_score"]),
                -float(previous["max_score_deficit"]),
            ):
                states[key] = candidate

    options = list(states.values())
    non_dominated: list[dict[str, Any]] = []
    for candidate in options:
        dominated = any(
            other is not candidate
            and int(other["additional_false_routes"])
            <= int(candidate["additional_false_routes"])
            and int(other["additional_wrong_supported"])
            <= int(candidate["additional_wrong_supported"])
            and int(other["additional_supported_correct"])
            >= int(candidate["additional_supported_correct"])
            and (
                int(other["additional_false_routes"])
                < int(candidate["additional_false_routes"])
                or int(other["additional_wrong_supported"])
                < int(candidate["additional_wrong_supported"])
                or int(other["additional_supported_correct"])
                > int(candidate["additional_supported_correct"])
            )
            for other in options
        )
        if not dominated:
            non_dominated.append(candidate)
    return non_dominated


def _route_local_2d_frontier(
    rows: list[dict[str, Any]],
    routes: list[str],
    *,
    false_budget: int,
) -> dict[str, Any]:
    options = {
        route: _route_2d_options(rows, route)
        for route in routes
    }
    dp: dict[
        tuple[int, int],
        tuple[int, list[tuple[str, dict[str, Any]]]],
    ] = {(0, 0): (0, [])}

    for route in routes:
        next_dp: dict[
            tuple[int, int],
            tuple[int, list[tuple[str, dict[str, Any]]]],
        ] = {}
        for (used_false, used_wrong), (correct, selected) in dp.items():
            for option in options[route]:
                new_false = used_false + int(option["additional_false_routes"])
                if new_false > false_budget:
                    continue
                new_wrong = used_wrong + int(
                    option["additional_wrong_supported"]
                )
                new_correct = correct + int(
                    option["additional_supported_correct"]
                )
                key = (new_false, new_wrong)
                previous = next_dp.get(key)
                if previous is None or new_correct > previous[0]:
                    next_dp[key] = (
                        new_correct,
                        [*selected, (route, option)],
                    )
        dp = next_dp

    if not dp:
        raise ValueError(
            f"no 2D rescue solution for false budget {false_budget}"
        )

    # Maximize correct rescues, then minimize false/wrong supported rescues.
    (used_false, used_wrong), (correct, selected) = max(
        dp.items(),
        key=lambda item: (
            item[1][0],
            -item[0][0],
            -item[0][1],
        ),
    )
    return {
        "additional_supported_correct": correct,
        "additional_false_routes": used_false,
        "additional_wrong_supported": used_wrong,
        "thresholds": {
            route: {
                "min_validator_score": float(option["min_validator_score"]),
                "max_score_deficit": float(option["max_score_deficit"]),
            }
            for route, option in selected
        },
    }


def _compose_2d_metrics(
    rows: list[dict[str, Any]],
    thresholds: dict[str, dict[str, float]],
) -> dict[str, Any]:
    supported = [row for row in rows if row["expected"] is not None]
    near = [
        row
        for row in rows
        if row["category"] == "near_domain_unsupported_operation"
    ]
    ood = [
        row
        for row in rows
        if row["category"] == "out_of_domain"
    ]
    no_route = [row for row in rows if row["expected"] is None]

    predictions: list[str | None] = []
    rescued_ids: list[str] = []
    for row in rows:
        predicted = str(row["top_route"]) if row["base_accepted"] else None
        if not row["base_accepted"]:
            rule = thresholds.get(str(row["top_route"]))
            rescue = (
                rule is not None
                and float(row["validator_score"])
                >= float(rule["min_validator_score"])
                and float(row["score_deficit"])
                <= float(rule["max_score_deficit"])
            )
            if rescue:
                predicted = str(row["top_route"])
                rescued_ids.append(str(row["case_id"]))
        predictions.append(predicted)

    paired = list(zip(rows, predictions, strict=True))
    supported_correct = sum(
        predicted == row["expected"]
        for row, predicted in paired
        if row["expected"] is not None
    )
    near_false = sum(
        predicted is not None
        for row, predicted in paired
        if row["category"] == "near_domain_unsupported_operation"
    )
    ood_false = sum(
        predicted is not None
        for row, predicted in paired
        if row["category"] == "out_of_domain"
    )
    false_routes = sum(
        predicted is not None
        for row, predicted in paired
        if row["expected"] is None
    )
    wrong_supported = sum(
        predicted is not None
        and row["expected"] is not None
        and predicted != row["expected"]
        for row, predicted in paired
    )

    return {
        "supported_correct": supported_correct,
        "supported_exact_route_accuracy": supported_correct / len(supported),
        "near_domain_unsupported_rejection": 1.0 - near_false / len(near),
        "out_of_domain_rejection": 1.0 - ood_false / len(ood),
        "false_routes": false_routes,
        "false_route_rate": false_routes / len(no_route),
        "wrong_supported": wrong_supported,
        "rescued_cases": len(rescued_ids),
        "rescued_case_ids": sorted(rescued_ids),
    }


def evaluate(cases: list[dict[str, Any]]) -> dict[str, Any]:
    result = one_d.evaluate(cases)
    rows = result["rows"]
    _decorate_score_deficit(rows)
    routes = sorted(FROZEN_THRESHOLDS)

    frontier: list[dict[str, Any]] = []
    for budget in RESCUE_FALSE_BUDGETS:
        solution = _route_local_2d_frontier(
            rows,
            routes,
            false_budget=budget,
        )
        metrics = _compose_2d_metrics(
            rows,
            solution["thresholds"],
        )
        frontier.append(
            {
                "rescue_false_budget": budget,
                **solution,
                **metrics,
            }
        )

    primary = next(
        item
        for item in frontier
        if int(item["rescue_false_budget"]) == 0
    )
    target_pass = (
        int(primary["additional_supported_correct"]) >= 15
        and float(primary["supported_exact_route_accuracy"]) >= 0.85
        and float(primary["near_domain_unsupported_rejection"]) >= 0.97
        and float(primary["false_route_rate"]) <= 0.01
        and int(primary["additional_false_routes"]) == 0
    )

    result["experiment"] = "robust-2d-winner-rescue-v1"
    result["route_local_2d_rescue_frontier"] = frontier
    result["primary_zero_additional_false_2d"] = primary
    result["primary_2d_target_pass"] = target_pass
    result["policy"]["rescue_features"] = [
        "validator_score",
        "base_score_deficit",
    ]
    result["policy"]["base_margin_relaxed"] = False
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    cases = json.loads(args.corpus.read_text(encoding="utf-8"))
    if not isinstance(cases, list) or any(
        not isinstance(item, dict) for item in cases
    ):
        raise ValueError("corpus must be a JSON object list")

    result = evaluate(cases)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "primary": result["primary_zero_additional_false_2d"],
                "target_pass": result["primary_2d_target_pass"],
                "base": result["base"],
                "validator": result["validator"],
                "composed_sequential_latency_ms": result[
                    "composed_sequential_latency_ms"
                ],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    unload()


if __name__ == "__main__":
    main()
