"""Route-local BGE-M3 dual-view fusion with numerically stable boundaries."""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
import time
from pathlib import Path
from typing import Any

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_SCRIPTS_DIR = Path(__file__).resolve().parent
for _path in (_PROJECT_ROOT, _SCRIPTS_DIR):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import analyze_dual_view_embedding_v4 as dual  # noqa: E402
import analyze_embedding_backbone_screen_v4 as screen  # noqa: E402
from benchmark_decision_routing import reference_registry  # noqa: E402

ROUTE_SCHEMA_WEIGHTS: dict[str, float] = {
    "calendar.create": 0.45,
    "calendar.list": 0.55,
    "finance.history": 0.60,
    "finance.quote": 0.55,
    "inventory.search": 0.35,
    "inventory.update": 0.55,
    "materials.search": 0.55,
    "materials.structure": 0.60,
    "papers.citations": 0.60,
    "papers.search": 0.30,
    "support.create_ticket": 0.40,
    "support.search": 0.55,
    "users.lookup": 0.55,
    "users.update": 0.55,
    "weather.current": 0.55,
    "weather.forecast": 0.40,
}

FALSE_BUDGETS = (6, 12)
MARGIN_THRESHOLDS = (0.0, 0.02, 0.05, 0.08, 0.10, 0.15, 0.20)
ROUND_DECIMALS = 6
PRIMARY_STABILITY_EPSILON = 1e-6
SECONDARY_STABILITY_EPSILON = 1e-5


def _distribution(values: list[float]) -> dict[str, float | int | None]:
    if not values:
        return {
            "count": 0,
            "min": None,
            "p50": None,
            "p95": None,
            "max": None,
            "mean": None,
        }
    ordered = sorted(values)

    def percentile(q: float) -> float:
        position = (len(ordered) - 1) * q
        lower = math.floor(position)
        upper = math.ceil(position)
        if lower == upper:
            return ordered[lower]
        weight = position - lower
        return ordered[lower] * (1.0 - weight) + ordered[upper] * weight

    return {
        "count": len(values),
        "min": min(values),
        "p50": percentile(0.50),
        "p95": percentile(0.95),
        "max": max(values),
        "mean": statistics.fmean(values),
    }


def _round_up(value: float, decimals: int = ROUND_DECIMALS) -> float:
    if value <= -1.0 or value >= 1.000001:
        return value
    scale = 10**decimals
    return math.ceil(value * scale) / scale


def _midpoint_thresholds(scores: list[float]) -> list[float]:
    unique = sorted(set(scores))
    if not unique:
        return [-1.0, 1.000001]
    thresholds = [-1.0]
    thresholds.extend(
        (left + right) / 2.0
        for left, right in zip(unique, unique[1:], strict=False)
    )
    thresholds.append(1.000001)
    return thresholds


def _catalog() -> list[dict[str, Any]]:
    registry = reference_registry()
    items: list[dict[str, Any]] = []
    for tool in registry.tools():
        for endpoint in tool.endpoints:
            route_id = f"{tool.key}.{endpoint.name}"
            if route_id not in ROUTE_SCHEMA_WEIGHTS:
                raise ValueError(f"missing frozen route fusion weight for {route_id}")
            items.append(
                {
                    "route_id": route_id,
                    "schema_text": dual._schema_text(tool, endpoint),
                    "action_text": dual._action_text(endpoint),
                    "schema_weight": ROUTE_SCHEMA_WEIGHTS[route_id],
                }
            )
    actual = {str(item["route_id"]) for item in items}
    expected = set(ROUTE_SCHEMA_WEIGHTS)
    if actual != expected:
        raise ValueError(
            f"route map mismatch: missing={sorted(expected-actual)}, "
            f"extra={sorted(actual-expected)}"
        )
    return sorted(items, key=lambda item: str(item["route_id"]))


def _threshold_options(
    rows: list[dict[str, Any]],
    *,
    route: str,
) -> list[dict[str, Any]]:
    routed = [
        row
        for row in rows
        if row["selected_route"] == route
    ]
    score_thresholds = _midpoint_thresholds(
        [float(row["top_score"]) for row in routed]
    )

    states: dict[tuple[int, int], dict[str, Any]] = {}
    for score_threshold in score_thresholds:
        for margin_threshold in MARGIN_THRESHOLDS:
            supported_correct = 0
            false_routes = 0
            wrong_supported = 0
            for row in routed:
                if (
                    float(row["top_score"]) < score_threshold
                    or float(row["top_margin"]) < margin_threshold
                ):
                    continue
                expected = row.get("expected")
                if expected == route:
                    supported_correct += 1
                elif expected is None:
                    false_routes += 1
                else:
                    wrong_supported += 1

            key = (false_routes, wrong_supported)
            candidate = {
                "min_score_unrounded": score_threshold,
                "min_margin": margin_threshold,
                "supported_correct": supported_correct,
                "false_routes": false_routes,
                "wrong_supported": wrong_supported,
            }
            previous = states.get(key)
            if previous is None or (
                supported_correct,
                score_threshold,
                margin_threshold,
            ) > (
                int(previous["supported_correct"]),
                float(previous["min_score_unrounded"]),
                float(previous["min_margin"]),
            ):
                states[key] = candidate

    candidates = list(states.values())
    non_dominated: list[dict[str, Any]] = []
    for candidate in candidates:
        dominated = any(
            other is not candidate
            and int(other["false_routes"]) <= int(candidate["false_routes"])
            and int(other["wrong_supported"]) <= int(candidate["wrong_supported"])
            and int(other["supported_correct"]) >= int(candidate["supported_correct"])
            and (
                int(other["false_routes"]) < int(candidate["false_routes"])
                or int(other["wrong_supported"]) < int(candidate["wrong_supported"])
                or int(other["supported_correct"]) > int(candidate["supported_correct"])
            )
            for other in candidates
        )
        if not dominated:
            non_dominated.append(candidate)
    return non_dominated


def _optimize(
    rows: list[dict[str, Any]],
    *,
    routes: list[str],
    false_budget: int,
) -> dict[str, Any]:
    options = {
        route: _threshold_options(rows, route=route)
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
        for (used_false, used_wrong), (correct, chosen) in dp.items():
            for option in options[route]:
                new_false = used_false + int(option["false_routes"])
                if new_false > false_budget:
                    continue
                new_wrong = used_wrong + int(option["wrong_supported"])
                new_correct = correct + int(option["supported_correct"])
                key = (new_false, new_wrong)
                previous = next_dp.get(key)
                if previous is None or new_correct > previous[0]:
                    next_dp[key] = (
                        new_correct,
                        [*chosen, (route, option)],
                    )
        dp = next_dp

    if not dp:
        raise RuntimeError(f"no route-local threshold solution for budget={false_budget}")

    (used_false, used_wrong), (correct, chosen) = max(
        dp.items(),
        key=lambda item: (
            item[1][0],
            -item[0][0],
            -item[0][1],
        ),
    )
    thresholds = {
        route: {
            "min_score": _round_up(float(option["min_score_unrounded"])),
            "min_score_unrounded": float(option["min_score_unrounded"]),
            "min_margin": float(option["min_margin"]),
        }
        for route, option in chosen
    }
    return {
        "false_budget": false_budget,
        "optimizer_false_routes_unrounded": used_false,
        "optimizer_wrong_supported_unrounded": used_wrong,
        "optimizer_supported_correct_unrounded": correct,
        "thresholds": thresholds,
    }


def _project(
    rows: list[dict[str, Any]],
    *,
    thresholds: dict[str, dict[str, float]],
    perturbation_epsilon: float = 0.0,
) -> dict[str, Any]:
    supported = [row for row in rows if row.get("expected") is not None]
    near = [
        row
        for row in rows
        if row.get("category") == "near_domain_unsupported_operation"
    ]
    ood = [
        row for row in rows
        if row.get("category") == "out_of_domain"
    ]
    no_route = [row for row in rows if row.get("expected") is None]

    accepted: list[dict[str, Any]] = []
    for row in rows:
        route = str(row["selected_route"])
        threshold = thresholds[route]
        sign = 1.0 if row.get("expected") is None else -1.0
        score = float(row["top_score"]) + sign * perturbation_epsilon
        margin = float(row["top_margin"]) + sign * perturbation_epsilon
        if (
            score >= float(threshold["min_score"])
            and margin >= float(threshold["min_margin"])
        ):
            accepted.append(row)

    supported_correct = sum(
        row.get("expected") == row.get("selected_route")
        for row in accepted
        if row.get("expected") is not None
    )
    wrong_supported = sum(
        row.get("expected") is not None
        and row.get("expected") != row.get("selected_route")
        for row in accepted
    )
    false_routes = sum(row.get("expected") is None for row in accepted)
    near_false = sum(
        row.get("expected") is None
        and row.get("category") == "near_domain_unsupported_operation"
        for row in accepted
    )
    ood_false = sum(
        row.get("expected") is None
        and row.get("category") == "out_of_domain"
        for row in accepted
    )
    return {
        "perturbation_epsilon": perturbation_epsilon,
        "supported_exact_route_accuracy": supported_correct / len(supported),
        "supported_correct": supported_correct,
        "wrong_supported": wrong_supported,
        "near_domain_unsupported_rejection": 1.0 - near_false / len(near),
        "out_of_domain_rejection": 1.0 - ood_false / len(ood),
        "false_routes": false_routes,
        "false_route_rate": false_routes / len(no_route),
        "accepted_total": len(accepted),
    }


def run(cases: list[dict[str, Any]]) -> dict[str, Any]:
    config, static_embedder, query_embedder = screen._build_embedders("bge-m3")
    catalog = _catalog()
    route_ids = [str(item["route_id"]) for item in catalog]

    static_texts = [
        *(str(item["schema_text"]) for item in catalog),
        *(str(item["action_text"]) for item in catalog),
    ]
    static_started = time.perf_counter_ns()
    static_vectors = static_embedder(static_texts)
    static_ms = (time.perf_counter_ns() - static_started) / 1_000_000
    split = len(catalog)
    schema_vectors = static_vectors[:split]
    action_vectors = static_vectors[split:]

    rows: list[dict[str, Any]] = []
    latencies: list[float] = []
    for case in cases:
        started = time.perf_counter_ns()
        query_vector = query_embedder([str(case["query"])])[0]
        scores: list[float] = []
        for index, item in enumerate(catalog):
            schema_score = dual._cosine(query_vector, schema_vectors[index])
            action_score = dual._cosine(query_vector, action_vectors[index])
            schema_weight = float(item["schema_weight"])
            scores.append(
                schema_weight * schema_score
                + (1.0 - schema_weight) * action_score
            )
        top_route, top_score, second_score, top_margin = dual._rank(
            route_ids,
            scores,
        )
        latencies.append(
            (time.perf_counter_ns() - started) / 1_000_000
        )
        rows.append(
            {
                "case_id": case.get("id"),
                "query": case.get("query"),
                "category": case.get("category"),
                "language": case.get("language"),
                "unsupported_family": case.get("unsupported_family"),
                "expected": case.get("expected"),
                "selected_route": top_route,
                "top_score": top_score,
                "second_score": second_score,
                "top_margin": top_margin,
            }
        )

    supported = [row for row in rows if row.get("expected") is not None]
    raw_correct = sum(
        row.get("selected_route") == row.get("expected")
        for row in supported
    )

    routes = sorted({str(row["selected_route"]) for row in rows})
    results: dict[str, Any] = {}
    for false_budget in FALSE_BUDGETS:
        optimized = _optimize(
            rows,
            routes=routes,
            false_budget=false_budget,
        )
        nominal = _project(
            rows,
            thresholds=optimized["thresholds"],
            perturbation_epsilon=0.0,
        )
        epsilon_1e6 = _project(
            rows,
            thresholds=optimized["thresholds"],
            perturbation_epsilon=PRIMARY_STABILITY_EPSILON,
        )
        epsilon_1e5 = _project(
            rows,
            thresholds=optimized["thresholds"],
            perturbation_epsilon=SECONDARY_STABILITY_EPSILON,
        )
        results[str(false_budget)] = {
            **optimized,
            "nominal": nominal,
            "stability_1e-6": epsilon_1e6,
            "stability_1e-5": epsilon_1e5,
        }

    strict = results["6"]
    latency = _distribution(latencies)
    nominal = strict["nominal"]
    stable = strict["stability_1e-6"]
    strict_gate_pass = (
        float(nominal["supported_exact_route_accuracy"]) >= 0.85
        and float(nominal["near_domain_unsupported_rejection"]) >= 0.97
        and float(nominal["false_route_rate"]) <= 0.01
        and float(nominal["out_of_domain_rejection"]) == 1.0
        and float(stable["supported_exact_route_accuracy"]) >= 0.85
        and float(stable["near_domain_unsupported_rejection"]) >= 0.97
        and float(stable["false_route_rate"]) <= 0.01
        and latency["p95"] is not None
        and float(latency["p95"]) <= 250.0
    )

    return {
        "architecture": {
            "model": config,
            "route_schema_weights": ROUTE_SCHEMA_WEIGHTS,
            "threshold_score_candidates": "midpoints_between_unique_winner_scores",
            "threshold_rounding": "ceil_to_6_decimal_places",
            "margin_thresholds": list(MARGIN_THRESHOLDS),
            "static_route_view_embedding_ms": static_ms,
        },
        "summary": {
            "cases": len(rows),
            "raw_supported_exact_route_accuracy": raw_correct / len(supported),
            "raw_supported_correct": raw_correct,
            "latency_ms": latency,
            "strict_gate_pass": strict_gate_pass,
        },
        "false_budget_results": results,
        "policy": {
            "data_role": "tuning_eligible_development",
            "calibration_or_blind_used": False,
            "behavior_change": False,
            "full_population_denominators": True,
            "numerical_stability_primary_epsilon": PRIMARY_STABILITY_EPSILON,
            "numerical_stability_secondary_epsilon": SECONDARY_STABILITY_EPSILON,
        },
    }


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

    result = run(cases)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "raw_supported_exact_route_accuracy": result["summary"][
                    "raw_supported_exact_route_accuracy"
                ],
                "latency": result["summary"]["latency_ms"],
                "strict_gate_pass": result["summary"]["strict_gate_pass"],
                "strict": result["false_budget_results"]["6"],
                "secondary": result["false_budget_results"]["12"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
