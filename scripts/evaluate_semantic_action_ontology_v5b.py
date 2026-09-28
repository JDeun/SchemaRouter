"""Evaluate semantic-action-ontology experiment #349 on a frozen surface."""

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

from benchmarks.operation_routing_v5b_catalog import (  # noqa: E402
    confirmation_registry,
    development_registry,
)
from benchmarks.semantic_action_ontology import (  # noqa: E402
    MODEL_NAME,
    MODEL_REVISION,
    SemanticActionOntologyRouter,
)


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


def _language_metrics(rows: list[dict[str, Any]]) -> dict[str, dict[str, float | int]]:
    result: dict[str, dict[str, float | int]] = {}
    for language in sorted({str(row["language"]) for row in rows}):
        selected = [row for row in rows if row["language"] == language]
        supported = [row for row in selected if row["expected"] is not None]
        unsupported = [row for row in selected if row["expected"] is None]
        result[language] = {
            "cases": len(selected),
            "supported_exact": (
                sum(row["predicted"] == row["expected"] for row in supported)
                / len(supported)
                if supported
                else 0.0
            ),
            "unsupported_rejection": (
                sum(row["predicted"] is None for row in unsupported)
                / len(unsupported)
                if unsupported
                else 1.0
            ),
        }
    return result


def _registry(surface: str):
    if surface == "development":
        return development_registry()
    if surface == "confirmation":
        return confirmation_registry()
    raise ValueError("surface must be development or confirmation")


def evaluate(
    *,
    surface: str,
    cases: list[dict[str, Any]],
) -> dict[str, Any]:
    registry = _registry(surface)
    model = _load_model()
    embed = _embedder(model)

    static_started = time.perf_counter_ns()
    router = SemanticActionOntologyRouter(registry, embed)
    static_ms = (time.perf_counter_ns() - static_started) / 1_000_000

    allowed_routes = set(router.route_ids)
    rows: list[dict[str, Any]] = []
    latencies: list[float] = []
    authority_violations = 0
    errors = 0

    for case in cases:
        query = str(case["query"])
        started = time.perf_counter_ns()
        try:
            result = router.route(query)
            elapsed_ms = (time.perf_counter_ns() - started) / 1_000_000
            latencies.append(elapsed_ms)
            predicted = result["predicted"]
            raw_top = str(result["raw_top_route"])
            if predicted is not None and predicted not in allowed_routes:
                authority_violations += 1

            rows.append(
                {
                    "case_id": case["id"],
                    "query": query,
                    "category": case["category"],
                    "language": case["language"],
                    "expected": case.get("expected"),
                    "unsupported_action": case.get("unsupported_action"),
                    "unsupported_family": case.get("unsupported_family"),
                    "predicted": predicted,
                    "raw_top_route": raw_top,
                    "raw_tool": result["raw_tool"],
                    "frame": result["frame"],
                    "compatible_routes": result["compatible_routes"],
                    "reason": result["reason"],
                    "latency_ms": elapsed_ms,
                    "error": None,
                }
            )
        except Exception as exc:  # noqa: BLE001 - evidence records every failure.
            elapsed_ms = (time.perf_counter_ns() - started) / 1_000_000
            latencies.append(elapsed_ms)
            errors += 1
            rows.append(
                {
                    "case_id": case["id"],
                    "query": query,
                    "category": case["category"],
                    "language": case["language"],
                    "expected": case.get("expected"),
                    "unsupported_action": case.get("unsupported_action"),
                    "unsupported_family": case.get("unsupported_family"),
                    "predicted": None,
                    "raw_top_route": None,
                    "raw_tool": None,
                    "frame": None,
                    "compatible_routes": [],
                    "reason": "execution_error",
                    "latency_ms": elapsed_ms,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )

    supported = [row for row in rows if row["expected"] is not None]
    near = [
        row
        for row in rows
        if row["category"] == "near_domain_unsupported_operation"
    ]
    ood = [row for row in rows if row["category"] == "out_of_domain"]
    unsupported = [*near, *ood]

    supported_correct = sum(
        row["predicted"] == row["expected"]
        for row in supported
    )
    near_rejected = sum(row["predicted"] is None for row in near)
    ood_rejected = sum(row["predicted"] is None for row in ood)
    false_routes = sum(row["predicted"] is not None for row in unsupported)
    raw_supported_exact = sum(
        row["raw_top_route"] == row["expected"]
        for row in supported
    )
    raw_supported_tool = sum(
        _tool(row["raw_top_route"]) == _tool(row["expected"])
        for row in supported
    )
    wrong_tool = sum(
        row["predicted"] is not None
        and row["expected"] is not None
        and _tool(row["predicted"]) != _tool(row["expected"])
        for row in supported
    )
    wrong_endpoint = sum(
        row["predicted"] is not None
        and row["expected"] is not None
        and _tool(row["predicted"]) == _tool(row["expected"])
        and row["predicted"] != row["expected"]
        for row in supported
    )
    empty_sets = sum(
        row["reason"] == "empty_semantic_capability_set"
        for row in rows
    )

    latency = _distribution(latencies)
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
            false_routes / len(unsupported) if unsupported else 0.0
        ),
        "raw_supported_exact_route_accuracy": (
            raw_supported_exact / len(supported) if supported else 0.0
        ),
        "raw_supported_tool_accuracy": (
            raw_supported_tool / len(supported) if supported else 0.0
        ),
        "wrong_tool": wrong_tool,
        "wrong_endpoint": wrong_endpoint,
        "empty_semantic_capability_set_count": empty_sets,
        "authority_violations": authority_violations,
        "execution_errors": errors,
        "latency_ms": latency,
        "static_embedding_ms": static_ms,
        "per_language": _language_metrics(rows),
    }

    p95 = latency["p95"]
    gates = {
        "supported_exact_route_accuracy": (
            metrics["supported_exact_route_accuracy"] >= 0.85
        ),
        "near_domain_unsupported_rejection": (
            metrics["near_domain_unsupported_rejection"] >= 0.97
        ),
        "out_of_domain_rejection": metrics["out_of_domain_rejection"] == 1.0,
        "false_route_rate": metrics["false_route_rate"] <= 0.01,
        "authority_violations": authority_violations == 0,
        "execution_errors": errors == 0,
        "p95_latency": p95 is not None and float(p95) <= 250.0,
    }

    return {
        "experiment": "semantic-action-ontology-v1",
        "issue": 349,
        "surface": f"0.12-B-{surface}",
        "model": {
            "name": MODEL_NAME,
            "revision": MODEL_REVISION,
            "schema_weight": 0.55,
            "action_weight": 0.45,
        },
        "case_count": len(rows),
        "supported_cases": len(supported),
        "near_domain_cases": len(near),
        "out_of_domain_cases": len(ood),
        "metrics": metrics,
        "gates": gates,
        "surface_pass": all(gates.values()),
        "rows": rows,
        "policy": {
            "old_0_11_dev_used": False,
            "fresh_270_used": False,
            "fresh_287_used": False,
            "fresh_326_used": False,
            "issue_338_holdout_used": False,
            "issue_347_dev_used": False,
            "issue_347_confirmation_used": False,
            "calibration_or_blind_used": False,
            "learned_veto": False,
            "route_specific_thresholds": False,
            "prototype_score_threshold": False,
            "prototype_margin_threshold": False,
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
    if not isinstance(cases, list) or any(
        not isinstance(item, dict) for item in cases
    ):
        raise ValueError("corpus must be a JSON object list")

    result = evaluate(surface=args.surface, cases=cases)
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
