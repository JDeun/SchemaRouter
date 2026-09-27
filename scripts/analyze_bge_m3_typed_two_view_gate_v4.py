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

MODEL_ID = "bge-m3"
MODEL_REVISION = "5617a9f61b028005a4858fdac845db406aefb181"
SCHEMA_WEIGHT = 0.25
ACTION_WEIGHT = 0.75
MARGIN_GUARDS = (0.00, 0.01, 0.02, 0.05)
FALSE_BUDGETS = (0, 3, 6, 12, 13, 24)
GATE_FAMILIES = ("action_only", "schema_only", "typed_and")


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


def _accepts(
    row: dict[str, Any],
    *,
    family: str,
    threshold: dict[str, float],
    margin_guard: float,
) -> bool:
    if float(row["fused_margin"]) < margin_guard:
        return False
    if family == "action_only":
        return float(row["action_score"]) >= threshold["min_action_score"]
    if family == "schema_only":
        return float(row["schema_score"]) >= threshold["min_schema_score"]
    if family == "typed_and":
        return (
            float(row["schema_score"]) >= threshold["min_schema_score"]
            and float(row["action_score"]) >= threshold["min_action_score"]
        )
    raise ValueError(f"unknown gate family: {family}")


def _state_counts(
    routed: list[dict[str, Any]],
    *,
    family: str,
    threshold: dict[str, float],
    margin_guard: float,
) -> tuple[int, int, int]:
    supported_correct = 0
    false_routes = 0
    wrong_supported = 0
    for row in routed:
        if not _accepts(
            row,
            family=family,
            threshold=threshold,
            margin_guard=margin_guard,
        ):
            continue
        expected = row.get("expected")
        if expected == row["selected_route"]:
            supported_correct += 1
        elif expected is None:
            false_routes += 1
        else:
            wrong_supported += 1
    return supported_correct, false_routes, wrong_supported


def _route_options(
    rows: list[dict[str, Any]],
    *,
    route: str,
    family: str,
    margin_guard: float,
) -> list[dict[str, Any]]:
    routed = [row for row in rows if row["selected_route"] == route]

    schema_values = sorted({float(row["schema_score"]) for row in routed})
    action_values = sorted({float(row["action_score"]) for row in routed})
    schema_thresholds = [-1.0, *schema_values, 1.000001]
    action_thresholds = [-1.0, *action_values, 1.000001]

    thresholds: list[dict[str, float]] = []
    if family == "action_only":
        thresholds = [
            {"min_action_score": value}
            for value in action_thresholds
        ]
    elif family == "schema_only":
        thresholds = [
            {"min_schema_score": value}
            for value in schema_thresholds
        ]
    elif family == "typed_and":
        thresholds = [
            {
                "min_schema_score": schema_value,
                "min_action_score": action_value,
            }
            for schema_value in schema_thresholds
            for action_value in action_thresholds
        ]
    else:
        raise ValueError(f"unknown gate family: {family}")

    # Collapse thresholds with identical outcome counts, then prune dominated states.
    states: dict[tuple[int, int], dict[str, Any]] = {}
    for threshold in thresholds:
        supported_correct, false_routes, wrong_supported = _state_counts(
            routed,
            family=family,
            threshold=threshold,
            margin_guard=margin_guard,
        )
        key = (false_routes, wrong_supported)
        candidate = {
            "threshold": threshold,
            "supported_correct": supported_correct,
            "false_routes": false_routes,
            "wrong_supported": wrong_supported,
        }
        previous = states.get(key)
        if previous is None or supported_correct > int(previous["supported_correct"]):
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
    family: str,
    margin_guard: float,
    false_budget: int,
) -> dict[str, Any]:
    options = {
        route: _route_options(
            rows,
            route=route,
            family=family,
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
        for (used_false, used_wrong), (supported_correct, chosen) in dp.items():
            for option in options[route]:
                new_false = used_false + int(option["false_routes"])
                if new_false > false_budget:
                    continue
                new_wrong = used_wrong + int(option["wrong_supported"])
                new_correct = supported_correct + int(option["supported_correct"])
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
            f"no threshold solution for family={family}, "
            f"margin={margin_guard}, budget={false_budget}"
        )

    (used_false, used_wrong), (supported_correct, chosen) = max(
        dp.items(),
        key=lambda item: (
            item[1][0],
            -item[0][0],
            -item[0][1],
        ),
    )
    return {
        "family": family,
        "fused_margin_guard": margin_guard,
        "false_budget": false_budget,
        "false_routes": used_false,
        "wrong_supported": used_wrong,
        "supported_correct": supported_correct,
        "thresholds": {
            route: option["threshold"]
            for route, option in chosen
        },
    }


def _project(
    rows: list[dict[str, Any]],
    *,
    family: str,
    margin_guard: float,
    thresholds: dict[str, dict[str, float]],
) -> dict[str, Any]:
    supported = [row for row in rows if row.get("expected") is not None]
    near = [
        row
        for row in rows
        if row.get("category") == "near_domain_unsupported_operation"
    ]
    ood = [row for row in rows if row.get("category") == "out_of_domain"]
    no_route = [row for row in rows if row.get("expected") is None]

    accepted: list[dict[str, Any]] = []
    for row in rows:
        threshold = thresholds.get(str(row["selected_route"]))
        if threshold is None:
            continue
        if _accepts(
            row,
            family=family,
            threshold=threshold,
            margin_guard=margin_guard,
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
        "supported_exact_route_accuracy": supported_correct / len(supported),
        "near_domain_unsupported_rejection": 1.0 - near_false / len(near),
        "out_of_domain_rejection": 1.0 - ood_false / len(ood),
        "canonical_false_route_rate": false_routes / len(no_route),
        "supported_correct": supported_correct,
        "wrong_supported": wrong_supported,
        "false_routes": false_routes,
        "accepted_total": len(accepted),
    }


def run(cases: list[dict[str, Any]]) -> dict[str, Any]:
    config, static_embedder, query_embedder = screen._build_embedders(MODEL_ID)
    if config.get("revision") != MODEL_REVISION:
        raise RuntimeError(
            f"unexpected BGE-M3 revision: {config.get('revision')!r}"
        )

    registry = reference_registry()
    catalog = dual._route_catalog(registry)
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
        schema_scores = [
            dual._cosine(query_vector, vector)
            for vector in schema_vectors
        ]
        action_scores = [
            dual._cosine(query_vector, vector)
            for vector in action_vectors
        ]
        fused_scores = [
            SCHEMA_WEIGHT * schema_score + ACTION_WEIGHT * action_score
            for schema_score, action_score in zip(
                schema_scores,
                action_scores,
                strict=True,
            )
        ]
        top_route, top_score, second_score, fused_margin = dual._rank(
            route_ids,
            fused_scores,
        )
        winner_index = route_ids.index(top_route)
        latencies.append(
            (time.perf_counter_ns() - started) / 1_000_000
        )
        rows.append(
            {
                "case_id": case.get("id"),
                "category": case.get("category"),
                "language": case.get("language"),
                "unsupported_family": case.get("unsupported_family"),
                "expected": case.get("expected"),
                "selected_route": top_route,
                "fused_score": top_score,
                "fused_second_score": second_score,
                "fused_margin": fused_margin,
                "schema_score": schema_scores[winner_index],
                "action_score": action_scores[winner_index],
                "rank_correct": top_route == case.get("expected"),
            }
        )

    supported = [row for row in rows if row.get("expected") is not None]
    raw_correct = sum(bool(row["rank_correct"]) for row in supported)
    routes = sorted({str(row["selected_route"]) for row in rows})

    frontiers: dict[str, dict[str, list[dict[str, Any]]]] = {}
    primary: list[dict[str, Any]] = []
    secondary: list[dict[str, Any]] = []

    for family in GATE_FAMILIES:
        frontiers[family] = {}
        for margin_guard in MARGIN_GUARDS:
            points: list[dict[str, Any]] = []
            for false_budget in FALSE_BUDGETS:
                solution = _optimize(
                    rows,
                    routes=routes,
                    family=family,
                    margin_guard=margin_guard,
                    false_budget=false_budget,
                )
                projected = _project(
                    rows,
                    family=family,
                    margin_guard=margin_guard,
                    thresholds=solution["thresholds"],
                )
                point = {**solution, **projected}
                points.append(point)
                if false_budget == 6:
                    primary.append(point)
                elif false_budget == 12:
                    secondary.append(point)
            frontiers[family][f"{margin_guard:.2f}"] = points

    def _sort_key(item: dict[str, Any]) -> tuple[Any, ...]:
        return (
            -float(item["supported_exact_route_accuracy"]),
            int(item["false_routes"]),
            int(item["wrong_supported"]),
            str(item["family"]),
            float(item["fused_margin_guard"]),
        )

    primary.sort(key=_sort_key)
    secondary.sort(key=_sort_key)
    latency = _distribution(latencies)
    p95 = latency["p95"]
    passing = [
        item
        for item in primary
        if float(item["supported_exact_route_accuracy"]) >= 0.85
        and float(item["near_domain_unsupported_rejection"]) >= 0.97
        and float(item["canonical_false_route_rate"]) <= 0.01
        and p95 is not None
        and float(p95) <= 250.0
    ]

    return {
        "architecture": {
            "model_id": MODEL_ID,
            "model_name": config["model_name"],
            "model_revision": config["revision"],
            "schema_weight": SCHEMA_WEIGHT,
            "action_weight": ACTION_WEIGHT,
            "gate_families": list(GATE_FAMILIES),
            "margin_guards": list(MARGIN_GUARDS),
            "behavior_change": False,
        },
        "summary": {
            "cases": len(rows),
            "raw_supported_exact_route_accuracy": raw_correct / len(supported),
            "query_embedding_plus_scoring_latency_ms": latency,
            "static_route_view_embedding_ms": static_ms,
            "best_primary_budget_6": primary[0] if primary else None,
            "best_secondary_budget_12": secondary[0] if secondary else None,
            "strict_gate_pass_count": len(passing),
            "strict_gate_passes": passing,
        },
        "frontiers": frontiers,
        "policy": {
            "data_role": "tuning_eligible_development",
            "calibration_or_blind_used": False,
            "full_population_denominators": True,
            "thresholds_are_diagnostic_only": True,
            "future_freeze_policy_issue": 253,
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
                "best_primary_budget_6": result["summary"][
                    "best_primary_budget_6"
                ],
                "best_secondary_budget_12": result["summary"][
                    "best_secondary_budget_12"
                ],
                "strict_gate_pass_count": result["summary"][
                    "strict_gate_pass_count"
                ],
                "latency": result["summary"][
                    "query_embedding_plus_scoring_latency_ms"
                ],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
