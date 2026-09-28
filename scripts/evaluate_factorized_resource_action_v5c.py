"""Evaluate factorized resource-action experiment #355 on a frozen surface."""

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
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from benchmarks.factorized_resource_action import (  # noqa: E402
    MODEL_NAME,
    MODEL_REVISION,
    NON_TOOL_ACTIONS,
    FactorizedResourceActionRouter,
)
from benchmarks.operation_routing_v5c_catalog import (  # noqa: E402
    confirmation_registry,
    development_registry,
)


def _quantile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    pos = q * (len(ordered) - 1)
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return ordered[lo]
    weight = pos - lo
    return ordered[lo] * (1.0 - weight) + ordered[hi] * weight


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


def _load_model() -> Any:
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


def _tool(route: str | None) -> str | None:
    if route is None or "." not in route:
        return None
    return route.split(".", 1)[0]


def _registry(surface: str):
    if surface == "development":
        return development_registry()
    if surface == "confirmation":
        return confirmation_registry()
    raise ValueError("surface must be development or confirmation")


def evaluate(surface: str, cases: list[dict[str, Any]]) -> dict[str, Any]:
    registry = _registry(surface)
    model = _load_model()
    embed = _embedder(model)

    static_started = time.perf_counter_ns()
    router = FactorizedResourceActionRouter(registry, embed)
    static_ms = (time.perf_counter_ns() - static_started) / 1_000_000

    allowed = set(router.route_ids)
    rows: list[dict[str, Any]] = []
    latencies: list[float] = []
    authority_violations = 0
    execution_errors = 0

    for case in cases:
        started = time.perf_counter_ns()
        try:
            result = router.route(str(case["query"]))
            latency_ms = (time.perf_counter_ns() - started) / 1_000_000
            latencies.append(latency_ms)
            predicted = result["predicted"]
            if predicted is not None and predicted not in allowed:
                authority_violations += 1
            expected = case.get("expected")
            expected_tool = _tool(expected)
            if expected_tool is None and case.get("unsupported_family"):
                expected_tool = str(case["unsupported_family"]).rsplit(".", 1)[0]
            expected_action = None
            if expected is not None:
                expected_action = router.contracts[str(expected)].action
            elif case.get("unsupported_action"):
                expected_action = str(case["unsupported_action"])

            rows.append(
                {
                    "case_id": case["id"],
                    "query": case["query"],
                    "category": case["category"],
                    "language": case["language"],
                    "expected": expected,
                    "expected_tool": expected_tool,
                    "expected_action": expected_action,
                    "predicted": predicted,
                    "resource_tool": result["resource_tool"],
                    "action": result["frame"]["action"],
                    "action_score": result["frame"]["action_score"],
                    "compatible_routes": result["compatible_routes"],
                    "reason": result["reason"],
                    "diagnostic_raw_top_route": result["diagnostic_raw_top_route"],
                    "latency_ms": latency_ms,
                    "error": None,
                }
            )
        except Exception as exc:  # noqa: BLE001
            latency_ms = (time.perf_counter_ns() - started) / 1_000_000
            latencies.append(latency_ms)
            execution_errors += 1
            rows.append(
                {
                    "case_id": case["id"],
                    "query": case["query"],
                    "category": case["category"],
                    "language": case["language"],
                    "expected": case.get("expected"),
                    "expected_tool": None,
                    "expected_action": None,
                    "predicted": None,
                    "resource_tool": None,
                    "action": None,
                    "action_score": None,
                    "compatible_routes": [],
                    "reason": "execution_error",
                    "diagnostic_raw_top_route": None,
                    "latency_ms": latency_ms,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )

    supported = [row for row in rows if row["expected"] is not None]
    near = [row for row in rows if row["category"] == "near_domain_unsupported_operation"]
    ood = [row for row in rows if row["category"] == "out_of_domain"]
    unsupported = [*near, *ood]

    supported_correct = sum(row["predicted"] == row["expected"] for row in supported)
    near_rejected = sum(row["predicted"] is None for row in near)
    ood_rejected = sum(row["predicted"] is None for row in ood)
    false_routes = sum(row["predicted"] is not None for row in unsupported)

    supported_tool_correct = sum(
        row["resource_tool"] == row["expected_tool"] for row in supported
    )
    near_tool_correct = sum(
        row["resource_tool"] == row["expected_tool"] for row in near
    )
    supported_action_correct = sum(
        row["action"] == row["expected_action"] for row in supported
    )
    near_action_correct = sum(
        row["action"] == row["expected_action"] for row in near
    )
    ood_non_tool = sum(row["action"] in NON_TOOL_ACTIONS for row in ood)

    raw_supported_exact = sum(
        row["diagnostic_raw_top_route"] == row["expected"]
        for row in supported
    )

    latency = _distribution(latencies)
    metrics = {
        "supported_exact_route_accuracy": supported_correct / len(supported),
        "near_domain_unsupported_rejection": near_rejected / len(near),
        "out_of_domain_rejection": ood_rejected / len(ood),
        "false_routes": false_routes,
        "false_route_rate": false_routes / len(unsupported),
        "resource_tool_accuracy_supported": supported_tool_correct / len(supported),
        "resource_tool_accuracy_near": near_tool_correct / len(near),
        "action_accuracy_supported": supported_action_correct / len(supported),
        "action_accuracy_near": near_action_correct / len(near),
        "ood_non_tool_action_rate": ood_non_tool / len(ood),
        "diagnostic_global_raw_exact": raw_supported_exact / len(supported),
        "empty_intersection_count": sum(
            row["reason"] == "empty_factorized_capability_intersection"
            for row in rows
        ),
        "authority_violations": authority_violations,
        "execution_errors": execution_errors,
        "latency_ms": latency,
        "static_embedding_ms": static_ms,
    }

    p95 = latency["p95"]
    gates = {
        "supported_exact_route_accuracy": metrics["supported_exact_route_accuracy"] >= 0.85,
        "near_domain_unsupported_rejection": metrics["near_domain_unsupported_rejection"] >= 0.97,
        "out_of_domain_rejection": metrics["out_of_domain_rejection"] == 1.0,
        "false_route_rate": metrics["false_route_rate"] <= 0.01,
        "authority_violations": authority_violations == 0,
        "execution_errors": execution_errors == 0,
        "p95_latency": p95 is not None and float(p95) <= 250.0,
    }

    return {
        "experiment": "factorized-resource-conditioned-action-v1",
        "issue": 355,
        "surface": f"0.12-C-{surface}",
        "case_count": len(rows),
        "supported_cases": len(supported),
        "near_domain_cases": len(near),
        "out_of_domain_cases": len(ood),
        "metrics": metrics,
        "gates": gates,
        "surface_pass": all(gates.values()),
        "rows": rows,
        "policy": {
            "prior_surfaces_used_for_tuning": False,
            "learned_veto": False,
            "resource_threshold": False,
            "action_threshold": False,
            "action_margin_threshold": False,
            "route_specific_thresholds": False,
            "pseudo_route": False,
            "cross_tool_fallback": False,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--surface", choices=("development", "confirmation"), required=True)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    cases = json.loads(args.corpus.read_text(encoding="utf-8"))
    if not isinstance(cases, list) or any(not isinstance(item, dict) for item in cases):
        raise ValueError("corpus must be a JSON object list")

    result = evaluate(args.surface, cases)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "surface": result["surface"],
                "surface_pass": result["surface_pass"],
                "metrics": result["metrics"],
                "gates": result["gates"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
