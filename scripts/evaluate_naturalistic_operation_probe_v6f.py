"""Evaluate frozen #404 naturalistic operation-probe membership on DEV only."""

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

from benchmarks.operation_routing_v6f_catalog import development_registry  # noqa: E402
from benchmarks.schema_adb_baseline import BGE_MODEL, BGE_REVISION  # noqa: E402
from benchmarks.schema_naturalistic_operation_probe import (  # noqa: E402
    BACKGROUND,
    MINILM_MODEL,
    MINILM_REVISION,
    TOOL_OPERATION,
    SchemaNaturalisticProbeRouter,
)


def _q(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    pos = q * (len(ordered) - 1)
    lo, hi = math.floor(pos), math.ceil(pos)
    if lo == hi:
        return ordered[lo]
    w = pos - lo
    return ordered[lo] * (1 - w) + ordered[hi] * w


def _dist(values: list[float]) -> dict[str, float | int | None]:
    return {
        "count": len(values),
        "min": min(values) if values else None,
        "p50": _q(values, 0.50),
        "p90": _q(values, 0.90),
        "p95": _q(values, 0.95),
        "max": max(values) if values else None,
        "mean": statistics.fmean(values) if values else None,
    }


def _embedder(model: Any):
    def embed(texts: list[str]) -> list[list[float]]:
        return model.encode(
            texts,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        ).tolist()
    return embed


def evaluate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    from sentence_transformers import SentenceTransformer

    if len(rows) != 552:
        raise ValueError("V6F probe DEV must contain 552 rows")

    load_started = time.perf_counter_ns()
    bge = SentenceTransformer(
        BGE_MODEL,
        revision=BGE_REVISION,
        trust_remote_code=False,
        device="cpu",
    )
    minilm = SentenceTransformer(
        MINILM_MODEL,
        revision=MINILM_REVISION,
        trust_remote_code=False,
        device="cpu",
    )
    model_load_ms = (time.perf_counter_ns() - load_started) / 1_000_000

    compile_started = time.perf_counter_ns()
    router = SchemaNaturalisticProbeRouter(
        development_registry(),
        _embedder(bge),
        _embedder(minilm),
    )
    compile_ms = (time.perf_counter_ns() - compile_started) / 1_000_000

    results: list[dict[str, Any]] = []
    latencies: list[float] = []
    errors = 0
    switches = 0
    authority = 0

    for case in rows:
        started = time.perf_counter_ns()
        try:
            result = router.route(str(case["query"]))
            elapsed = (time.perf_counter_ns() - started) / 1_000_000
            latencies.append(elapsed)
            predicted = result["predicted"]
            raw_top = result["raw_top_route"]
            if predicted is not None and predicted != raw_top:
                switches += 1
                authority += 1
            if predicted is not None and predicted not in router.route_ids:
                authority += 1
            results.append({
                "id": case["id"],
                "query": case["query"],
                "category": case["category"],
                "language": case["language"],
                "expected": case.get("expected"),
                "predicted": predicted,
                "raw_top_route": raw_top,
                "scope_class": result["scope_class"],
                "operation_class": result["operation_class"],
                "reason": result["reason"],
                "latency_ms": elapsed,
                "error": None,
            })
        except Exception as exc:  # noqa: BLE001
            elapsed = (time.perf_counter_ns() - started) / 1_000_000
            latencies.append(elapsed)
            errors += 1
            results.append({
                "id": case["id"],
                "query": case["query"],
                "category": case["category"],
                "language": case["language"],
                "expected": case.get("expected"),
                "predicted": None,
                "raw_top_route": None,
                "scope_class": None,
                "operation_class": None,
                "reason": "exception",
                "latency_ms": elapsed,
                "error": f"{type(exc).__name__}: {exc}",
            })

    supported = [r for r in results if r["category"] == "supported"]
    near = [r for r in results if r["category"] == "near_domain_unsupported_operation"]
    ood = [r for r in results if r["category"] == "out_of_domain"]
    unsupported = [*near, *ood]

    exact = sum(r["predicted"] == r["expected"] for r in supported)
    raw_exact = sum(r["raw_top_route"] == r["expected"] for r in supported)
    raw_tool = sum(
        r["raw_top_route"] is not None
        and str(r["raw_top_route"]).split(".", 1)[0]
        == str(r["expected"]).split(".", 1)[0]
        for r in supported
    )
    near_rej = sum(r["predicted"] is None for r in near)
    ood_rej = sum(r["predicted"] is None for r in ood)
    false_routes = sum(r["predicted"] is not None for r in unsupported)
    raw_correct_veto = sum(
        r["raw_top_route"] == r["expected"] and r["predicted"] is None
        for r in supported
    )
    vetoes = sum(r["predicted"] is None for r in results)
    true_vetoes = sum(r["predicted"] is None for r in unsupported)

    reason_counts: dict[str, int] = {}
    scope_counts: dict[str, dict[str, int]] = {}
    for row in results:
        reason_counts[row["reason"]] = reason_counts.get(row["reason"], 0) + 1
        category = str(row["category"])
        scope = str(row["scope_class"])
        scope_counts.setdefault(category, {})
        scope_counts[category][scope] = scope_counts[category].get(scope, 0) + 1

    per_language = {}
    for lang in sorted({str(r["language"]) for r in results}):
        group = [r for r in results if r["language"] == lang]
        s = [r for r in group if r["category"] == "supported"]
        u = [r for r in group if r["category"] != "supported"]
        per_language[lang] = {
            "cases": len(group),
            "supported_exact": sum(r["predicted"] == r["expected"] for r in s) / len(s),
            "unsupported_rejection": sum(r["predicted"] is None for r in u) / len(u),
        }

    latency = _dist(latencies)
    p95 = latency["p95"]
    metrics = {
        "supported_exact_route_accuracy": exact / len(supported),
        "raw_supported_exact_route_accuracy": raw_exact / len(supported),
        "raw_supported_tool_accuracy": raw_tool / len(supported),
        "near_domain_unsupported_rejection": near_rej / len(near),
        "out_of_domain_rejection": ood_rej / len(ood),
        "false_routes": false_routes,
        "false_route_rate": false_routes / len(unsupported),
        "raw_correct_winner_vetoed": raw_correct_veto,
        "raw_correct_winner_veto_rate": raw_correct_veto / raw_exact if raw_exact else 0.0,
        "vetoes": vetoes,
        "true_unsupported_vetoes": true_vetoes,
        "veto_precision": true_vetoes / vetoes if vetoes else 0.0,
        "veto_recall": true_vetoes / len(unsupported),
        "reason_counts": reason_counts,
        "scope_counts_by_category": scope_counts,
        "query_latency_ms": latency,
        "model_load_ms": model_load_ms,
        "probe_and_route_compile_ms": compile_ms,
        "positive_route_switches": switches,
        "authority_violations": authority,
        "execution_errors": errors,
        "per_language": per_language,
    }
    gates = {
        "supported_exact_route_accuracy": metrics["supported_exact_route_accuracy"] >= 0.85,
        "near_domain_unsupported_rejection": metrics["near_domain_unsupported_rejection"] >= 0.97,
        "out_of_domain_rejection": metrics["out_of_domain_rejection"] == 1.0,
        "false_route_rate": metrics["false_route_rate"] <= 0.01,
        "authority_violations": authority == 0,
        "positive_route_switches": switches == 0,
        "execution_errors": errors == 0,
    }
    runtime = p95 is not None and float(p95) <= 250.0
    return {
        "experiment": "naturalistic-generic-operation-linear-probe-membership-v1",
        "issue": 404,
        "surface": "V6F-development",
        "metrics": metrics,
        "quality_gates": gates,
        "runtime_gate": runtime,
        "quality_pass": all(gates.values()),
        "surface_pass": all(gates.values()) and runtime,
        "policy": {
            "confirmation_scored": False,
            "raw_bge_is_sole_positive_selector": True,
            "probe_veto_only": True,
            "positive_rerank": False,
            "endpoint_switch": False,
            "rank2_fallback": False,
            "pseudo_route": False,
            "probability_threshold": None,
            "margin_threshold": None,
            "dev_selected_hyperparameters": False,
            "scope_labels": [TOOL_OPERATION, BACKGROUND],
        },
        "rows": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--development", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    rows = json.loads(args.development.read_text(encoding="utf-8"))
    result = evaluate(rows)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "surface": result["surface"],
        "quality_pass": result["quality_pass"],
        "runtime_gate": result["runtime_gate"],
        "surface_pass": result["surface_pass"],
        "metrics": result["metrics"],
        "quality_gates": result["quality_gates"],
    }, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
