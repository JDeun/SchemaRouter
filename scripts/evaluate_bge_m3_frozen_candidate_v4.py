"""Execute the frozen BGE-M3 dual-view candidate through SchemaPlanner."""

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
    MODEL_NAME,
    MODEL_REVISION,
    AcceptAllRegisteredRecallBackend,
    FrozenBgeM3DualViewBackend,
)
from schemarouter import DecisionPolicy, PlanRequest, SchemaPlanner  # noqa: E402


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
        "p50": _quantile(values, 0.50),
        "p90": _quantile(values, 0.90),
        "p95": _quantile(values, 0.95),
        "max": max(values) if values else None,
        "mean": statistics.fmean(values) if values else None,
    }


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


def _route_from_plan(plan: Any) -> str | None:
    if not plan.calls:
        return None
    call = plan.calls[0]
    return f"{call.tool}.{call.endpoint}"


def _tool(route: str | None) -> str | None:
    if route is None or "." not in route:
        return None
    return route.split(".", 1)[0]


def evaluate(cases: list[dict[str, Any]]) -> dict[str, Any]:
    registry = reference_registry()
    model = _load_model()
    embed = _embedder(model)

    static_started = time.perf_counter_ns()
    backend = FrozenBgeM3DualViewBackend(registry, embed)
    static_ms = (time.perf_counter_ns() - static_started) / 1_000_000

    planner = SchemaPlanner(
        registry,
        decision_backend=backend,
        decision_policy=DecisionPolicy(
            enabled=True,
            tool_selection=True,
            endpoint_selection=True,
            field_selection=False,
            evidence_sufficiency=False,
            recall_on_empty=False,
            candidate_abstention="no_route",
            fallback="error",
        ),
        candidate_recall_backend=AcceptAllRegisteredRecallBackend(),
        candidate_recall_limit=len(backend.route_ids),
    )

    allowed_routes = set(backend.route_ids)
    rows: list[dict[str, Any]] = []
    planner_latencies: list[float] = []
    direct_latencies: list[float] = []

    for case in cases:
        query = str(case["query"])
        expected = case.get("expected")

        direct_started = time.perf_counter_ns()
        direct = backend.score_routes(query, backend.route_ids)
        direct_latency_ms = (
            time.perf_counter_ns() - direct_started
        ) / 1_000_000
        direct_latencies.append(direct_latency_ms)
        direct_predicted = (
            str(direct["top_route"])
            if bool(direct["accepted"])
            else None
        )

        backend.last_result = None
        started = time.perf_counter_ns()
        try:
            plan = planner.plan(PlanRequest(query=query, max_calls=1))
            planner_latency_ms = (
                time.perf_counter_ns() - started
            ) / 1_000_000
            planner_latencies.append(planner_latency_ms)
            predicted = _route_from_plan(plan)
            decision = backend.last_result
            metadata = decision.metadata if decision is not None else {}

            rows.append(
                {
                    "case_id": case.get("id"),
                    "category": case.get("category"),
                    "language": case.get("language"),
                    "unsupported_family": case.get("unsupported_family"),
                    "expected": expected,
                    "direct_predicted": direct_predicted,
                    "predicted": predicted,
                    "planner_matches_direct": predicted == direct_predicted,
                    "invalid_plan": (
                        predicted is not None and predicted not in allowed_routes
                    ),
                    "direct_top_route": direct["top_route"],
                    "direct_top_score": direct["top_score"],
                    "direct_top_margin": direct["top_margin"],
                    "direct_accepted": direct["accepted"],
                    "decision_top_route": metadata.get("top_route"),
                    "decision_top_score": metadata.get("top_score"),
                    "decision_top_margin": metadata.get("top_margin"),
                    "decision_accepted": metadata.get("accepted"),
                    "planner_latency_ms": planner_latency_ms,
                    "direct_latency_ms": direct_latency_ms,
                    "warnings": list(plan.warnings),
                    "error": None,
                }
            )
        except Exception as exc:  # noqa: BLE001 - confirmation records every failure.
            planner_latency_ms = (
                time.perf_counter_ns() - started
            ) / 1_000_000
            planner_latencies.append(planner_latency_ms)
            rows.append(
                {
                    "case_id": case.get("id"),
                    "category": case.get("category"),
                    "language": case.get("language"),
                    "unsupported_family": case.get("unsupported_family"),
                    "expected": expected,
                    "direct_predicted": direct_predicted,
                    "predicted": None,
                    "planner_matches_direct": False,
                    "invalid_plan": False,
                    "direct_top_route": direct["top_route"],
                    "direct_top_score": direct["top_score"],
                    "direct_top_margin": direct["top_margin"],
                    "direct_accepted": direct["accepted"],
                    "decision_top_route": None,
                    "decision_top_score": None,
                    "decision_top_margin": None,
                    "decision_accepted": None,
                    "planner_latency_ms": planner_latency_ms,
                    "direct_latency_ms": direct_latency_ms,
                    "warnings": [],
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )

    supported = [row for row in rows if row["expected"] is not None]
    near = [
        row
        for row in rows
        if row["category"] == "near_domain_unsupported_operation"
    ]
    ood = [
        row
        for row in rows
        if row["category"] == "out_of_domain"
    ]
    no_route = [row for row in rows if row["expected"] is None]

    supported_correct = sum(
        row["predicted"] == row["expected"]
        for row in supported
    )
    near_rejected = sum(row["predicted"] is None for row in near)
    ood_rejected = sum(row["predicted"] is None for row in ood)
    false_routes = sum(row["predicted"] is not None for row in no_route)
    invalid_plans = sum(bool(row["invalid_plan"]) for row in rows)
    errors = sum(row["error"] is not None for row in rows)
    parity_mismatches = sum(
        not bool(row["planner_matches_direct"])
        for row in rows
    )
    rank2_fallthroughs = sum(
        bool(row["direct_accepted"]) is False
        and row["predicted"] is not None
        for row in rows
    )

    wrong_tool = sum(
        row["predicted"] is not None
        and row["expected"] is not None
        and _tool(str(row["predicted"])) != _tool(str(row["expected"]))
        for row in supported
    )
    wrong_endpoint = sum(
        row["predicted"] is not None
        and row["expected"] is not None
        and _tool(str(row["predicted"])) == _tool(str(row["expected"]))
        and row["predicted"] != row["expected"]
        for row in supported
    )

    metrics = {
        "supported_exact_route_accuracy": (
            supported_correct / len(supported) if supported else 0.0
        ),
        "near_domain_unsupported_rejection": (
            near_rejected / len(near) if near else 1.0
        ),
        "out_of_domain_rejection": (
            ood_rejected / len(ood) if ood else 1.0
        ),
        "false_routes": false_routes,
        "false_route_rate": (
            false_routes / len(no_route) if no_route else 0.0
        ),
        "wrong_tool": wrong_tool,
        "wrong_endpoint": wrong_endpoint,
        "invalid_plans": invalid_plans,
        "execution_errors": errors,
        "planner_direct_parity_mismatches": parity_mismatches,
        "rank2_fallthroughs": rank2_fallthroughs,
        "planner_latency_ms": _distribution(planner_latencies),
        "direct_scoring_latency_ms": _distribution(direct_latencies),
        "static_route_embedding_ms": static_ms,
    }

    frozen_projection_matches = (
        supported_correct == 960
        and false_routes == 6
        and near_rejected == 570
        and ood_rejected == 72
    )
    gates = {
        "planner_matches_direct_case_by_case": parity_mismatches == 0,
        "frozen_projection_counts_match": frozen_projection_matches,
        "supported_exact_route_accuracy": (
            metrics["supported_exact_route_accuracy"] >= 0.70
        ),
        "near_domain_unsupported_rejection": (
            metrics["near_domain_unsupported_rejection"] >= 0.96
        ),
        "false_route_rate_screening": metrics["false_route_rate"] <= 0.02,
        "false_route_rate_long_term_safety": metrics["false_route_rate"] <= 0.01,
        "invalid_plans": invalid_plans == 0,
        "execution_errors": errors == 0,
        "rank2_fallthroughs": rank2_fallthroughs == 0,
    }

    return {
        "candidate": {
            "name": "bge-m3-dual-view-budget6-v1",
            "model": MODEL_NAME,
            "model_revision": MODEL_REVISION,
            "registered_routes": sorted(allowed_routes),
            "registered_route_count": len(allowed_routes),
            "threshold_profile": "false-budget-6",
        },
        "cases": len(rows),
        "supported_cases": len(supported),
        "near_domain_cases": len(near),
        "out_of_domain_cases": len(ood),
        "metrics": metrics,
        "gates": gates,
        "all_confirmation_gates_pass": all(gates.values()),
        "rows": rows,
        "policy": {
            "calibration_or_blind_used": False,
            "no_retuning": True,
            "gate_failure_behavior": "abstain_no_route",
            "execution_authority": "registered routes only",
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
                "all_confirmation_gates_pass": result[
                    "all_confirmation_gates_pass"
                ],
                "metrics": result["metrics"],
                "gates": result["gates"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    if not result["all_confirmation_gates_pass"]:
        raise SystemExit("frozen executable candidate failed confirmation gates")


if __name__ == "__main__":
    main()
