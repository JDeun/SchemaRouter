"""Diagnose winner-only cross-encoder rescue over the frozen BGE-M3 budget-6 gate."""

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

from benchmark_decision_routing import reference_registry  # noqa: E402

from benchmarks.bge_m3_frozen_candidate import (  # noqa: E402
    MODEL_NAME as RANKER_MODEL_NAME,
)
from benchmarks.bge_m3_frozen_candidate import (  # noqa: E402
    MODEL_REVISION as RANKER_MODEL_REVISION,
)
from benchmarks.bge_m3_frozen_candidate import (  # noqa: E402
    FrozenBgeM3DualViewBackend,
)
from benchmarks.bge_winner_validator import (  # noqa: E402
    MODEL_NAME as VALIDATOR_MODEL_NAME,
)
from benchmarks.bge_winner_validator import (  # noqa: E402
    MODEL_REVISION as VALIDATOR_MODEL_REVISION,
)
from benchmarks.bge_winner_validator import score_pair, score_pairs, unload  # noqa: E402

RESCUE_FALSE_BUDGETS = (0, 1, 2, 3)


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


def _load_ranker():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(
        RANKER_MODEL_NAME,
        revision=RANKER_MODEL_REVISION,
        trust_remote_code=False,
    )


def _ranker_embedder(model: Any):
    def embed(texts: list[str]) -> list[list[float]]:
        vectors = model.encode(
            texts,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return vectors.tolist()

    return embed


def _validator_surface(registry: Any) -> dict[str, str]:
    result: dict[str, str] = {}
    for tool in registry.tools():
        for endpoint in tool.endpoints:
            route_id = f"{tool.key}.{endpoint.name}"
            operation_name = endpoint.name.replace("_", " ").replace("-", " ")
            parts = [
                operation_name,
                *endpoint.operation_aliases,
                endpoint.description.strip(),
            ]
            result[route_id] = "\n".join(
                dict.fromkeys(part for part in parts if part)
            )
    return result


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
        raise ValueError(f"no global rescue threshold for false budget {false_budget}")
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
        row for row in rows
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
        raise ValueError(
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
        row for row in rows
        if row["category"] == "near_domain_unsupported_operation"
    ]
    ood = [
        row for row in rows
        if row["category"] == "out_of_domain"
    ]
    no_route = [row for row in rows if row["expected"] is None]

    predictions: list[str | None] = []
    rescued_ids: set[str] = set()
    for row in rows:
        predicted = str(row["top_route"]) if row["base_accepted"] else None
        if not row["base_accepted"]:
            if global_threshold is not None:
                rescue = float(row["validator_score"]) >= global_threshold
            else:
                assert route_thresholds is not None
                threshold = route_thresholds.get(str(row["top_route"]), math.inf)
                rescue = float(row["validator_score"]) >= threshold
            if rescue:
                predicted = str(row["top_route"])
                rescued_ids.add(str(row["case_id"]))
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
    registry = reference_registry()
    surfaces = _validator_surface(registry)

    ranker = _load_ranker()
    ranker_backend = FrozenBgeM3DualViewBackend(
        registry,
        _ranker_embedder(ranker),
    )

    base_rows: list[dict[str, Any]] = []
    base_latencies: list[float] = []
    for case in cases:
        started = time.perf_counter_ns()
        result = ranker_backend.score_routes(
            str(case["query"]),
            ranker_backend.route_ids,
        )
        latency_ms = (time.perf_counter_ns() - started) / 1_000_000
        base_latencies.append(latency_ms)
        top_route = str(result["top_route"])
        base_rows.append(
            {
                "case_id": case.get("id"),
                "query": case.get("query"),
                "category": case.get("category"),
                "language": case.get("language"),
                "unsupported_family": case.get("unsupported_family"),
                "expected": case.get("expected"),
                "top_route": top_route,
                "base_top_score": float(result["top_score"]),
                "base_top_margin": float(result["top_margin"]),
                "base_accepted": bool(result["accepted"]),
                "validator_surface": surfaces[top_route],
            }
        )

    del ranker_backend
    del ranker
    gc.collect()

    rejected = [row for row in base_rows if not row["base_accepted"]]
    validator_latencies: list[float] = []
    for row in rejected:
        started = time.perf_counter_ns()
        score = score_pair(
            str(row["query"]),
            str(row["validator_surface"]),
        )
        validator_latency = (time.perf_counter_ns() - started) / 1_000_000
        row["validator_score"] = score
        row["validator_latency_ms"] = validator_latency
        validator_latencies.append(validator_latency)

    for row in base_rows:
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
    if batch_pairs:
        batch_scores = score_pairs(batch_pairs)
        if len(batch_scores) != len(batch_pairs):
            raise RuntimeError("validator batch score count mismatch")
    batch_latency_ms = (
        (time.perf_counter_ns() - batch_started) / 1_000_000
        if batch_pairs
        else 0.0
    )

    routes = sorted(surfaces)
    global_frontier: list[dict[str, Any]] = []
    route_frontier: list[dict[str, Any]] = []

    for budget in RESCUE_FALSE_BUDGETS:
        global_solution = _global_frontier(
            base_rows,
            false_budget=budget,
        )
        global_metrics = _compose_metrics(
            base_rows,
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
            base_rows,
            routes,
            false_budget=budget,
        )
        route_metrics = _compose_metrics(
            base_rows,
            route_thresholds=route_solution["thresholds"],
        )
        route_frontier.append(
            {
                "rescue_false_budget": budget,
                **route_solution,
                **route_metrics,
            }
        )

    base_metrics = _compose_metrics(
        base_rows,
        route_thresholds={route: math.inf for route in routes},
    )

    zero_false = next(
        item
        for item in route_frontier
        if int(item["rescue_false_budget"]) == 0
    )

    composed_latencies = [
        base_latency
        + (
            float(row["validator_latency_ms"])
            if not row["base_accepted"]
            else 0.0
        )
        for row, base_latency in zip(base_rows, base_latencies, strict=True)
    ]

    supported_rejected_correct_winner = sum(
        not row["base_accepted"]
        and row["expected"] is not None
        and row["expected"] == row["top_route"]
        for row in base_rows
    )

    target_pass = (
        float(zero_false["supported_exact_route_accuracy"]) >= 0.85
        and float(zero_false["near_domain_unsupported_rejection"]) >= 0.97
        and float(zero_false["false_route_rate"]) <= 0.01
        and int(zero_false["additional_false_routes"]) == 0
    )

    return {
        "experiment": "winner-only-cross-encoder-rescue-validator-v1",
        "base": {
            "model": RANKER_MODEL_NAME,
            "revision": RANKER_MODEL_REVISION,
            "metrics": base_metrics,
            "ranker_latency_ms": _distribution(base_latencies),
            "rejected_cases": len(rejected),
            "validator_invocation_rate": len(rejected) / len(base_rows),
            "supported_rejected_correct_winner_headroom": (
                supported_rejected_correct_winner
            ),
        },
        "validator": {
            "model": VALIDATOR_MODEL_NAME,
            "revision": VALIDATOR_MODEL_REVISION,
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
        "composed_sequential_latency_ms": _distribution(composed_latencies),
        "global_rescue_frontier": global_frontier,
        "route_local_rescue_frontier": route_frontier,
        "primary_zero_additional_false": zero_false,
        "primary_target_pass": target_pass,
        "rows": base_rows,
        "policy": {
            "base_accepted_decisions_changed": False,
            "rank2_fallback": False,
            "same_winner_rescue_only": True,
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
                "validator": result["validator"],
                "composed_sequential_latency_ms": result[
                    "composed_sequential_latency_ms"
                ],
                "primary_zero_additional_false": result[
                    "primary_zero_additional_false"
                ],
                "primary_target_pass": result["primary_target_pass"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )

    unload()


if __name__ == "__main__":
    main()
