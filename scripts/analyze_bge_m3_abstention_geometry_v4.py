"""DEV-only native BGE-M3 abstention-geometry rescue diagnostic."""

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

from benchmark_decision_routing import reference_registry  # noqa: E402

from benchmarks.bge_m3_frozen_candidate import (  # noqa: E402
    ACTION_WEIGHT,
    BOUNDARY_EPSILON,
    FROZEN_THRESHOLDS,
    MODEL_NAME,
    MODEL_REVISION,
    SCHEMA_WEIGHT,
    FrozenBgeM3DualViewBackend,
    _cosine,
    _to_vectors,
)

SCORE_SHORTFALL_GRID = (0.001, 0.0025, 0.005, 0.01, 0.02, 0.04)
MARGIN_SHORTFALL_GRID = (0.0, 0.0025, 0.005, 0.01, 0.02)
DISAGREEMENT_GRID = (0.025, 0.05, 0.10, 0.20)
FALSE_BUDGETS = (0, 1, 2, 3)
RULE_FAMILIES = (
    "proximity",
    "proximity_tool_agree",
    "proximity_route_agree",
    "proximity_winner_top1_both",
    "proximity_bounded_view_disagreement",
)


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


def _tool(route: str | None) -> str | None:
    if not isinstance(route, str) or "." not in route:
        return None
    return route.split(".", 1)[0]


def _rank(
    route_ids: list[str],
    scores: list[float],
) -> tuple[str, float, float | None, float]:
    ranked = sorted(
        zip(route_ids, scores, strict=True),
        key=lambda item: (-item[1], item[0]),
    )
    top_route, top_score = ranked[0]
    second_score = ranked[1][1] if len(ranked) > 1 else None
    margin = top_score - second_score if second_score is not None else 2.0
    return top_route, top_score, second_score, margin


def _load_model():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(
        MODEL_NAME,
        revision=MODEL_REVISION,
        trust_remote_code=False,
    )


def _embedder(model: Any):
    def embed(texts: list[str]) -> list[list[float]]:
        vectors = model.encode(
            texts,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return vectors.tolist()

    return embed


def _rule_configs() -> list[dict[str, Any]]:
    configs: list[dict[str, Any]] = []
    for score_shortfall in SCORE_SHORTFALL_GRID:
        for margin_shortfall in MARGIN_SHORTFALL_GRID:
            common = {
                "score_shortfall_max": score_shortfall,
                "margin_shortfall_max": margin_shortfall,
            }
            for family in RULE_FAMILIES[:-1]:
                configs.append(
                    {
                        "family": family,
                        **common,
                        "view_disagreement_max": None,
                    }
                )
            for disagreement in DISAGREEMENT_GRID:
                configs.append(
                    {
                        "family": "proximity_bounded_view_disagreement",
                        **common,
                        "view_disagreement_max": disagreement,
                    }
                )
    return configs


RULE_CONFIGS = _rule_configs()


def _rule_key(config: dict[str, Any]) -> tuple[Any, ...]:
    return (
        str(config["family"]),
        float(config["score_shortfall_max"]),
        float(config["margin_shortfall_max"]),
        (
            None
            if config["view_disagreement_max"] is None
            else float(config["view_disagreement_max"])
        ),
    )


def _passes_rule(row: dict[str, Any], config: dict[str, Any]) -> bool:
    if bool(row["base_accepted"]):
        return False
    if float(row["score_shortfall"]) > float(config["score_shortfall_max"]):
        return False
    if float(row["margin_shortfall"]) > float(config["margin_shortfall_max"]):
        return False

    family = str(config["family"])
    if family == "proximity":
        return True
    if family == "proximity_tool_agree":
        return bool(row["schema_action_top_tool_agree"])
    if family == "proximity_route_agree":
        return bool(row["schema_action_top_route_agree"])
    if family == "proximity_winner_top1_both":
        return bool(row["fused_winner_schema_top1"]) and bool(
            row["fused_winner_action_top1"]
        )
    if family == "proximity_bounded_view_disagreement":
        limit = config["view_disagreement_max"]
        assert limit is not None
        return float(row["winner_view_score_disagreement"]) <= float(limit)
    raise ValueError(f"unknown rule family: {family}")


def _evaluate_rule(
    rows: list[dict[str, Any]],
    config: dict[str, Any],
    *,
    route: str | None = None,
) -> dict[str, Any]:
    eligible = [
        row
        for row in rows
        if not bool(row["base_accepted"])
        and (route is None or row["top_route"] == route)
        and _passes_rule(row, config)
    ]
    additional_correct = sum(
        row["expected"] is not None and row["expected"] == row["top_route"]
        for row in eligible
    )
    additional_false = sum(row["expected"] is None for row in eligible)
    additional_wrong_supported = sum(
        row["expected"] is not None and row["expected"] != row["top_route"]
        for row in eligible
    )
    return {
        "additional_supported_correct": additional_correct,
        "additional_false_routes": additional_false,
        "additional_wrong_supported": additional_wrong_supported,
        "rescued_cases": len(eligible),
    }


def _global_frontier(
    rows: list[dict[str, Any]],
    *,
    false_budget: int,
) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    for config in RULE_CONFIGS:
        counts = _evaluate_rule(rows, config)
        if int(counts["additional_false_routes"]) <= false_budget:
            candidates.append(
                {
                    "rule": config,
                    **counts,
                }
            )

    reject_all = {
        "rule": {
            "family": "reject_all",
            "score_shortfall_max": 0.0,
            "margin_shortfall_max": 0.0,
            "view_disagreement_max": None,
        },
        "additional_supported_correct": 0,
        "additional_false_routes": 0,
        "additional_wrong_supported": 0,
        "rescued_cases": 0,
    }
    candidates.append(reject_all)

    return max(
        candidates,
        key=lambda item: (
            int(item["additional_supported_correct"]),
            -int(item["additional_false_routes"]),
            -int(item["additional_wrong_supported"]),
            -int(item["rescued_cases"]),
            _rule_key(item["rule"]),
        ),
    )


def _route_options(
    rows: list[dict[str, Any]],
    route: str,
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = [
        {
            "rule": {
                "family": "reject_all",
                "score_shortfall_max": 0.0,
                "margin_shortfall_max": 0.0,
                "view_disagreement_max": None,
            },
            "additional_supported_correct": 0,
            "additional_false_routes": 0,
            "additional_wrong_supported": 0,
            "rescued_cases": 0,
        }
    ]
    for config in RULE_CONFIGS:
        candidates.append(
            {
                "rule": config,
                **_evaluate_rule(rows, config, route=route),
            }
        )

    # Keep one strongest rule per (false, wrong) state.
    states: dict[tuple[int, int], dict[str, Any]] = {}
    for candidate in candidates:
        key = (
            int(candidate["additional_false_routes"]),
            int(candidate["additional_wrong_supported"]),
        )
        previous = states.get(key)
        if previous is None or (
            int(candidate["additional_supported_correct"]),
            -int(candidate["rescued_cases"]),
            _rule_key(candidate["rule"]),
        ) > (
            int(previous["additional_supported_correct"]),
            -int(previous["rescued_cases"]),
            _rule_key(previous["rule"]),
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


def _route_local_frontier(
    rows: list[dict[str, Any]],
    routes: list[str],
    *,
    false_budget: int,
) -> dict[str, Any]:
    options = {route: _route_options(rows, route) for route in routes}
    dp: dict[
        tuple[int, int],
        tuple[int, int, list[tuple[str, dict[str, Any]]]],
    ] = {(0, 0): (0, 0, [])}

    for route in routes:
        next_dp: dict[
            tuple[int, int],
            tuple[int, int, list[tuple[str, dict[str, Any]]]],
        ] = {}
        for (used_false, used_wrong), (
            correct,
            rescued,
            selected,
        ) in dp.items():
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
                new_rescued = rescued + int(option["rescued_cases"])
                key = (new_false, new_wrong)
                previous = next_dp.get(key)
                if previous is None or (
                    new_correct,
                    -new_rescued,
                ) > (
                    previous[0],
                    -previous[1],
                ):
                    next_dp[key] = (
                        new_correct,
                        new_rescued,
                        [*selected, (route, option)],
                    )
        dp = next_dp

    if not dp:
        raise RuntimeError(
            f"no route-local rule solution for false budget {false_budget}"
        )

    (used_false, used_wrong), (
        correct,
        rescued,
        selected,
    ) = max(
        dp.items(),
        key=lambda item: (
            item[1][0],
            -item[0][0],
            -item[0][1],
            -item[1][1],
        ),
    )
    return {
        "additional_supported_correct": correct,
        "additional_false_routes": used_false,
        "additional_wrong_supported": used_wrong,
        "rescued_cases": rescued,
        "rules": {
            route: option["rule"]
            for route, option in selected
        },
    }


def _rescued_by_route_rules(
    row: dict[str, Any],
    rules: dict[str, dict[str, Any]],
) -> bool:
    if bool(row["base_accepted"]):
        return False
    config = rules.get(str(row["top_route"]))
    if config is None or config["family"] == "reject_all":
        return False
    return _passes_rule(row, config)


def _compose(
    rows: list[dict[str, Any]],
    *,
    global_rule: dict[str, Any] | None = None,
    route_rules: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if (global_rule is None) == (route_rules is None):
        raise ValueError("provide exactly one rescue mode")

    predictions: list[str | None] = []
    rescued_ids: list[str] = []
    for row in rows:
        if bool(row["base_accepted"]):
            predicted = str(row["top_route"])
        else:
            if global_rule is not None:
                rescue = (
                    global_rule["family"] != "reject_all"
                    and _passes_rule(row, global_rule)
                )
            else:
                assert route_rules is not None
                rescue = _rescued_by_route_rules(row, route_rules)
            predicted = str(row["top_route"]) if rescue else None
            if rescue:
                rescued_ids.append(str(row["case_id"]))
        predictions.append(predicted)

    paired = list(zip(rows, predictions, strict=True))
    supported = [row for row in rows if row["expected"] is not None]
    near = [
        row
        for row in rows
        if row["category"] == "near_domain_unsupported_operation"
    ]
    ood = [row for row in rows if row["category"] == "out_of_domain"]
    no_route = [row for row in rows if row["expected"] is None]

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
        "supported_exact_route_accuracy": (
            supported_correct / len(supported) if supported else 0.0
        ),
        "near_domain_unsupported_rejection": (
            1.0 - near_false / len(near) if near else 1.0
        ),
        "out_of_domain_rejection": (
            1.0 - ood_false / len(ood) if ood else 1.0
        ),
        "false_routes": false_routes,
        "false_route_rate": (
            false_routes / len(no_route) if no_route else 0.0
        ),
        "wrong_supported": wrong_supported,
        "rescued_cases": len(rescued_ids),
        "rescued_case_ids": sorted(rescued_ids),
    }


def evaluate(cases: list[dict[str, Any]]) -> dict[str, Any]:
    registry = reference_registry()
    model = _load_model()
    backend = FrozenBgeM3DualViewBackend(registry, _embedder(model))
    route_ids = list(backend.route_ids)

    rows: list[dict[str, Any]] = []
    latencies: list[float] = []
    for case in cases:
        started = time.perf_counter_ns()
        query_vector = _to_vectors(backend.embedder([str(case["query"])]))[0]

        schema_scores = [
            _cosine(query_vector, backend._schema_vectors[route])
            for route in route_ids
        ]
        action_scores = [
            _cosine(query_vector, backend._action_vectors[route])
            for route in route_ids
        ]
        fused_scores = [
            SCHEMA_WEIGHT * schema_score + ACTION_WEIGHT * action_score
            for schema_score, action_score in zip(
                schema_scores,
                action_scores,
                strict=True,
            )
        ]

        fused = _rank(route_ids, fused_scores)
        schema = _rank(route_ids, schema_scores)
        action = _rank(route_ids, action_scores)

        top_route, top_score, _second_score, top_margin = fused
        boundary = FROZEN_THRESHOLDS[top_route]
        score_shortfall = max(
            0.0,
            float(boundary["min_score"]) - (top_score + BOUNDARY_EPSILON),
        )
        margin_shortfall = max(
            0.0,
            float(boundary["min_margin"]) - (top_margin + BOUNDARY_EPSILON),
        )
        accepted = score_shortfall == 0.0 and margin_shortfall == 0.0

        winner_index = route_ids.index(top_route)
        winner_schema_score = schema_scores[winner_index]
        winner_action_score = action_scores[winner_index]
        latency_ms = (time.perf_counter_ns() - started) / 1_000_000
        latencies.append(latency_ms)

        rows.append(
            {
                "case_id": case.get("id"),
                "query": case.get("query"),
                "category": case.get("category"),
                "language": case.get("language"),
                "unsupported_family": case.get("unsupported_family"),
                "expected": case.get("expected"),
                "top_route": top_route,
                "base_accepted": accepted,
                "fused_top_score": top_score,
                "fused_top_margin": top_margin,
                "min_score": float(boundary["min_score"]),
                "min_margin": float(boundary["min_margin"]),
                "score_shortfall": score_shortfall,
                "margin_shortfall": margin_shortfall,
                "schema_top_route": schema[0],
                "schema_top_score": schema[1],
                "schema_top_margin": schema[3],
                "action_top_route": action[0],
                "action_top_score": action[1],
                "action_top_margin": action[3],
                "schema_action_top_route_agree": schema[0] == action[0],
                "schema_action_top_tool_agree": _tool(schema[0]) == _tool(action[0]),
                "fused_winner_schema_top1": top_route == schema[0],
                "fused_winner_action_top1": top_route == action[0],
                "winner_schema_score": winner_schema_score,
                "winner_action_score": winner_action_score,
                "winner_view_score_disagreement": abs(
                    winner_schema_score - winner_action_score
                ),
            }
        )

    base_metrics = _compose(
        rows,
        route_rules={
            route: {
                "family": "reject_all",
                "score_shortfall_max": 0.0,
                "margin_shortfall_max": 0.0,
                "view_disagreement_max": None,
            }
            for route in route_ids
        },
    )

    abstained = [row for row in rows if not bool(row["base_accepted"])]
    correct_winner_headroom = sum(
        row["expected"] is not None and row["expected"] == row["top_route"]
        for row in abstained
    )

    global_frontier: list[dict[str, Any]] = []
    route_frontier: list[dict[str, Any]] = []
    for false_budget in FALSE_BUDGETS:
        global_solution = _global_frontier(rows, false_budget=false_budget)
        global_metrics = _compose(
            rows,
            global_rule=global_solution["rule"],
        )
        global_frontier.append(
            {
                "additional_false_budget": false_budget,
                **global_solution,
                **global_metrics,
            }
        )

        route_solution = _route_local_frontier(
            rows,
            route_ids,
            false_budget=false_budget,
        )
        route_metrics = _compose(
            rows,
            route_rules=route_solution["rules"],
        )
        route_frontier.append(
            {
                "additional_false_budget": false_budget,
                **route_solution,
                **route_metrics,
            }
        )

    primary = next(
        item
        for item in route_frontier
        if int(item["additional_false_budget"]) == 0
    )
    target_pass = (
        float(primary["supported_exact_route_accuracy"]) >= 0.85
        and float(primary["near_domain_unsupported_rejection"]) >= 0.97
        and float(primary["false_route_rate"]) <= 0.01
        and int(primary["additional_false_routes"]) == 0
    )

    return {
        "experiment": "native-bge-m3-abstention-geometry-rescue-v1",
        "base": {
            "metrics": base_metrics,
            "abstained_cases": len(abstained),
            "correct_winner_headroom": correct_winner_headroom,
            "scoring_latency_ms": _distribution(latencies),
        },
        "rule_grid": {
            "rule_config_count": len(RULE_CONFIGS),
            "families": list(RULE_FAMILIES),
            "score_shortfall_grid": list(SCORE_SHORTFALL_GRID),
            "margin_shortfall_grid": list(MARGIN_SHORTFALL_GRID),
            "view_disagreement_grid": list(DISAGREEMENT_GRID),
        },
        "global_frontier": global_frontier,
        "route_local_frontier": route_frontier,
        "primary_zero_additional_false": primary,
        "primary_target_pass": target_pass,
        "rows": rows,
        "policy": {
            "base_accepted_decisions_changed": False,
            "same_winner_rescue_only": True,
            "rank2_fallback": False,
            "learned_classifier": False,
            "calibration_or_blind_used": False,
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

    result = evaluate(cases)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "base": result["base"],
                "primary_zero_additional_false": result[
                    "primary_zero_additional_false"
                ],
                "primary_target_pass": result["primary_target_pass"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
