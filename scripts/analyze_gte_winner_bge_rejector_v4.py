"""DEV-only diagnostic for GTE ranking plus winner-only BGE rejection."""

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

FALSE_BUDGETS = (0, 6, 12, 13, 24, 36)
GTE_MARGIN_GUARDS = (0.0, 0.02, 0.05, 0.08)


def _sigmoid(value: float) -> float:
    if value >= 0:
        z = math.exp(-value)
        return 1.0 / (1.0 + z)
    z = math.exp(value)
    return z / (1.0 + z)


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


def _catalog() -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    registry = reference_registry()
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
                    "tool": tool.key,
                    "endpoint": endpoint.name,
                    "schema_text": dual._schema_text(tool, endpoint),
                    "action_text": action_text,
                    "capability_text": capability_text,
                }
            )
    return sorted(items, key=lambda item: item["route_id"])


class BGEReranker:
    def __init__(self, *, max_length: int) -> None:
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        self.max_length = max_length
        self.model_name = "BAAI/bge-reranker-v2-m3"
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
        self.model = AutoModelForSequenceClassification.from_pretrained(self.model_name)
        self.model.eval()

    def score(self, query: str, text: str) -> float:
        import torch

        encoded = self.tokenizer(
            [query],
            [text],
            padding=True,
            truncation=True,
            max_length=self.max_length,
            return_tensors="pt",
        )
        with torch.no_grad():
            logits = self.model(**encoded, return_dict=True).logits
        flattened = logits.reshape(logits.shape[0], -1)
        if flattened.shape != (1, 1):
            raise RuntimeError(
                f"{self.model_name} returned unexpected logits shape "
                f"{tuple(flattened.shape)}"
            )
        return _sigmoid(float(flattened[0, 0].item()))


def _route_options(
    rows: list[dict[str, Any]],
    *,
    route: str,
    margin_guard: float,
) -> list[dict[str, Any]]:
    routed = [
        row
        for row in rows
        if row["selected_route"] == route
        and float(row["gte_margin"]) >= margin_guard
    ]
    scores = sorted({float(row["bge_score"]) for row in routed})
    thresholds = [-1.0, *scores, 1.000001]

    states: dict[tuple[int, int], dict[str, Any]] = {}
    for threshold in thresholds:
        supported_correct = 0
        false_routes = 0
        wrong_supported = 0
        for row in routed:
            if float(row["bge_score"]) < threshold:
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
            "min_bge_score": threshold,
            "supported_correct": supported_correct,
            "false_routes": false_routes,
            "wrong_supported": wrong_supported,
        }
        previous = states.get(key)
        if previous is None or (
            supported_correct,
            threshold,
        ) > (
            int(previous["supported_correct"]),
            float(previous["min_bge_score"]),
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


def _optimize(
    rows: list[dict[str, Any]],
    *,
    routes: list[str],
    margin_guard: float,
    false_budget: int,
) -> dict[str, Any]:
    options = {
        route: _route_options(
            rows,
            route=route,
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
            f"no solution for margin_guard={margin_guard}, "
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
        "gte_margin_guard": margin_guard,
        "false_budget": false_budget,
        "false_routes": used_false,
        "wrong_supported": used_wrong,
        "supported_correct": supported_correct,
        "thresholds": {
            route: float(option["min_bge_score"])
            for route, option in chosen
        },
    }


def _project(
    rows: list[dict[str, Any]],
    *,
    margin_guard: float,
    thresholds: dict[str, float],
) -> dict[str, Any]:
    supported = [row for row in rows if row.get("expected") is not None]
    near = [
        row
        for row in rows
        if row.get("category") == "near_domain_unsupported_operation"
    ]
    ood = [
        row
        for row in rows
        if row.get("category") == "out_of_domain"
    ]
    no_route = [row for row in rows if row.get("expected") is None]

    accepted: list[dict[str, Any]] = []
    for row in rows:
        if float(row["gte_margin"]) < margin_guard:
            continue
        route = str(row["selected_route"])
        threshold = thresholds.get(route)
        if threshold is None:
            continue
        if float(row["bge_score"]) >= threshold:
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


def run(
    cases: list[dict[str, Any]],
    *,
    text_variant: str,
    max_length: int,
) -> dict[str, Any]:
    if text_variant not in {"action-only", "capability"}:
        raise ValueError("text_variant must be action-only or capability")
    if max_length not in {128, 256}:
        raise ValueError("max_length must be 128 or 256")

    config, static_embedder, query_embedder = screen._build_embedders(
        "gte-multilingual-base"
    )
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

    bge = BGEReranker(max_length=max_length)
    rows: list[dict[str, Any]] = []
    gte_latencies: list[float] = []
    bge_latencies: list[float] = []
    total_latencies: list[float] = []

    for case in cases:
        total_started = time.perf_counter_ns()

        gte_started = time.perf_counter_ns()
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
            0.25 * schema_score + 0.75 * action_score
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
        gte_ms = (time.perf_counter_ns() - gte_started) / 1_000_000

        winner_index = route_ids.index(top_route)
        winner = catalog[winner_index]
        winner_text = str(
            winner[
                "action_text"
                if text_variant == "action-only"
                else "capability_text"
            ]
        )

        bge_started = time.perf_counter_ns()
        bge_score = bge.score(str(case["query"]), winner_text)
        bge_ms = (time.perf_counter_ns() - bge_started) / 1_000_000
        total_ms = (time.perf_counter_ns() - total_started) / 1_000_000

        gte_latencies.append(gte_ms)
        bge_latencies.append(bge_ms)
        total_latencies.append(total_ms)
        rows.append(
            {
                "case_id": case.get("id"),
                "category": case.get("category"),
                "language": case.get("language"),
                "unsupported_family": case.get("unsupported_family"),
                "expected": case.get("expected"),
                "selected_route": top_route,
                "gte_top_score": top_score,
                "gte_second_score": second_score,
                "gte_margin": top_margin,
                "bge_score": bge_score,
                "rank_correct": top_route == case.get("expected"),
            }
        )

    supported = [row for row in rows if row.get("expected") is not None]
    raw_supported_correct = sum(
        row["rank_correct"] for row in supported
    )
    routes = sorted({str(row["selected_route"]) for row in rows})

    frontiers: dict[str, list[dict[str, Any]]] = {}
    canonical: list[dict[str, Any]] = []
    for margin_guard in GTE_MARGIN_GUARDS:
        points: list[dict[str, Any]] = []
        for false_budget in FALSE_BUDGETS:
            solution = _optimize(
                rows,
                routes=routes,
                margin_guard=margin_guard,
                false_budget=false_budget,
            )
            projected = _project(
                rows,
                margin_guard=margin_guard,
                thresholds=solution["thresholds"],
            )
            point = {**solution, **projected}
            points.append(point)
            if false_budget == 12:
                canonical.append(point)
        frontiers[f"{margin_guard:.2f}"] = points

    canonical.sort(
        key=lambda item: (
            -float(item["supported_exact_route_accuracy"]),
            int(item["false_routes"]),
            int(item["wrong_supported"]),
            float(item["gte_margin_guard"]),
        )
    )
    passing = [
        item
        for item in canonical
        if float(item["supported_exact_route_accuracy"]) >= 0.85
        and float(item["near_domain_unsupported_rejection"]) >= 0.97
        and float(item["canonical_false_route_rate"]) <= 0.02
    ]

    score_groups = {
        "correct_supported": [
            float(row["bge_score"])
            for row in rows
            if row.get("expected") is not None and row["rank_correct"]
        ],
        "wrong_supported": [
            float(row["bge_score"])
            for row in rows
            if row.get("expected") is not None and not row["rank_correct"]
        ],
        "near_domain_unsupported": [
            float(row["bge_score"])
            for row in rows
            if row.get("category") == "near_domain_unsupported_operation"
        ],
        "out_of_domain": [
            float(row["bge_score"])
            for row in rows
            if row.get("category") == "out_of_domain"
        ],
    }

    return {
        "architecture": {
            "gte_model": config,
            "gte_schema_weight": 0.25,
            "gte_action_weight": 0.75,
            "bge_model": "BAAI/bge-reranker-v2-m3",
            "bge_text_variant": text_variant,
            "bge_max_length": max_length,
            "bge_pairs_per_case": 1,
            "bge_can_change_route": False,
            "static_gte_route_embedding_ms": static_ms,
        },
        "summary": {
            "cases": len(rows),
            "raw_supported_exact_route_accuracy": (
                raw_supported_correct / len(supported)
            ),
            "bge_score_distributions": {
                name: _distribution(values)
                for name, values in score_groups.items()
            },
            "gte_latency_ms": _distribution(gte_latencies),
            "bge_latency_ms": _distribution(bge_latencies),
            "end_to_end_latency_ms": _distribution(total_latencies),
            "best_canonical_false_budget_12": (
                canonical[0] if canonical else None
            ),
            "screening_gate_pass_count": len(passing),
            "screening_gate_passes": passing,
        },
        "frontiers": frontiers,
        "canonical_false_budget_12": canonical,
        "policy": {
            "data_role": "tuning_eligible_development",
            "calibration_or_blind_used": False,
            "behavior_change": False,
            "full_population_denominators": True,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument(
        "--text-variant",
        choices=("action-only", "capability"),
        required=True,
    )
    parser.add_argument(
        "--max-length",
        type=int,
        choices=(128, 256),
        required=True,
    )
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    cases = json.loads(args.corpus.read_text(encoding="utf-8"))
    if not isinstance(cases, list) or any(
        not isinstance(item, dict) for item in cases
    ):
        raise ValueError("corpus must be a JSON object list")

    result = run(
        cases,
        text_variant=args.text_variant,
        max_length=args.max_length,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "text_variant": args.text_variant,
                "max_length": args.max_length,
                "raw_supported_exact_route_accuracy": result["summary"][
                    "raw_supported_exact_route_accuracy"
                ],
                "best_canonical": result["summary"][
                    "best_canonical_false_budget_12"
                ],
                "screening_gate_pass_count": result["summary"][
                    "screening_gate_pass_count"
                ],
                "gte_latency": result["summary"]["gte_latency_ms"],
                "bge_latency": result["summary"]["bge_latency_ms"],
                "end_to_end_latency": result["summary"][
                    "end_to_end_latency_ms"
                ],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
