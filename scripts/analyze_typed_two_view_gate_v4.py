"""DEV-only typed two-view BGE-M3 open-set gate diagnostic."""

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

FALSE_BUDGETS = (0, 3, 6, 12, 13, 24)
MARGIN_GUARDS = (0.0, 0.01, 0.02, 0.05)
GATE_FAMILIES = ("action-only", "schema-only", "typed-and")
SCHEMA_WEIGHT = 0.25
ACTION_WEIGHT = 0.75


def _distribution(values: list[float]) -> dict[str, float | int | None]:
    if not values:
        return {"count": 0, "mean": None, "p50": None, "p95": None, "max": None}
    ordered = sorted(values)

    def q(value: float) -> float:
        position = (len(ordered) - 1) * value
        lower = math.floor(position)
        upper = math.ceil(position)
        if lower == upper:
            return ordered[lower]
        weight = position - lower
        return ordered[lower] * (1.0 - weight) + ordered[upper] * weight

    return {
        "count": len(values),
        "mean": statistics.fmean(values),
        "p50": q(0.50),
        "p95": q(0.95),
        "max": max(values),
    }


def _route_options(
    rows: list[dict[str, Any]],
    *,
    route: str,
    gate_family: str,
    margin_guard: float,
) -> list[dict[str, Any]]:
    routed = [
        row
        for row in rows
        if row["selected_route"] == route
        and float(row["fused_margin"]) >= margin_guard
    ]

    schema_values = sorted({float(row["schema_score"]) for row in routed})
    action_values = sorted({float(row["action_score"]) for row in routed})

    if gate_family == "action-only":
        threshold_pairs = [(-1.0, value) for value in [-1.0, *action_values, 1.000001]]
    elif gate_family == "schema-only":
        threshold_pairs = [(value, -1.0) for value in [-1.0, *schema_values, 1.000001]]
    elif gate_family == "typed-and":
        schema_thresholds = [-1.0, *schema_values, 1.000001]
        action_thresholds = [-1.0, *action_values, 1.000001]
        threshold_pairs = [
            (schema_threshold, action_threshold)
            for schema_threshold in schema_thresholds
            for action_threshold in action_thresholds
        ]
    else:
        raise ValueError(f"unsupported gate family: {gate_family}")

    states: dict[tuple[int, int], dict[str, Any]] = {}
    for min_schema, min_action in threshold_pairs:
        correct = false_routes = wrong_supported = 0
        for row in routed:
            if float(row["schema_score"]) < min_schema:
                continue
            if float(row["action_score"]) < min_action:
                continue
            expected = row.get("expected")
            if expected == route:
                correct += 1
            elif expected is None:
                false_routes += 1
            else:
                wrong_supported += 1

        key = (false_routes, wrong_supported)
        candidate = {
            "min_schema_score": min_schema,
            "min_action_score": min_action,
            "margin_guard": margin_guard,
            "supported_correct": correct,
            "false_routes": false_routes,
            "wrong_supported": wrong_supported,
        }
        previous = states.get(key)
        if previous is None or correct > int(previous["supported_correct"]):
            states[key] = candidate

    candidates = list(states.values())
    frontier: list[dict[str, Any]] = []
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
            frontier.append(candidate)
    return frontier


def _optimize(
    rows: list[dict[str, Any]],
    *,
    routes: list[str],
    gate_family: str,
    margin_guard: float,
    false_budget: int,
) -> dict[str, Any]:
    options = {
        route: _route_options(
            rows,
            route=route,
            gate_family=gate_family,
            margin_guard=margin_guard,
        )
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
        raise RuntimeError(
            f"no solution for family={gate_family}, margin={margin_guard}, "
            f"false_budget={false_budget}"
        )

    (used_false, used_wrong), (correct, chosen) = max(
        dp.items(),
        key=lambda item: (item[1][0], -item[0][0], -item[0][1]),
    )
    return {
        "gate_family": gate_family,
        "margin_guard": margin_guard,
        "false_budget": false_budget,
        "false_routes": used_false,
        "wrong_supported": used_wrong,
        "supported_correct": correct,
        "thresholds": {
            route: {
                "min_schema_score": float(option["min_schema_score"]),
                "min_action_score": float(option["min_action_score"]),
            }
            for route, option in chosen
        },
    }


def _project(
    rows: list[dict[str, Any]],
    *,
    solution: dict[str, Any],
) -> dict[str, Any]:
    thresholds = solution["thresholds"]
    margin_guard = float(solution["margin_guard"])
    accepted: list[dict[str, Any]] = []

    for row in rows:
        if float(row["fused_margin"]) < margin_guard:
            continue
        route = str(row["selected_route"])
        threshold = thresholds.get(route)
        if threshold is None:
            continue
        if float(row["schema_score"]) < float(threshold["min_schema_score"]):
            continue
        if float(row["action_score"]) < float(threshold["min_action_score"]):
            continue
        accepted.append(row)

    supported = [row for row in rows if row.get("expected") is not None]
    near = [
        row for row in rows
        if row.get("category") == "near_domain_unsupported_operation"
    ]
    ood = [row for row in rows if row.get("category") == "out_of_domain"]
    no_route = [row for row in rows if row.get("expected") is None]

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
        "supported_exact_route_accuracy": supported_correct / len(supported),
        "near_domain_unsupported_rejection": 1.0 - near_false / len(near),
        "out_of_domain_rejection": 1.0 - ood_false / len(ood),
        "false_routes": false_routes,
        "false_route_rate": false_routes / len(no_route),
        "wrong_supported": wrong_supported,
        "accepted_total": len(accepted),
    }


def run(cases: list[dict[str, Any]]) -> dict[str, Any]:
    registry = reference_registry()
    catalog = dual._route_catalog(registry)
    route_ids = [str(item["route_id"]) for item in catalog]

    config, static_embedder, query_embedder = screen._build_embedders("bge-m3")
    static_texts = [
        *(str(item["schema_text"]) for item in catalog),
        *(str(item["action_text"]) for item in catalog),
    ]
    static_vectors = static_embedder(static_texts)
    split = len(catalog)
    schema_vectors = static_vectors[:split]
    action_vectors = static_vectors[split:]

    rows: list[dict[str, Any]] = []
    latencies: list[float] = []
    for case in cases:
        started = time.perf_counter_ns()
        query_vector = query_embedder([str(case["query"])])[0]
        schema_scores = [
            dual._cosine(query_vector, vector) for vector in schema_vectors
        ]
        action_scores = [
            dual._cosine(query_vector, vector) for vector in action_vectors
        ]
        fused_scores = [
            SCHEMA_WEIGHT * schema + ACTION_WEIGHT * action
            for schema, action in zip(schema_scores, action_scores, strict=True)
        ]
        top_route, _, _, margin = dual._rank(route_ids, fused_scores)
        winner_index = route_ids.index(top_route)
        latencies.append((time.perf_counter_ns() - started) / 1_000_000)
        rows.append(
            {
                "case_id": case.get("id"),
                "category": case.get("category"),
                "language": case.get("language"),
                "expected": case.get("expected"),
                "selected_route": top_route,
                "schema_score": schema_scores[winner_index],
                "action_score": action_scores[winner_index],
                "fused_margin": margin,
            }
        )

    supported = [row for row in rows if row.get("expected") is not None]
    raw_correct = sum(
        row.get("expected") == row.get("selected_route") for row in supported
    )

    routes = sorted(set(route_ids))
    points: list[dict[str, Any]] = []
    for gate_family in GATE_FAMILIES:
        for margin_guard in MARGIN_GUARDS:
            for false_budget in FALSE_BUDGETS:
                solution = _optimize(
                    rows,
                    routes=routes,
                    gate_family=gate_family,
                    margin_guard=margin_guard,
                    false_budget=false_budget,
                )
                projected = _project(rows, solution=solution)
                points.append({**solution, **projected})

    strict = [point for point in points if int(point["false_budget"]) == 6]
    strict.sort(
        key=lambda item: (
            -float(item["supported_exact_route_accuracy"]),
            int(item["false_routes"]),
            int(item["wrong_supported"]),
            str(item["gate_family"]),
            float(item["margin_guard"]),
        )
    )
    passing = [
        point for point in strict
        if float(point["supported_exact_route_accuracy"]) >= 0.85
        and float(point["near_domain_unsupported_rejection"]) >= 0.97
        and float(point["false_route_rate"]) <= 0.01
    ]

    return {
        "architecture": {
            "model": config,
            "schema_weight": SCHEMA_WEIGHT,
            "action_weight": ACTION_WEIGHT,
            "gate_families": list(GATE_FAMILIES),
            "margin_guards": list(MARGIN_GUARDS),
            "false_budgets": list(FALSE_BUDGETS),
            "behavior_change": False,
        },
        "summary": {
            "cases": len(rows),
            "raw_supported_exact_route_accuracy": raw_correct / len(supported),
            "latency_ms": _distribution(latencies),
            "best_strict": strict[0] if strict else None,
            "strict_gate_pass_count": len(passing),
            "strict_gate_passes": passing,
        },
        "frontier": points,
        "policy": {
            "data_role": "tuning_eligible_development",
            "calibration_or_blind_used": False,
            "full_population_denominators": True,
            "execution_blocked_while_262_active": True,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    cases = json.loads(args.corpus.read_text(encoding="utf-8"))
    if not isinstance(cases, list) or any(not isinstance(item, dict) for item in cases):
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
                "best_strict": result["summary"]["best_strict"],
                "strict_gate_pass_count": result["summary"]["strict_gate_pass_count"],
                "latency": result["summary"]["latency_ms"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
