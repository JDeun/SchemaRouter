"""DEV-only zero-false abstention rescue diagnostic on the robust BGE-M3 base."""

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

from benchmarks.bge_m3_frozen_candidate import (  # noqa: E402
    FROZEN_THRESHOLDS,
    FrozenBgeM3DualViewBackend,
)

FALSE_BUDGETS = (0, 1, 2)
GTE_MARGIN_THRESHOLDS = (0.0, 0.01, 0.02, 0.03, 0.05, 0.08, 0.10, 0.15)
SCORE_DEFICIT_MAX = (0.001, 0.0025, 0.005, 0.01, 0.02, 0.05, 1.0)
MARGIN_DEFICIT_MAX = (0.0, 0.005, 0.01, 0.02, 0.05, 1.0)
BGE_RERANKER_MODEL = "BAAI/bge-reranker-v2-m3"
BGE_RERANKER_REVISION = "953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e"
SCORE_QUANTILES = (0.0, 0.10, 0.25, 0.50, 0.75, 0.90, 1.0)


def _quantile_thresholds(values: list[float]) -> list[float]:
    if not values:
        return [1.000001]
    ordered = sorted(values)
    thresholds = {-1.0, 1.000001}
    for q in SCORE_QUANTILES:
        position = (len(ordered) - 1) * q
        lower = math.floor(position)
        upper = math.ceil(position)
        if lower == upper:
            value = ordered[lower]
        else:
            weight = position - lower
            value = ordered[lower] * (1.0 - weight) + ordered[upper] * weight
        thresholds.add(float(value))
    return sorted(thresholds)


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


def _catalog(registry: Any) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for tool in registry.tools():
        for endpoint in tool.endpoints:
            action = dual._action_text(endpoint)
            items.append(
                {
                    "route_id": f"{tool.key}.{endpoint.name}",
                    "schema_text": dual._schema_text(tool, endpoint),
                    "action_text": action,
                    "capability_text": "\n".join(
                        part for part in [action, endpoint.description.strip()] if part
                    ),
                }
            )
    return sorted(items, key=lambda item: item["route_id"])


def _sigmoid(value: float) -> float:
    if value >= 0:
        z = math.exp(-value)
        return 1.0 / (1.0 + z)
    z = math.exp(value)
    return z / (1.0 + z)


class WinnerReranker:
    def __init__(self) -> None:
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        self.tokenizer = AutoTokenizer.from_pretrained(
            BGE_RERANKER_MODEL,
            revision=BGE_RERANKER_REVISION,
        )
        self.model = AutoModelForSequenceClassification.from_pretrained(
            BGE_RERANKER_MODEL,
            revision=BGE_RERANKER_REVISION,
        )
        self.model.eval()

    def score(self, query: str, text: str) -> float:
        import torch

        encoded = self.tokenizer(
            [query],
            [text],
            padding=True,
            truncation=True,
            max_length=256,
            return_tensors="pt",
        )
        with torch.no_grad():
            logits = self.model(**encoded, return_dict=True).logits
        flat = logits.reshape(logits.shape[0], -1)
        if flat.shape != (1, 1):
            raise RuntimeError(f"unexpected reranker logits shape: {tuple(flat.shape)}")
        return _sigmoid(float(flat[0, 0].item()))


def _candidate_rules(
    rows: list[dict[str, Any]],
    *,
    route: str,
    variant: str,
) -> list[dict[str, Any]]:
    routed = [
        row for row in rows
        if row["base_raw_route"] == route
        and row["gte_agrees"]
        and not row["base_accepted"]
    ]
    score_thresholds = _quantile_thresholds(
        [float(row["gte_top_score"]) for row in routed]
    )

    if variant == "gte-agreement-bge":
        reranker_thresholds = _quantile_thresholds(
            [
                float(row["reranker_score"])
                for row in routed
                if row["reranker_score"] is not None
            ]
        )
    else:
        reranker_thresholds = [-1.0]

    states: dict[tuple[int, int], dict[str, Any]] = {}
    for min_gte_score in score_thresholds:
        for min_gte_margin in GTE_MARGIN_THRESHOLDS:
            for max_score_deficit in SCORE_DEFICIT_MAX:
                for max_margin_deficit in MARGIN_DEFICIT_MAX:
                    for min_reranker in reranker_thresholds:
                        correct = false_routes = wrong_supported = 0
                        for row in routed:
                            if float(row["gte_top_score"]) < min_gte_score:
                                continue
                            if float(row["gte_margin"]) < min_gte_margin:
                                continue
                            if float(row["base_score_deficit"]) > max_score_deficit:
                                continue
                            if float(row["base_margin_deficit"]) > max_margin_deficit:
                                continue
                            if variant == "gte-agreement-bge":
                                value = row["reranker_score"]
                                if value is None or float(value) < min_reranker:
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
                            "min_gte_score": min_gte_score,
                            "min_gte_margin": min_gte_margin,
                            "max_base_score_deficit": max_score_deficit,
                            "max_base_margin_deficit": max_margin_deficit,
                            "min_reranker_score": (
                                min_reranker if variant == "gte-agreement-bge" else None
                            ),
                            "rescued_correct": correct,
                            "additional_false_routes": false_routes,
                            "rescued_wrong_supported": wrong_supported,
                        }
                        prev = states.get(key)
                        if prev is None or correct > int(prev["rescued_correct"]):
                            states[key] = candidate

    candidates = list(states.values())
    frontier: list[dict[str, Any]] = []
    for candidate in candidates:
        dominated = any(
            other is not candidate
            and int(other["additional_false_routes"])
            <= int(candidate["additional_false_routes"])
            and int(other["rescued_wrong_supported"])
            <= int(candidate["rescued_wrong_supported"])
            and int(other["rescued_correct"]) >= int(candidate["rescued_correct"])
            and (
                int(other["additional_false_routes"])
                < int(candidate["additional_false_routes"])
                or int(other["rescued_wrong_supported"])
                < int(candidate["rescued_wrong_supported"])
                or int(other["rescued_correct"]) > int(candidate["rescued_correct"])
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
    variant: str,
    false_budget: int,
) -> dict[str, Any]:
    route_options = {
        route: _candidate_rules(rows, route=route, variant=variant)
        for route in routes
    }
    dp: dict[
        tuple[int, int],
        tuple[int, list[tuple[str, dict[str, Any]]]],
    ] = {(0, 0): (0, [])}

    for route in routes:
        options = route_options[route]
        if not options:
            options = [{
                "min_gte_score": 1.000001,
                "min_gte_margin": 1.0,
                "max_base_score_deficit": 0.0,
                "max_base_margin_deficit": 0.0,
                "min_reranker_score": 1.000001 if variant == "gte-agreement-bge" else None,
                "rescued_correct": 0,
                "additional_false_routes": 0,
                "rescued_wrong_supported": 0,
            }]
        next_dp: dict[
            tuple[int, int],
            tuple[int, list[tuple[str, dict[str, Any]]]],
        ] = {}
        for (used_false, used_wrong), (rescued_correct, chosen) in dp.items():
            for option in options:
                new_false = used_false + int(option["additional_false_routes"])
                if new_false > false_budget:
                    continue
                new_wrong = used_wrong + int(option["rescued_wrong_supported"])
                new_correct = rescued_correct + int(option["rescued_correct"])
                key = (new_false, new_wrong)
                prev = next_dp.get(key)
                if prev is None or new_correct > prev[0]:
                    next_dp[key] = (new_correct, [*chosen, (route, option)])
        dp = next_dp

    if not dp:
        raise RuntimeError(f"no rescue solution for budget={false_budget}")

    (used_false, used_wrong), (rescued_correct, chosen) = max(
        dp.items(),
        key=lambda item: (item[1][0], -item[0][0], -item[0][1]),
    )
    return {
        "variant": variant,
        "additional_false_budget": false_budget,
        "additional_false_routes": used_false,
        "rescued_wrong_supported": used_wrong,
        "rescued_correct": rescued_correct,
        "rules": {route: option for route, option in chosen},
    }


def _passes_rule(row: dict[str, Any], rule: dict[str, Any], variant: str) -> bool:
    if not row["gte_agrees"] or row["base_accepted"]:
        return False
    if float(row["gte_top_score"]) < float(rule["min_gte_score"]):
        return False
    if float(row["gte_margin"]) < float(rule["min_gte_margin"]):
        return False
    if float(row["base_score_deficit"]) > float(rule["max_base_score_deficit"]):
        return False
    if float(row["base_margin_deficit"]) > float(rule["max_base_margin_deficit"]):
        return False
    if variant == "gte-agreement-bge":
        score = row["reranker_score"]
        threshold = rule["min_reranker_score"]
        if score is None or threshold is None or float(score) < float(threshold):
            return False
    return True


def _compose(
    rows: list[dict[str, Any]],
    *,
    solution: dict[str, Any],
) -> dict[str, Any]:
    variant = str(solution["variant"])
    rules = solution["rules"]
    final_routes: list[str | None] = []
    rescued_ids: set[str] = set()
    for row in rows:
        if row["base_accepted"]:
            final_routes.append(str(row["base_raw_route"]))
            continue
        route = str(row["base_raw_route"])
        rule = rules.get(route)
        if rule is not None and _passes_rule(row, rule, variant):
            final_routes.append(route)
            rescued_ids.add(str(row["case_id"]))
        else:
            final_routes.append(None)

    supported_indexes = [i for i, row in enumerate(rows) if row.get("expected") is not None]
    near_indexes = [
        i for i, row in enumerate(rows)
        if row.get("category") == "near_domain_unsupported_operation"
    ]
    ood_indexes = [
        i for i, row in enumerate(rows)
        if row.get("category") == "out_of_domain"
    ]
    no_route_indexes = [i for i, row in enumerate(rows) if row.get("expected") is None]

    supported_correct = sum(
        final_routes[i] == rows[i].get("expected") for i in supported_indexes
    )
    false_routes = sum(final_routes[i] is not None for i in no_route_indexes)
    near_rejected = sum(final_routes[i] is None for i in near_indexes)
    ood_rejected = sum(final_routes[i] is None for i in ood_indexes)

    return {
        "supported_correct": supported_correct,
        "supported_exact_route_accuracy": supported_correct / len(supported_indexes),
        "near_domain_unsupported_rejection": near_rejected / len(near_indexes),
        "out_of_domain_rejection": ood_rejected / len(ood_indexes),
        "false_routes": false_routes,
        "false_route_rate": false_routes / len(no_route_indexes),
        "rescued_total": len(rescued_ids),
    }


def run(cases: list[dict[str, Any]], *, variant: str) -> dict[str, Any]:
    if variant not in {"gte-agreement", "gte-agreement-bge"}:
        raise ValueError("unsupported variant")

    registry = reference_registry()
    catalog = _catalog(registry)
    route_ids = [str(item["route_id"]) for item in catalog]
    capability_by_route = {
        str(item["route_id"]): str(item["capability_text"]) for item in catalog
    }

    # Frozen robust BGE-M3 base.
    bge_config, bge_static, bge_query = screen._build_embedders("bge-m3")
    base = FrozenBgeM3DualViewBackend(registry, bge_query)
    # Replace base static vectors with the document-role encoder output to mirror the
    # frozen screen semantics exactly when the helper distinguishes query/document roles.
    static_texts = [
        *(base._route_specs[route][0] for route in base.route_ids),
        *(base._route_specs[route][1] for route in base.route_ids),
    ]
    static_vectors = bge_static(static_texts)
    split = len(base.route_ids)
    base._schema_vectors = dict(zip(base.route_ids, static_vectors[:split], strict=True))
    base._action_vectors = dict(zip(base.route_ids, static_vectors[split:], strict=True))

    # GTE agreement ranker.
    gte_config, gte_static, gte_query = screen._build_embedders("gte-multilingual-base")
    gte_static_texts = [
        *(str(item["schema_text"]) for item in catalog),
        *(str(item["action_text"]) for item in catalog),
    ]
    gte_vectors = gte_static(gte_static_texts)
    gte_schema = gte_vectors[: len(catalog)]
    gte_action = gte_vectors[len(catalog) :]

    reranker = WinnerReranker() if variant == "gte-agreement-bge" else None

    rows: list[dict[str, Any]] = []
    gte_latencies: list[float] = []
    reranker_latencies: list[float] = []
    validator_invocations = 0

    for case in cases:
        query = str(case["query"])
        base_result = base.score_routes(query, base.route_ids)
        base_route = str(base_result["top_route"])
        boundary = FROZEN_THRESHOLDS[base_route]

        gte_started = time.perf_counter_ns()
        query_vector = gte_query([query])[0]
        schema_scores = [dual._cosine(query_vector, vector) for vector in gte_schema]
        action_scores = [dual._cosine(query_vector, vector) for vector in gte_action]
        fused = [
            0.25 * schema + 0.75 * action
            for schema, action in zip(schema_scores, action_scores, strict=True)
        ]
        gte_route, gte_score, _, gte_margin = dual._rank(route_ids, fused)
        gte_latencies.append((time.perf_counter_ns() - gte_started) / 1_000_000)

        gte_agrees = gte_route == base_route
        reranker_score: float | None = None
        if (
            variant == "gte-agreement-bge"
            and not bool(base_result["accepted"])
            and gte_agrees
            and reranker is not None
        ):
            validator_invocations += 1
            started = time.perf_counter_ns()
            reranker_score = reranker.score(query, capability_by_route[base_route])
            reranker_latencies.append(
                (time.perf_counter_ns() - started) / 1_000_000
            )

        rows.append(
            {
                "case_id": case.get("id"),
                "category": case.get("category"),
                "language": case.get("language"),
                "expected": case.get("expected"),
                "base_raw_route": base_route,
                "base_raw_score": float(base_result["top_score"]),
                "base_raw_margin": float(base_result["top_margin"]),
                "base_accepted": bool(base_result["accepted"]),
                "base_score_deficit": max(
                    0.0,
                    float(boundary["min_score"]) - float(base_result["top_score"]),
                ),
                "base_margin_deficit": max(
                    0.0,
                    float(boundary["min_margin"]) - float(base_result["top_margin"]),
                ),
                "gte_route": gte_route,
                "gte_top_score": gte_score,
                "gte_margin": gte_margin,
                "gte_agrees": gte_agrees,
                "reranker_score": reranker_score,
            }
        )

    routes = sorted(set(route_ids))
    frontier: list[dict[str, Any]] = []
    for budget in FALSE_BUDGETS:
        solution = _optimize(rows, routes=routes, variant=variant, false_budget=budget)
        composed = _compose(rows, solution=solution)
        frontier.append({**solution, **composed})

    primary = next(item for item in frontier if item["additional_false_budget"] == 0)
    base_metrics = _compose(
        rows,
        solution={
            "variant": variant,
            "rules": {},
        },
    )

    return {
        "architecture": {
            "base_model": bge_config,
            "gte_model": gte_config,
            "variant": variant,
            "reranker_model": BGE_RERANKER_MODEL if reranker is not None else None,
            "reranker_revision": BGE_RERANKER_REVISION if reranker is not None else None,
            "same_winner_only": True,
            "base_accepted_immutable": True,
        },
        "summary": {
            "cases": len(rows),
            "base": base_metrics,
            "base_abstentions": sum(not row["base_accepted"] for row in rows),
            "gte_agreement_on_base_abstentions": sum(
                (not row["base_accepted"]) and row["gte_agrees"] for row in rows
            ),
            "gte_latency_ms": _distribution(gte_latencies),
            "reranker_invocations": validator_invocations,
            "reranker_invocation_rate": validator_invocations / len(rows),
            "reranker_latency_ms": _distribution(reranker_latencies),
            "primary_zero_false": primary,
            "promotion_gate_pass": (
                float(primary["supported_exact_route_accuracy"]) >= 0.85
                and float(primary["near_domain_unsupported_rejection"]) >= 0.97
                and float(primary["false_route_rate"]) <= 0.01
                and int(primary["additional_false_routes"]) == 0
            ),
        },
        "rescue_frontier": frontier,
        "rows": rows,
        "policy": {
            "data_role": "tuning_eligible_development",
            "calibration_or_blind_used": False,
            "execution_prerequisite": "#259 must pass before this diagnostic is executed",
            "behavior_change": False,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument(
        "--variant",
        choices=("gte-agreement", "gte-agreement-bge"),
        required=True,
    )
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    cases = json.loads(args.corpus.read_text(encoding="utf-8"))
    if not isinstance(cases, list) or any(not isinstance(item, dict) for item in cases):
        raise ValueError("corpus must be a JSON object list")

    result = run(cases, variant=args.variant)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "variant": args.variant,
                "primary_zero_false": result["summary"]["primary_zero_false"],
                "promotion_gate_pass": result["summary"]["promotion_gate_pass"],
                "base_abstentions": result["summary"]["base_abstentions"],
                "gte_agreement_on_base_abstentions": result["summary"][
                    "gte_agreement_on_base_abstentions"
                ],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
