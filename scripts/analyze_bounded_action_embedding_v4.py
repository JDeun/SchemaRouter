"""Diagnose bounded width-2 action-only embedding reranking on v4 DEV.

This experiment is development-only. It never expands execution authority: semantic
recall first selects registered/schema-authorized candidates, then a cheap cached
MiniLM embedding ranks only those candidates using endpoint action names and trusted
operation aliases.
"""

from __future__ import annotations

import argparse
import inspect
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
from schemarouter import (  # noqa: E402
    CachedEmbeddingDecisionBackend,
    PlanRequest,
    SchemaPlanner,
)

MARGIN_THRESHOLDS = (0.00, 0.02, 0.05, 0.08, 0.10, 0.15, 0.20)
FALSE_BUDGETS = (0, 6, 12, 13, 24, 36)


class RecordingBackend:
    """Record synchronous decision metadata without changing backend behavior."""

    def __init__(self, backend: Any) -> None:
        self.backend = backend
        self.last_request: Any | None = None
        self.last_result: Any | None = None
        self.last_invoked = False

    def decide(self, request: Any) -> Any:
        self.last_request = request
        self.last_invoked = True
        result = self.backend.decide(request)
        if inspect.isawaitable(result):
            close = getattr(result, "close", None)
            if callable(close):
                close()
            raise RuntimeError("bounded action embedding diagnostic requires sync embeddings")
        self.last_result = result
        return result


def action_only_option_text(option: Any) -> str:
    """Use normalized endpoint action + trusted aliases, excluding endpoint description."""

    label = str(getattr(option, "label", "") or getattr(option, "id", "")).strip()
    normalized_label = " ".join(label.replace("_", " ").replace("-", " ").split())
    description = str(getattr(option, "description", "") or "")
    lines = [line.strip() for line in description.splitlines() if line.strip()]

    # SchemaPlanner operation-fit description is:
    # normalized operation name, operation_aliases..., endpoint description.
    action_lines = lines[:-1] if len(lines) >= 2 else lines
    return "\n".join(
        dict.fromkeys(
            part for part in [normalized_label, *action_lines] if part
        )
    )


def percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * q
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def distribution(values: list[float]) -> dict[str, float | int | None]:
    return {
        "count": len(values),
        "min": min(values) if values else None,
        "p05": percentile(values, 0.05),
        "p10": percentile(values, 0.10),
        "p25": percentile(values, 0.25),
        "p50": percentile(values, 0.50),
        "p75": percentile(values, 0.75),
        "p90": percentile(values, 0.90),
        "p95": percentile(values, 0.95),
        "max": max(values) if values else None,
        "mean": statistics.fmean(values) if values else None,
    }


def load_cases(path: Path) -> list[dict[str, Any]]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise ValueError("corpus must be a JSON object list")
    return value


def _threshold_options(
    rows: list[dict[str, Any]],
    route: str,
) -> list[dict[str, Any]]:
    routed = [
        row
        for row in rows
        if row.get("operation_fit_invoked")
        and row.get("top_route") == route
        and row.get("top_score") is not None
        and row.get("top_margin") is not None
    ]
    scores = sorted({float(row["top_score"]) for row in routed})
    score_thresholds = [-1.0, *scores]
    if scores:
        score_thresholds.append(math.nextafter(scores[-1], math.inf))

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
                "score_threshold": score_threshold,
                "margin_threshold": margin_threshold,
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
                float(previous["score_threshold"]),
                float(previous["margin_threshold"]),
            ):
                states[key] = candidate

    # Remove dominated states before global dynamic programming.
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


def optimize_route_thresholds(
    rows: list[dict[str, Any]],
    routes: list[str],
    false_budget: int,
) -> dict[str, Any]:
    route_options = {
        route: _threshold_options(rows, route)
        for route in routes
    }
    dp: dict[tuple[int, int], tuple[int, list[tuple[str, dict[str, Any]]]]] = {
        (0, 0): (0, [])
    }
    for route in routes:
        next_dp: dict[
            tuple[int, int],
            tuple[int, list[tuple[str, dict[str, Any]]]],
        ] = {}
        for (used_false, used_wrong), (supported_correct, selected) in dp.items():
            for option in route_options[route]:
                new_false = used_false + int(option["false_routes"])
                if new_false > false_budget:
                    continue
                new_wrong = used_wrong + int(option["wrong_supported"])
                new_supported = supported_correct + int(option["supported_correct"])
                key = (new_false, new_wrong)
                previous = next_dp.get(key)
                if previous is None or new_supported > previous[0]:
                    next_dp[key] = (
                        new_supported,
                        [*selected, (route, option)],
                    )
        dp = next_dp

    if not dp:
        raise ValueError(f"no threshold solution for false budget {false_budget}")

    (used_false, used_wrong), (supported_correct, selected) = max(
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
                "min_similarity": float(option["score_threshold"]),
                "min_margin": float(option["margin_threshold"]),
            }
            for route, option in selected
        },
    }


def apply_threshold_map(
    rows: list[dict[str, Any]],
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

    accepted_rows: list[dict[str, Any]] = []
    for row in rows:
        route = row.get("top_route")
        if not isinstance(route, str):
            continue
        threshold = thresholds.get(route)
        if threshold is None:
            continue
        if (
            float(row["top_score"]) >= threshold["min_similarity"]
            and float(row["top_margin"]) >= threshold["min_margin"]
        ):
            accepted_rows.append(row)

    accepted_ids = {str(row["case_id"]) for row in accepted_rows}
    supported_correct = sum(
        row.get("expected") == row.get("top_route")
        for row in accepted_rows
        if row.get("expected") is not None
    )
    false_routes = sum(row.get("expected") is None for row in accepted_rows)
    near_false = sum(
        row.get("category") == "near_domain_unsupported_operation"
        for row in accepted_rows
        if row.get("expected") is None
    )
    ood_false = sum(
        row.get("category") == "out_of_domain"
        for row in accepted_rows
        if row.get("expected") is None
    )
    wrong_supported = sum(
        row.get("expected") is not None
        and row.get("expected") != row.get("top_route")
        for row in accepted_rows
    )

    per_route: dict[str, Any] = {}
    for route in sorted({str(row["expected"]) for row in supported}):
        route_rows = [row for row in supported if row.get("expected") == route]
        correct = sum(
            str(row["case_id"]) in accepted_ids
            and row.get("top_route") == route
            for row in route_rows
        )
        per_route[route] = {
            "cases": len(route_rows),
            "supported_correct": correct,
            "recall": correct / len(route_rows) if route_rows else 0.0,
        }

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
        "per_route": per_route,
    }


def run(
    cases: list[dict[str, Any]],
    *,
    warmup_cases: int,
) -> dict[str, Any]:
    registry = reference_registry()
    allowed_routes = {
        f"{tool.key}.{endpoint.name}"
        for tool in registry.tools()
        for endpoint in tool.endpoints
    }

    recall_backend = CachedEmbeddingDecisionBackend(
        embed,
        min_similarity=-1.0,
        min_margin=0.0,
    )
    operation_recorder = RecordingBackend(
        CachedEmbeddingDecisionBackend(
            embed,
            min_similarity=-1.0,
            min_margin=0.0,
            option_text=action_only_option_text,
        )
    )
    planner = SchemaPlanner(
        registry,
        candidate_recall_backend=recall_backend,
        candidate_recall_limit=2,
        operation_fit_backend=operation_recorder,
        operation_fit_select_accepted=True,
        operation_fit_scope="all_candidates",
    )

    for case in cases[:warmup_cases]:
        planner.plan(PlanRequest(query=str(case["query"]), max_calls=1))

    rows: list[dict[str, Any]] = []
    for case in cases:
        operation_recorder.last_invoked = False
        operation_recorder.last_result = None
        started = time.perf_counter_ns()
        try:
            plan = planner.plan(
                PlanRequest(
                    query=str(case["query"]),
                    max_calls=1,
                )
            )
            latency_ms = (time.perf_counter_ns() - started) / 1_000_000
            predicted = (
                f"{plan.calls[0].tool}.{plan.calls[0].endpoint}"
                if plan.calls
                else None
            )
            result = operation_recorder.last_result
            metadata = getattr(result, "metadata", {}) if result is not None else {}
            ranked = metadata.get("ranked_options")
            ranked = ranked if isinstance(ranked, list) else []
            top_route = (
                ranked[0].get("option_id")
                if ranked and isinstance(ranked[0], dict)
                else None
            )
            top_score = metadata.get("top_similarity")
            second_score = metadata.get("second_similarity")
            top_margin = metadata.get("top_margin")
            expected = case.get("expected")
            rows.append(
                {
                    "case_id": case.get("id"),
                    "query": case.get("query"),
                    "category": case.get("category"),
                    "language": case.get("language"),
                    "unsupported_family": case.get("unsupported_family"),
                    "expected": expected,
                    "predicted": predicted,
                    "correct": predicted == expected,
                    "invalid_plan": predicted is not None and predicted not in allowed_routes,
                    "latency_ms": latency_ms,
                    "operation_fit_invoked": operation_recorder.last_invoked,
                    "top_route": top_route,
                    "top_score": top_score,
                    "second_score": second_score,
                    "top_margin": top_margin,
                    "operation_cache_hits": metadata.get("cache_hits"),
                    "operation_cache_misses": metadata.get("cache_misses"),
                    "error": None,
                }
            )
        except Exception as exc:  # noqa: BLE001 - diagnostics must retain provider failures.
            latency_ms = (time.perf_counter_ns() - started) / 1_000_000
            rows.append(
                {
                    "case_id": case.get("id"),
                    "query": case.get("query"),
                    "category": case.get("category"),
                    "language": case.get("language"),
                    "unsupported_family": case.get("unsupported_family"),
                    "expected": case.get("expected"),
                    "predicted": None,
                    "correct": False,
                    "invalid_plan": False,
                    "latency_ms": latency_ms,
                    "operation_fit_invoked": operation_recorder.last_invoked,
                    "top_route": None,
                    "top_score": None,
                    "second_score": None,
                    "top_margin": None,
                    "operation_cache_hits": None,
                    "operation_cache_misses": None,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )

    supported = [row for row in rows if row.get("expected") is not None]
    near = [
        row
        for row in rows
        if row.get("category") == "near_domain_unsupported_operation"
    ]
    ood = [row for row in rows if row.get("category") == "out_of_domain"]
    no_route = [row for row in rows if row.get("expected") is None]
    invoked = [row for row in rows if row.get("operation_fit_invoked")]
    valid_scored = [
        row
        for row in invoked
        if row.get("top_route") is not None
        and row.get("top_score") is not None
        and row.get("top_margin") is not None
    ]

    per_language: dict[str, Any] = {}
    for language in sorted({str(row["language"]) for row in supported}):
        subset = [row for row in supported if row.get("language") == language]
        raw_correct = sum(row.get("top_route") == row.get("expected") for row in subset)
        per_language[language] = {
            "cases": len(subset),
            "raw_top_exact_rate": raw_correct / len(subset) if subset else 0.0,
        }

    per_route: dict[str, Any] = {}
    for route in sorted({str(row["expected"]) for row in supported}):
        subset = [row for row in supported if row.get("expected") == route]
        raw_correct = sum(row.get("top_route") == route for row in subset)
        per_route[route] = {
            "cases": len(subset),
            "raw_top_exact_rate": raw_correct / len(subset) if subset else 0.0,
        }

    routes = sorted(
        {
            str(row["top_route"])
            for row in valid_scored
            if isinstance(row.get("top_route"), str)
        }
    )
    frontiers: list[dict[str, Any]] = []
    for budget in FALSE_BUDGETS:
        solution = optimize_route_thresholds(valid_scored, routes, budget)
        projected = apply_threshold_map(valid_scored, solution["thresholds"])
        frontiers.append({**solution, **projected})

    canonical = next(
        item for item in frontiers if int(item["false_budget"]) == 12
    )
    latency_values = [
        float(row["latency_ms"])
        for row in rows
        if row.get("error") is None
    ]

    result = {
        "architecture": {
            "candidate_recall_model": (
                "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
            ),
            "candidate_recall_limit": 2,
            "candidate_recall_static_option_cache": True,
            "operation_fit_model": (
                "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
            ),
            "operation_fit_surface": "action_name_plus_operation_aliases_only",
            "operation_fit_static_option_cache": True,
            "operation_fit_scope": "all_recalled_candidates",
            "operation_fit_select_accepted": True,
            "bge_used": False,
        },
        "summary": {
            "cases": len(rows),
            "supported_cases": len(supported),
            "near_domain_cases": len(near),
            "ood_cases": len(ood),
            "raw_supported_top_exact_rate": (
                sum(row.get("top_route") == row.get("expected") for row in supported)
                / len(supported)
                if supported
                else 0.0
            ),
            "raw_false_route_rate": (
                sum(row.get("predicted") is not None for row in no_route) / len(no_route)
                if no_route
                else 0.0
            ),
            "invalid_plans": sum(bool(row.get("invalid_plan")) for row in rows),
            "errors": sum(row.get("error") is not None for row in rows),
            "operation_fit_invocations": len(invoked),
            "latency_ms": distribution(latency_values),
            "operation_cache_hits_total": sum(
                int(row["operation_cache_hits"])
                for row in valid_scored
                if isinstance(row.get("operation_cache_hits"), int)
            ),
            "operation_cache_misses_total": sum(
                int(row["operation_cache_misses"])
                for row in valid_scored
                if isinstance(row.get("operation_cache_misses"), int)
            ),
            "per_language": per_language,
            "per_route": per_route,
        },
        "winner_only_route_local_frontier": frontiers,
        "canonical_false_budget_12": canonical,
        "rows": rows,
        "policy": {
            "data_role": "tuning_eligible_development",
            "behavior_change": False,
            "calibration_or_blind_used": False,
            "note": (
                "Threshold maps are retrospective DEV projections only. Any executable "
                "candidate must freeze a selected map before its next run."
            ),
        },
    }
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--warmup-cases", type=int, default=24)
    args = parser.parse_args()
    if args.warmup_cases < 0:
        parser.error("--warmup-cases must be >= 0")

    result = run(
        load_cases(args.corpus),
        warmup_cases=args.warmup_cases,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "raw_supported_top_exact_rate": result["summary"][
                    "raw_supported_top_exact_rate"
                ],
                "latency_ms": result["summary"]["latency_ms"],
                "canonical_false_budget_12": result["canonical_false_budget_12"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
