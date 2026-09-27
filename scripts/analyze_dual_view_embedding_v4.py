"""DEV-only single-query dual-view embedding diagnostic for operation routing."""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_SCRIPTS_DIR = Path(__file__).resolve().parent
for _path in (_PROJECT_ROOT, _SCRIPTS_DIR):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from benchmark_decision_routing import reference_registry  # noqa: E402

from benchmarks.multilingual_embedder import embed  # noqa: E402

FALSE_BUDGETS = (0, 6, 12, 13, 24, 36)
MARGIN_THRESHOLDS = (0.0, 0.02, 0.05, 0.08, 0.10, 0.15, 0.20)
WEIGHTED_STRATEGIES = {
    "schema_only": 1.0,
    "fusion_schema_0_75": 0.75,
    "fusion_schema_0_50": 0.50,
    "fusion_schema_0_25": 0.25,
    "action_only": 0.0,
}
AGREEMENT_MODES = (
    "none",
    "schema_action_top_tool_agree",
    "schema_action_top_route_agree",
)


def _cosine(left: list[float], right: list[float]) -> float:
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0.0 or right_norm == 0.0:
        raise ValueError("embedding vector must have non-zero norm")
    value = sum(a * b for a, b in zip(left, right, strict=True))
    value /= left_norm * right_norm
    return max(-1.0, min(1.0, value))


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
        "min": min(values) if values else None,
        "p05": _quantile(values, 0.05),
        "p10": _quantile(values, 0.10),
        "p25": _quantile(values, 0.25),
        "p50": _quantile(values, 0.50),
        "p75": _quantile(values, 0.75),
        "p90": _quantile(values, 0.90),
        "p95": _quantile(values, 0.95),
        "max": max(values) if values else None,
        "mean": statistics.fmean(values) if values else None,
    }


def _schema_text(tool: Any, endpoint: Any) -> str:
    route_id = f"{tool.key}.{endpoint.name}"
    field_labels = [
        field.semantic_id or field.name
        for field in endpoint.output_fields
        if not field.identifier
    ]
    parts = [
        route_id,
        tool.description.strip(),
        endpoint.description.strip(),
    ]
    if field_labels:
        parts.append("Fields: " + ", ".join(dict.fromkeys(field_labels)))
    return "\n".join(part for part in parts if part)


def _action_text(endpoint: Any) -> str:
    operation_name = endpoint.name.replace("_", " ").replace("-", " ")
    parts = [
        operation_name,
        *endpoint.operation_aliases,
    ]
    return "\n".join(dict.fromkeys(part for part in parts if part))


def _route_catalog(registry: Any) -> list[dict[str, Any]]:
    routes: list[dict[str, Any]] = []
    for tool in registry.tools():
        for endpoint in tool.endpoints:
            routes.append(
                {
                    "route_id": f"{tool.key}.{endpoint.name}",
                    "tool": tool.key,
                    "endpoint": endpoint.name,
                    "schema_text": _schema_text(tool, endpoint),
                    "action_text": _action_text(endpoint),
                }
            )
    return sorted(routes, key=lambda item: item["route_id"])


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


def _tool(route_id: str | None) -> str | None:
    if not isinstance(route_id, str) or "." not in route_id:
        return None
    return route_id.split(".", 1)[0]


def _factorized(
    catalog: list[dict[str, Any]],
    schema_scores: list[float],
    action_scores: list[float],
) -> dict[str, Any]:
    tool_scores: dict[str, float] = {}
    tool_route_indexes: dict[str, list[int]] = defaultdict(list)
    for index, item in enumerate(catalog):
        tool_name = str(item["tool"])
        tool_route_indexes[tool_name].append(index)
        tool_scores[tool_name] = max(
            tool_scores.get(tool_name, -1.0),
            schema_scores[index],
        )

    ranked_tools = sorted(
        tool_scores.items(),
        key=lambda item: (-item[1], item[0]),
    )
    selected_tool, selected_tool_score = ranked_tools[0]
    second_tool_score = ranked_tools[1][1] if len(ranked_tools) > 1 else None
    tool_margin = (
        selected_tool_score - second_tool_score
        if second_tool_score is not None
        else 2.0
    )

    endpoint_indexes = tool_route_indexes[selected_tool]
    ranked_endpoints = sorted(
        endpoint_indexes,
        key=lambda index: (
            -action_scores[index],
            str(catalog[index]["route_id"]),
        ),
    )
    selected_index = ranked_endpoints[0]
    selected_route = str(catalog[selected_index]["route_id"])
    selected_action_score = action_scores[selected_index]
    second_action_score = (
        action_scores[ranked_endpoints[1]]
        if len(ranked_endpoints) > 1
        else None
    )
    action_margin = (
        selected_action_score - second_action_score
        if second_action_score is not None
        else 2.0
    )
    return {
        "selected_route": selected_route,
        "top_score": min(selected_tool_score, selected_action_score),
        "second_score": None,
        "top_margin": min(tool_margin, action_margin),
        "tool_score": selected_tool_score,
        "tool_margin": tool_margin,
        "action_score": selected_action_score,
        "action_margin": action_margin,
    }


def _agreement_passes(row: dict[str, Any], mode: str) -> bool:
    if mode == "none":
        return True
    if mode == "schema_action_top_tool_agree":
        return bool(row["schema_action_top_tool_agree"])
    if mode == "schema_action_top_route_agree":
        return bool(row["schema_action_top_route_agree"])
    raise ValueError(f"unsupported agreement mode: {mode}")


def _threshold_options(
    rows: list[dict[str, Any]],
    *,
    route: str,
    agreement_mode: str,
) -> list[dict[str, Any]]:
    routed = [
        row
        for row in rows
        if row["selected_route"] == route
        and row.get("top_score") is not None
        and row.get("top_margin") is not None
        and _agreement_passes(row, agreement_mode)
    ]
    scores = sorted({float(row["top_score"]) for row in routed})
    thresholds = [-1.0, *scores, 1.000001]

    states: dict[tuple[int, int], dict[str, Any]] = {}
    for score_threshold in thresholds:
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
                "min_score": score_threshold,
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
                float(previous["min_score"]),
                float(previous["min_margin"]),
            ):
                states[key] = candidate

    candidates = list(states.values())
    result: list[dict[str, Any]] = []
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
            result.append(candidate)
    return result


def _optimize_thresholds(
    rows: list[dict[str, Any]],
    *,
    routes: list[str],
    agreement_mode: str,
    false_budget: int,
) -> dict[str, Any]:
    route_options = {
        route: _threshold_options(
            rows,
            route=route,
            agreement_mode=agreement_mode,
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
            for option in route_options[route]:
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
        raise ValueError(
            f"no threshold solution for agreement={agreement_mode!r}, "
            f"false_budget={false_budget}"
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
        "false_budget": false_budget,
        "false_routes": used_false,
        "wrong_supported": used_wrong,
        "supported_correct": supported_correct,
        "thresholds": {
            route: {
                "min_score": float(option["min_score"]),
                "min_margin": float(option["min_margin"]),
            }
            for route, option in chosen
        },
    }


def _project(
    rows: list[dict[str, Any]],
    *,
    thresholds: dict[str, dict[str, float]],
    agreement_mode: str,
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
        if not _agreement_passes(row, agreement_mode):
            continue
        route = row.get("selected_route")
        if not isinstance(route, str):
            continue
        threshold = thresholds.get(route)
        if threshold is None:
            continue
        if (
            float(row["top_score"]) >= threshold["min_score"]
            and float(row["top_margin"]) >= threshold["min_margin"]
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
        "supported_exact_route_accuracy": (
            supported_correct / len(supported) if supported else 0.0
        ),
        "near_domain_unsupported_rejection": (
            1.0 - near_false / len(near) if near else 1.0
        ),
        "out_of_domain_rejection": (
            1.0 - ood_false / len(ood) if ood else 1.0
        ),
        "canonical_false_route_rate": (
            false_routes / len(no_route) if no_route else 0.0
        ),
        "false_routes": false_routes,
        "wrong_supported": wrong_supported,
        "supported_correct": supported_correct,
        "accepted_total": len(accepted),
    }


def _raw_profile(rows: list[dict[str, Any]]) -> dict[str, Any]:
    supported = [row for row in rows if row.get("expected") is not None]
    exact = sum(
        row.get("selected_route") == row.get("expected")
        for row in supported
    )
    wrong_tool = 0
    wrong_endpoint = 0
    for row in supported:
        expected = str(row["expected"])
        predicted = str(row["selected_route"])
        if _tool(expected) != _tool(predicted):
            wrong_tool += 1
        elif expected != predicted:
            wrong_endpoint += 1

    language: dict[str, Any] = {}
    for name in sorted({str(row["language"]) for row in supported}):
        group = [row for row in supported if row.get("language") == name]
        correct = sum(
            row.get("selected_route") == row.get("expected")
            for row in group
        )
        language[name] = {
            "cases": len(group),
            "exact_route_accuracy": correct / len(group),
        }

    route: dict[str, Any] = {}
    for name in sorted({str(row["expected"]) for row in supported}):
        group = [row for row in supported if row.get("expected") == name]
        correct = sum(
            row.get("selected_route") == name
            for row in group
        )
        route[name] = {
            "cases": len(group),
            "exact_route_accuracy": correct / len(group),
        }

    return {
        "supported_exact_route_accuracy": exact / len(supported),
        "wrong_tool": wrong_tool,
        "wrong_endpoint": wrong_endpoint,
        "top_score": _distribution(
            [float(row["top_score"]) for row in rows]
        ),
        "top_margin": _distribution(
            [float(row["top_margin"]) for row in rows]
        ),
        "language": language,
        "route": route,
    }


def _screening_passes(item: dict[str, Any]) -> bool:
    return (
        float(item["supported_exact_route_accuracy"]) >= 0.70
        and float(item["near_domain_unsupported_rejection"]) >= 0.96
        and float(item["canonical_false_route_rate"]) <= 0.02
    )


def analyze(
    cases: list[dict[str, Any]],
    *,
    static_embedder: Any = embed,
    query_embedder: Any = embed,
) -> dict[str, Any]:
    registry = reference_registry()
    catalog = _route_catalog(registry)
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

    strategy_rows: dict[str, list[dict[str, Any]]] = {
        **{name: [] for name in WEIGHTED_STRATEGIES},
        "factorized_tool_action": [],
    }
    query_latencies: list[float] = []

    for case in cases:
        query = str(case["query"])
        started = time.perf_counter_ns()
        query_vector = query_embedder([query])[0]
        schema_scores = [
            _cosine(query_vector, vector)
            for vector in schema_vectors
        ]
        action_scores = [
            _cosine(query_vector, vector)
            for vector in action_vectors
        ]

        schema_top = _rank(route_ids, schema_scores)
        action_top = _rank(route_ids, action_scores)
        top_route_agree = schema_top[0] == action_top[0]
        top_tool_agree = _tool(schema_top[0]) == _tool(action_top[0])

        common = {
            "case_id": case.get("id"),
            "category": case.get("category"),
            "language": case.get("language"),
            "unsupported_family": case.get("unsupported_family"),
            "expected": case.get("expected"),
            "schema_top_route": schema_top[0],
            "action_top_route": action_top[0],
            "schema_action_top_route_agree": top_route_agree,
            "schema_action_top_tool_agree": top_tool_agree,
        }

        for name, schema_weight in WEIGHTED_STRATEGIES.items():
            action_weight = 1.0 - schema_weight
            fused = [
                schema_weight * schema_score + action_weight * action_score
                for schema_score, action_score in zip(
                    schema_scores,
                    action_scores,
                    strict=True,
                )
            ]
            top_route, top_score, second_score, top_margin = _rank(
                route_ids,
                fused,
            )
            strategy_rows[name].append(
                {
                    **common,
                    "strategy": name,
                    "selected_route": top_route,
                    "top_score": top_score,
                    "second_score": second_score,
                    "top_margin": top_margin,
                }
            )

        factorized = _factorized(
            catalog,
            schema_scores,
            action_scores,
        )
        strategy_rows["factorized_tool_action"].append(
            {
                **common,
                "strategy": "factorized_tool_action",
                **factorized,
            }
        )
        query_latencies.append(
            (time.perf_counter_ns() - started) / 1_000_000
        )

    raw_profiles = {
        name: _raw_profile(rows)
        for name, rows in strategy_rows.items()
    }

    frontiers: dict[str, dict[str, list[dict[str, Any]]]] = {}
    canonical_candidates: list[dict[str, Any]] = []
    for strategy, rows in strategy_rows.items():
        routes = sorted(
            {
                str(row["selected_route"])
                for row in rows
                if isinstance(row.get("selected_route"), str)
            }
        )
        frontiers[strategy] = {}
        for agreement_mode in AGREEMENT_MODES:
            points: list[dict[str, Any]] = []
            for false_budget in FALSE_BUDGETS:
                solution = _optimize_thresholds(
                    rows,
                    routes=routes,
                    agreement_mode=agreement_mode,
                    false_budget=false_budget,
                )
                projected = _project(
                    rows,
                    thresholds=solution["thresholds"],
                    agreement_mode=agreement_mode,
                )
                point = {
                    "strategy": strategy,
                    "agreement_mode": agreement_mode,
                    **solution,
                    **projected,
                }
                points.append(point)
                if false_budget == 12:
                    canonical_candidates.append(point)
            frontiers[strategy][agreement_mode] = points

    canonical_candidates.sort(
        key=lambda item: (
            -float(item["supported_exact_route_accuracy"]),
            int(item["false_routes"]),
            int(item["wrong_supported"]),
            str(item["strategy"]),
            str(item["agreement_mode"]),
        )
    )
    passing = [
        item for item in canonical_candidates
        if _screening_passes(item)
    ]

    agreement_rows = next(iter(strategy_rows.values()))
    route_agreement_rate = statistics.fmean(
        float(row["schema_action_top_route_agree"])
        for row in agreement_rows
    )
    tool_agreement_rate = statistics.fmean(
        float(row["schema_action_top_tool_agree"])
        for row in agreement_rows
    )

    return {
        "architecture": {
            "model": (
                "sentence-transformers/"
                "paraphrase-multilingual-MiniLM-L12-v2"
            ),
            "query_embeddings_per_case": 1,
            "registered_route_count": len(catalog),
            "static_view_count": len(static_texts),
            "behavior_change": False,
        },
        "summary": {
            "cases": len(cases),
            "static_route_view_embedding_ms": static_ms,
            "query_embedding_plus_all_scoring_latency_ms": _distribution(
                query_latencies
            ),
            "schema_action_top_route_agreement_rate": route_agreement_rate,
            "schema_action_top_tool_agreement_rate": tool_agreement_rate,
            "raw_profiles": raw_profiles,
            "best_canonical_false_budget_12": (
                canonical_candidates[0]
                if canonical_candidates
                else None
            ),
            "screening_gate_pass_count": len(passing),
            "screening_gate_passes": passing,
        },
        "winner_only_route_local_frontiers": frontiers,
        "canonical_false_budget_12": canonical_candidates,
        "policy": {
            "data_role": "tuning_eligible_development",
            "calibration_or_blind_used": False,
            "full_population_denominators": True,
            "note": (
                "All threshold maps are retrospective DEV evidence. "
                "A separate preregistered execution is required before promotion."
            ),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    value = json.loads(args.corpus.read_text(encoding="utf-8"))
    if not isinstance(value, list) or any(
        not isinstance(item, dict) for item in value
    ):
        raise ValueError("corpus must be a JSON object list")

    result = analyze(value)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "latency": result["summary"][
                    "query_embedding_plus_all_scoring_latency_ms"
                ],
                "route_agreement": result["summary"][
                    "schema_action_top_route_agreement_rate"
                ],
                "tool_agreement": result["summary"][
                    "schema_action_top_tool_agreement_rate"
                ],
                "best_canonical": result["summary"][
                    "best_canonical_false_budget_12"
                ],
                "screening_gate_pass_count": result["summary"][
                    "screening_gate_pass_count"
                ],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
