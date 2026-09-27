"""DEV-only zero-additional-false rescue diagnostic over the strict BGE-M3 base."""

from __future__ import annotations

import argparse
import gc
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

from benchmarks.bge_winner_validator import (  # noqa: E402
    MAX_LENGTH as VALIDATOR_MAX_LENGTH,
)
from benchmarks.bge_winner_validator import (  # noqa: E402
    MODEL_NAME as VALIDATOR_MODEL_NAME,
)
from benchmarks.bge_winner_validator import (  # noqa: E402
    MODEL_REVISION as VALIDATOR_MODEL_REVISION,
)
from benchmarks.bge_winner_validator import score_pair, score_pairs, unload  # noqa: E402

RANKER_MODEL_NAME = "BAAI/bge-m3"
RANKER_MODEL_REVISION = "5617a9f61b028005a4858fdac845db406aefb181"
SCHEMA_WEIGHT = 0.55
ACTION_WEIGHT = 0.45
RESCUE_FALSE_BUDGETS = (0, 1, 2, 3)

BASE_THRESHOLDS: dict[str, dict[str, float]] = {
    "calendar.create": {"min_score": 0.5207915599172316, "min_margin": 0.0},
    "calendar.list": {"min_score": 0.5549226120493271, "min_margin": 0.0},
    "finance.history": {"min_score": 0.44227107387387427, "min_margin": 0.0},
    "finance.quote": {"min_score": 0.4893408565908712, "min_margin": 0.02},
    "inventory.search": {"min_score": 0.5359938169033298, "min_margin": 0.0},
    "inventory.update": {"min_score": 0.5376021992095548, "min_margin": 0.0},
    "materials.search": {"min_score": 0.44967027419294425, "min_margin": 0.0},
    "materials.structure": {"min_score": 0.42728435995293546, "min_margin": 0.0},
    "papers.citations": {"min_score": 0.46196385844297233, "min_margin": 0.0},
    "papers.search": {"min_score": 0.4590736815129689, "min_margin": 0.0},
    "support.create_ticket": {"min_score": 0.5326329467130329, "min_margin": 0.0},
    "support.search": {"min_score": 0.4830030958690135, "min_margin": 0.0},
    "users.lookup": {"min_score": 0.49123020769781134, "min_margin": 0.0},
    "users.update": {"min_score": 0.5230594574881653, "min_margin": 0.0},
    "weather.current": {"min_score": 0.5397048468861396, "min_margin": 0.02},
    "weather.forecast": {"min_score": 0.5050024291985815, "min_margin": 0.0},
}


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
        "p50": _quantile(values, 0.50),
        "p90": _quantile(values, 0.90),
        "p95": _quantile(values, 0.95),
        "max": max(values) if values else None,
        "mean": statistics.fmean(values) if values else None,
    }


def _catalog(registry: Any) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    for tool in registry.tools():
        for endpoint in tool.endpoints:
            action_text = dual._action_text(endpoint)
            capability_text = "\n".join(
                part
                for part in [action_text, endpoint.description.strip()]
                if part
            )
            items.append(
                {
                    "route_id": f"{tool.key}.{endpoint.name}",
                    "schema_text": dual._schema_text(tool, endpoint),
                    "action_text": action_text,
                    "validator_text": capability_text,
                }
            )
    items.sort(key=lambda item: item["route_id"])
    return items


def _base_rows(cases: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    registry = reference_registry()
    catalog = _catalog(registry)
    route_ids = [item["route_id"] for item in catalog]

    if set(route_ids) != set(BASE_THRESHOLDS):
        raise RuntimeError(
            "registered route set does not match frozen #246 threshold profile"
        )

    config, static_embedder, query_embedder = screen._build_embedders("bge-m3")
    if config["model_name"] != RANKER_MODEL_NAME:
        raise RuntimeError("unexpected ranker model")
    if config["revision"] != RANKER_MODEL_REVISION:
        raise RuntimeError("unexpected ranker revision")

    static_texts = [
        *(item["schema_text"] for item in catalog),
        *(item["action_text"] for item in catalog),
    ]
    static_started = time.perf_counter_ns()
    static_vectors = static_embedder(static_texts)
    static_latency_ms = (time.perf_counter_ns() - static_started) / 1_000_000
    split = len(catalog)
    schema_vectors = static_vectors[:split]
    action_vectors = static_vectors[split:]

    rows: list[dict[str, Any]] = []
    base_latencies: list[float] = []

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
        top_route, top_score, second_score, top_margin = dual._rank(
            route_ids,
            fused_scores,
        )
        latency_ms = (time.perf_counter_ns() - started) / 1_000_000
        base_latencies.append(latency_ms)

        boundary = BASE_THRESHOLDS[top_route]
        accepted = (
            float(top_score) >= float(boundary["min_score"])
            and float(top_margin) >= float(boundary["min_margin"])
        )
        winner_index = route_ids.index(top_route)
        rows.append(
            {
                "case_id": case.get("id"),
                "query": case.get("query"),
                "category": case.get("category"),
                "language": case.get("language"),
                "unsupported_family": case.get("unsupported_family"),
                "expected": case.get("expected"),
                "top_route": top_route,
                "base_top_score": float(top_score),
                "base_second_score": (
                    float(second_score) if second_score is not None else None
                ),
                "base_top_margin": float(top_margin),
                "base_min_score": float(boundary["min_score"]),
                "base_min_margin": float(boundary["min_margin"]),
                "base_accepted": accepted,
                "validator_surface": catalog[winner_index]["validator_text"],
                "base_latency_ms": latency_ms,
            }
        )

    # Release the ~0.6B embedding model before loading the cross-encoder.
    del static_vectors
    del schema_vectors
    del action_vectors
    del static_embedder
    del query_embedder
    gc.collect()

    return rows, {
        "model": RANKER_MODEL_NAME,
        "revision": RANKER_MODEL_REVISION,
        "schema_weight": SCHEMA_WEIGHT,
        "action_weight": ACTION_WEIGHT,
        "static_route_embedding_ms": static_latency_ms,
        "latency_ms": _distribution(base_latencies),
    }


def _global_frontier(
    rows: list[dict[str, Any]],
    *,
    false_budget: int,
) -> dict[str, Any]:
    rejected = [row for row in rows if not row["base_accepted"]]
    scores = sorted({float(row["validator_score"]) for row in rejected})
    thresholds = [0.0, *scores, math.nextafter(1.0, math.inf)]

    candidates: list[dict[str, Any]] = []
    for threshold in thresholds:
        rescued = [
            row for row in rejected
            if float(row["validator_score"]) >= threshold
        ]
        extra_correct = sum(
            row["expected"] is not None
            and row["expected"] == row["top_route"]
            for row in rescued
        )
        extra_false = sum(row["expected"] is None for row in rescued)
        extra_wrong_supported = sum(
            row["expected"] is not None
            and row["expected"] != row["top_route"]
            for row in rescued
        )
        if extra_false <= false_budget:
            candidates.append(
                {
                    "threshold": threshold,
                    "additional_supported_correct": extra_correct,
                    "additional_false_routes": extra_false,
                    "additional_wrong_supported": extra_wrong_supported,
                }
            )

    if not candidates:
        raise RuntimeError(
            f"no global rescue threshold for false budget {false_budget}"
        )

    return max(
        candidates,
        key=lambda item: (
            int(item["additional_supported_correct"]),
            -int(item["additional_false_routes"]),
            -int(item["additional_wrong_supported"]),
            -float(item["threshold"]),
        ),
    )


def _route_threshold_options(
    rows: list[dict[str, Any]],
    route: str,
) -> list[dict[str, Any]]:
    routed = [
        row
        for row in rows
        if not row["base_accepted"] and row["top_route"] == route
    ]
    scores = sorted({float(row["validator_score"]) for row in routed})
    thresholds = [0.0, *scores, math.nextafter(1.0, math.inf)]
    states: dict[tuple[int, int], dict[str, Any]] = {}

    for threshold in thresholds:
        rescued = [
            row for row in routed
            if float(row["validator_score"]) >= threshold
        ]
        extra_correct = sum(
            row["expected"] == route
            for row in rescued
            if row["expected"] is not None
        )
        extra_false = sum(row["expected"] is None for row in rescued)
        extra_wrong_supported = sum(
            row["expected"] is not None and row["expected"] != route
            for row in rescued
        )
        key = (extra_false, extra_wrong_supported)
        candidate = {
            "threshold": threshold,
            "additional_supported_correct": extra_correct,
            "additional_false_routes": extra_false,
            "additional_wrong_supported": extra_wrong_supported,
        }
        previous = states.get(key)
        if previous is None or (
            extra_correct,
            threshold,
        ) > (
            int(previous["additional_supported_correct"]),
            float(previous["threshold"]),
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
    options = {
        route: _route_threshold_options(rows, route)
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
                new_wrong = (
                    used_wrong + int(option["additional_wrong_supported"])
                )
                new_correct = (
                    correct + int(option["additional_supported_correct"])
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
        raise RuntimeError(
            f"no route-local rescue solution for false budget {false_budget}"
        )

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
            route: float(option["threshold"])
            for route, option in selected
        },
    }


def _compose_metrics(
    rows: list[dict[str, Any]],
    *,
    global_threshold: float | None = None,
    route_thresholds: dict[str, float] | None = None,
) -> dict[str, Any]:
    if (global_threshold is None) == (route_thresholds is None):
        raise ValueError("provide exactly one rescue threshold mode")

    supported = [row for row in rows if row["expected"] is not None]
    near = [
        row
        for row in rows
        if row["category"] == "near_domain_unsupported_operation"
    ]
    ood = [
        row for row in rows
        if row["category"] == "out_of_domain"
    ]
    no_route = [row for row in rows if row["expected"] is None]

    paired: list[tuple[dict[str, Any], str | None]] = []
    rescued_ids: list[str] = []
    for row in rows:
        predicted = str(row["top_route"]) if row["base_accepted"] else None
        if not row["base_accepted"]:
            if global_threshold is not None:
                rescue = float(row["validator_score"]) >= global_threshold
            else:
                assert route_thresholds is not None
                threshold = route_thresholds.get(
                    str(row["top_route"]),
                    math.inf,
                )
                rescue = float(row["validator_score"]) >= threshold
            if rescue:
                predicted = str(row["top_route"])
                rescued_ids.append(str(row["case_id"]))
        paired.append((row, predicted))

    supported_correct = sum(
        predicted == row["expected"]
        for row, predicted in paired
        if row["expected"] is not None
    )
    wrong_supported = sum(
        predicted is not None
        and row["expected"] is not None
        and predicted != row["expected"]
        for row, predicted in paired
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
    rows, base_runtime = _base_rows(cases)
    routes = sorted(BASE_THRESHOLDS)

    # Load the validator only after the embedding model has been released.
    rejected = [row for row in rows if not row["base_accepted"]]
    validator_latencies: list[float] = []
    for row in rejected:
        started = time.perf_counter_ns()
        score = score_pair(
            str(row["query"]),
            str(row["validator_surface"]),
        )
        latency_ms = (time.perf_counter_ns() - started) / 1_000_000
        row["validator_score"] = score
        row["validator_latency_ms"] = latency_ms
        validator_latencies.append(latency_ms)

    for row in rows:
        if row["base_accepted"]:
            row["validator_score"] = None
            row["validator_latency_ms"] = 0.0

    batch_sample = sorted(
        rejected,
        key=lambda row: str(row["case_id"]),
    )[: min(128, len(rejected))]
    batch_pairs = [
        (str(row["query"]), str(row["validator_surface"]))
        for row in batch_sample
    ]
    batch_started = time.perf_counter_ns()
    batch_scores = score_pairs(batch_pairs) if batch_pairs else []
    batch_latency_ms = (
        (time.perf_counter_ns() - batch_started) / 1_000_000
        if batch_pairs
        else 0.0
    )
    if len(batch_scores) != len(batch_pairs):
        raise RuntimeError("validator batch score count mismatch")

    base_metrics = _compose_metrics(
        rows,
        route_thresholds={route: math.inf for route in routes},
    )

    global_frontier: list[dict[str, Any]] = []
    route_frontier: list[dict[str, Any]] = []
    for budget in RESCUE_FALSE_BUDGETS:
        global_solution = _global_frontier(rows, false_budget=budget)
        global_metrics = _compose_metrics(
            rows,
            global_threshold=float(global_solution["threshold"]),
        )
        global_frontier.append(
            {
                "rescue_false_budget": budget,
                **global_solution,
                **global_metrics,
            }
        )

        route_solution = _route_local_frontier(
            rows,
            routes,
            false_budget=budget,
        )
        route_metrics = _compose_metrics(
            rows,
            route_thresholds=route_solution["thresholds"],
        )
        route_frontier.append(
            {
                "rescue_false_budget": budget,
                **route_solution,
                **route_metrics,
            }
        )

    primary = next(
        item
        for item in route_frontier
        if int(item["rescue_false_budget"]) == 0
    )

    base_latencies = [float(row["base_latency_ms"]) for row in rows]
    composed_latencies = [
        float(row["base_latency_ms"])
        + (
            float(row["validator_latency_ms"])
            if not row["base_accepted"]
            else 0.0
        )
        for row in rows
    ]

    supported_rejected_correct_winner = sum(
        not row["base_accepted"]
        and row["expected"] is not None
        and row["expected"] == row["top_route"]
        for row in rows
    )

    primary_target_pass = (
        float(primary["supported_exact_route_accuracy"]) >= 0.85
        and float(primary["near_domain_unsupported_rejection"]) >= 0.97
        and float(primary["false_route_rate"]) <= 0.01
        and int(primary["additional_false_routes"]) == 0
    )

    return {
        "experiment": "bge-m3-strict-base-zero-false-rescue-v1",
        "base": {
            **base_runtime,
            "threshold_profile_source": {
                "issue": 246,
                "workflow_run_id": 36324755106,
                "artifact_id": 10934145256,
                "artifact_sha256": (
                    "60dfbb1d32f1f27873bd8fad4aa4888af80856365196e3ab6fb5be6b1e7f0af7"
                ),
            },
            "thresholds": BASE_THRESHOLDS,
            "metrics": base_metrics,
            "rejected_cases": len(rejected),
            "validator_invocation_rate": len(rejected) / len(rows),
            "supported_rejected_correct_winner_headroom": (
                supported_rejected_correct_winner
            ),
        },
        "validator": {
            "model": VALIDATOR_MODEL_NAME,
            "revision": VALIDATOR_MODEL_REVISION,
            "max_length": VALIDATOR_MAX_LENGTH,
            "surface": (
                "action_name_plus_aliases_plus_endpoint_description"
            ),
            "per_invocation_latency_ms": _distribution(validator_latencies),
            "batch_sample_cases": len(batch_pairs),
            "batch_latency_ms": batch_latency_ms,
            "batch_cases_per_second": (
                len(batch_pairs) / (batch_latency_ms / 1000.0)
                if batch_latency_ms > 0
                else None
            ),
        },
        "base_latency_ms": _distribution(base_latencies),
        "composed_sequential_latency_ms": _distribution(composed_latencies),
        "global_rescue_frontier": global_frontier,
        "route_local_rescue_frontier": route_frontier,
        "primary_zero_additional_false": primary,
        "primary_target_pass": primary_target_pass,
        "rows": rows,
        "policy": {
            "base_accepted_decisions_changed": False,
            "rank2_fallback": False,
            "same_winner_rescue_only": True,
            "calibration_or_blind_used": False,
            "complete_population_denominators": True,
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
                "base_metrics": result["base"]["metrics"],
                "base_rejected_cases": result["base"]["rejected_cases"],
                "headroom": result["base"][
                    "supported_rejected_correct_winner_headroom"
                ],
                "primary_zero_additional_false": result[
                    "primary_zero_additional_false"
                ],
                "primary_target_pass": result["primary_target_pass"],
                "validator": result["validator"],
                "composed_latency": result[
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
