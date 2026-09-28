"""Evaluate frozen V6G conformal E5 membership on CAL + DEV only."""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmarks.conformal_e5_membership import (  # noqa: E402
    CONFORMAL_ALPHA,
    E5_MODEL,
    E5_REVISION,
    ConformalE5MembershipRouter,
    E5CatalogMembershipScorer,
)
from benchmarks.operation_routing_v6g_catalog import (  # noqa: E402
    calibration_registry,
    development_registry,
)
from benchmarks.schema_adb_baseline import BGE_MODEL, BGE_REVISION  # noqa: E402


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


def _tool(route_id: str) -> str:
    return route_id.split(".", 1)[0]


def _load_models() -> tuple[Any, Any]:
    from sentence_transformers import SentenceTransformer

    e5 = SentenceTransformer(
        E5_MODEL,
        revision=E5_REVISION,
        trust_remote_code=False,
        device="cpu",
    )
    bge = SentenceTransformer(
        BGE_MODEL,
        revision=BGE_REVISION,
        trust_remote_code=False,
        device="cpu",
    )
    return e5, bge


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


def evaluate(
    calibration_rows: list[dict[str, Any]],
    development_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    if len(calibration_rows) != 552 or len(development_rows) != 552:
        raise ValueError("V6G expects 552 CAL and 552 DEV rows")

    model_load_started = time.perf_counter_ns()
    e5_model, bge_model = _load_models()
    model_load_ms = (time.perf_counter_ns() - model_load_started) / 1_000_000
    e5_embed = _embedder(e5_model)
    bge_embed = _embedder(bge_model)

    cal_static_started = time.perf_counter_ns()
    cal_scorer = E5CatalogMembershipScorer(
        calibration_registry(),
        e5_embed,
    )
    cal_static_ms = (time.perf_counter_ns() - cal_static_started) / 1_000_000

    calibration_scores: list[dict[str, Any]] = []
    cal_query_latencies: list[float] = []
    for case in calibration_rows:
        started = time.perf_counter_ns()
        scored = cal_scorer.score(str(case["query"]))
        elapsed = (time.perf_counter_ns() - started) / 1_000_000
        cal_query_latencies.append(elapsed)
        calibration_scores.append(
            {
                "id": case["id"],
                "category": case["category"],
                "language": case["language"],
                "catalog_score": scored["catalog_score"],
            }
        )

    unsupported_calibration = [
        float(row["catalog_score"])
        for row in calibration_scores
        if row["category"] != "supported"
    ]
    if len(unsupported_calibration) != 324:
        raise ValueError("V6G requires exactly 324 unsupported calibration scores")

    dev_static_started = time.perf_counter_ns()
    router = ConformalE5MembershipRouter(
        development_registry(),
        bge_embedder=bge_embed,
        e5_embedder=e5_embed,
        calibration_unsupported_scores=unsupported_calibration,
    )
    dev_static_ms = (time.perf_counter_ns() - dev_static_started) / 1_000_000

    result_rows: list[dict[str, Any]] = []
    latencies: list[float] = []
    errors = 0
    authority_violations = 0
    switches = 0

    for case in development_rows:
        started = time.perf_counter_ns()
        try:
            result = router.route(str(case["query"]))
            elapsed = (time.perf_counter_ns() - started) / 1_000_000
            latencies.append(elapsed)
            predicted = result["predicted"]
            raw_top = result["raw_top_route"]
            if predicted is not None and predicted != raw_top:
                switches += 1
                authority_violations += 1
            if predicted is not None and predicted not in router.raw_retriever.route_ids:
                authority_violations += 1
            result_rows.append(
                {
                    "id": case["id"],
                    "query": case["query"],
                    "category": case["category"],
                    "language": case["language"],
                    "expected": case.get("expected"),
                    "predicted": predicted,
                    "raw_top_route": raw_top,
                    "catalog_score": result["catalog_score"],
                    "p_unsupported": result["p_unsupported"],
                    "diagnostic_e5_top_route": result[
                        "diagnostic_e5_top_route"
                    ],
                    "reason": result["reason"],
                    "latency_ms": elapsed,
                    "error": None,
                }
            )
        except Exception as exc:  # noqa: BLE001
            elapsed = (time.perf_counter_ns() - started) / 1_000_000
            latencies.append(elapsed)
            errors += 1
            result_rows.append(
                {
                    "id": case["id"],
                    "query": case["query"],
                    "category": case["category"],
                    "language": case["language"],
                    "expected": case.get("expected"),
                    "predicted": None,
                    "raw_top_route": None,
                    "catalog_score": None,
                    "p_unsupported": None,
                    "diagnostic_e5_top_route": None,
                    "reason": "exception",
                    "latency_ms": elapsed,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )

    supported = [row for row in result_rows if row["category"] == "supported"]
    near = [
        row
        for row in result_rows
        if row["category"] == "near_domain_unsupported_operation"
    ]
    ood = [row for row in result_rows if row["category"] == "out_of_domain"]
    unsupported = [*near, *ood]

    supported_exact = sum(
        row["predicted"] == row["expected"] for row in supported
    )
    raw_exact = sum(
        row["raw_top_route"] == row["expected"] for row in supported
    )
    raw_tool = sum(
        row["raw_top_route"] is not None
        and _tool(str(row["raw_top_route"])) == _tool(str(row["expected"]))
        for row in supported
    )
    near_rejected = sum(row["predicted"] is None for row in near)
    ood_rejected = sum(row["predicted"] is None for row in ood)
    false_routes = sum(row["predicted"] is not None for row in unsupported)
    raw_correct_vetoed = sum(
        row["raw_top_route"] == row["expected"] and row["predicted"] is None
        for row in supported
    )
    vetoes = sum(row["predicted"] is None for row in result_rows)
    true_unsupported_vetoes = sum(row["predicted"] is None for row in unsupported)

    def vals(rows: list[dict[str, Any]], key: str) -> list[float]:
        return [
            float(row[key])
            for row in rows
            if row.get(key) is not None
        ]

    cal_supported = [
        float(row["catalog_score"])
        for row in calibration_scores
        if row["category"] == "supported"
    ]
    cal_near = [
        float(row["catalog_score"])
        for row in calibration_scores
        if row["category"] == "near_domain_unsupported_operation"
    ]
    cal_ood = [
        float(row["catalog_score"])
        for row in calibration_scores
        if row["category"] == "out_of_domain"
    ]

    latency = _distribution(latencies)
    p95 = latency["p95"]
    metrics: dict[str, Any] = {
        "supported_exact_route_accuracy": supported_exact / len(supported),
        "raw_supported_exact_route_accuracy": raw_exact / len(supported),
        "raw_supported_tool_accuracy": raw_tool / len(supported),
        "near_domain_unsupported_rejection": near_rejected / len(near),
        "out_of_domain_rejection": ood_rejected / len(ood),
        "false_routes": false_routes,
        "false_route_rate": false_routes / len(unsupported),
        "raw_correct_winner_vetoed": raw_correct_vetoed,
        "raw_correct_winner_veto_rate": (
            raw_correct_vetoed / raw_exact if raw_exact else 0.0
        ),
        "vetoes": vetoes,
        "true_unsupported_vetoes": true_unsupported_vetoes,
        "veto_precision": (
            true_unsupported_vetoes / vetoes if vetoes else 0.0
        ),
        "veto_recall": true_unsupported_vetoes / len(unsupported),
        "catalog_score": {
            "supported": _distribution(vals(supported, "catalog_score")),
            "near_domain": _distribution(vals(near, "catalog_score")),
            "ood": _distribution(vals(ood, "catalog_score")),
        },
        "p_unsupported": {
            "supported": _distribution(vals(supported, "p_unsupported")),
            "near_domain": _distribution(vals(near, "p_unsupported")),
            "ood": _distribution(vals(ood, "p_unsupported")),
        },
        "calibration_catalog_score": {
            "supported_diagnostic": _distribution(cal_supported),
            "near_domain_unsupported": _distribution(cal_near),
            "ood": _distribution(cal_ood),
            "unsupported_combined": _distribution(unsupported_calibration),
        },
        "calibration_query_latency_ms": _distribution(cal_query_latencies),
        "combined_query_latency_ms": latency,
        "model_load_ms": model_load_ms,
        "calibration_static_e0_encode_ms": cal_static_ms,
        "development_static_router_encode_ms": dev_static_ms,
        "positive_route_switches": switches,
        "authority_violations": authority_violations,
        "execution_errors": errors,
    }

    per_language: dict[str, dict[str, float | int]] = {}
    for language in sorted({str(row["language"]) for row in result_rows}):
        rows = [row for row in result_rows if row["language"] == language]
        supp = [row for row in rows if row["category"] == "supported"]
        unsup = [row for row in rows if row["category"] != "supported"]
        per_language[language] = {
            "cases": len(rows),
            "supported_exact": (
                sum(row["predicted"] == row["expected"] for row in supp)
                / len(supp)
            ),
            "unsupported_rejection": (
                sum(row["predicted"] is None for row in unsup) / len(unsup)
            ),
        }
    metrics["per_language"] = per_language

    quality_gates = {
        "supported_exact_route_accuracy": (
            metrics["supported_exact_route_accuracy"] >= 0.85
        ),
        "near_domain_unsupported_rejection": (
            metrics["near_domain_unsupported_rejection"] >= 0.97
        ),
        "out_of_domain_rejection": metrics["out_of_domain_rejection"] == 1.0,
        "false_route_rate": metrics["false_route_rate"] <= 0.01,
        "authority_violations": authority_violations == 0,
        "positive_route_switches": switches == 0,
        "execution_errors": errors == 0,
    }
    runtime_gate = p95 is not None and float(p95) <= 250.0

    return {
        "experiment": "conformal-multilingual-e5-catalog-membership-v1",
        "issue": 412,
        "surface": "V6G-development",
        "models": {
            "bge": {"name": BGE_MODEL, "revision": BGE_REVISION},
            "e5": {"name": E5_MODEL, "revision": E5_REVISION},
        },
        "metrics": metrics,
        "quality_gates": quality_gates,
        "runtime_gate": runtime_gate,
        "quality_pass": all(quality_gates.values()),
        "surface_pass": all(quality_gates.values()) and runtime_gate,
        "policy": {
            "confirmation_scored": False,
            "calibration_used_for_rule": True,
            "calibration_supported_changes_rule": False,
            "calibration_unsupported_count": len(unsupported_calibration),
            "conformal_alpha": CONFORMAL_ALPHA,
            "unsupported_null": True,
            "conservative_tie_rule": True,
            "dev_selected_threshold": False,
            "alpha_sweep": False,
            "score_threshold_grid": False,
            "platt": False,
            "isotonic": False,
            "raw_bge_is_sole_positive_selector": True,
            "e5_has_positive_route_authority": False,
            "positive_rerank": False,
            "endpoint_switch": False,
            "rank2_fallback": False,
            "pseudo_route": False,
            "score_fusion": False,
            "exchangeability_required_for_formal_control": True,
        },
        "calibration_rows": calibration_scores,
        "rows": result_rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--calibration", type=Path, required=True)
    parser.add_argument("--development", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    calibration_rows = json.loads(
        args.calibration.read_text(encoding="utf-8")
    )
    development_rows = json.loads(
        args.development.read_text(encoding="utf-8")
    )
    if not isinstance(calibration_rows, list) or not isinstance(
        development_rows,
        list,
    ):
        raise ValueError("V6G corpora must be lists")

    result = evaluate(calibration_rows, development_rows)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "surface": result["surface"],
                "quality_pass": result["quality_pass"],
                "runtime_gate": result["runtime_gate"],
                "surface_pass": result["surface_pass"],
                "metrics": result["metrics"],
                "quality_gates": result["quality_gates"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
