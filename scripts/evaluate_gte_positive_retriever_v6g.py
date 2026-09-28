"""Evaluate frozen #409 GTE positive selector on supported DEV only."""

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

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmarks.operation_routing_v6g_catalog import development_registry  # noqa: E402
from benchmarks.schema_adb_baseline import (  # noqa: E402
    BGE_MODEL,
    BGE_REVISION,
    _action_text,
    _cosine,
    _schema_text,
    _to_vectors,
)

GTE_MODEL = "Alibaba-NLP/gte-multilingual-base"
GTE_REVISION = "087a024525fd6e2fe749cb4679d218d8bcc95bdd"
GTE_SCHEMA_WEIGHT = 0.25
GTE_ACTION_WEIGHT = 0.75
BGE_SCHEMA_WEIGHT = 0.55
BGE_ACTION_WEIGHT = 0.45


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
        "p50": _q(values, 0.5),
        "p90": _q(values, 0.9),
        "p95": _q(values, 0.95),
        "max": max(values) if values else None,
        "mean": statistics.fmean(values) if values else None,
    }


def _tool(route: str) -> str:
    return route.split(".", 1)[0]


class DenseDualViewRetriever:
    def __init__(
        self,
        registry: Any,
        model: Any,
        *,
        schema_weight: float,
        action_weight: float,
    ) -> None:
        self.model = model
        self.schema_weight = schema_weight
        self.action_weight = action_weight
        specs: dict[str, tuple[str, str]] = {}
        for tool in registry.tools():
            for endpoint in tool.endpoints:
                route = f"{tool.key}.{endpoint.name}"
                specs[route] = (_schema_text(tool, endpoint), _action_text(endpoint))
        self.route_ids = tuple(sorted(specs))
        count = len(self.route_ids)
        vectors = _to_vectors(
            model.encode(
                [
                    *(specs[r][0] for r in self.route_ids),
                    *(specs[r][1] for r in self.route_ids),
                ],
                normalize_embeddings=True,
                convert_to_numpy=True,
                show_progress_bar=False,
            ).tolist()
        )
        self.schema_vectors = dict(zip(self.route_ids, vectors[:count], strict=True))
        self.action_vectors = dict(zip(self.route_ids, vectors[count:], strict=True))

    def route(self, query: str) -> dict[str, Any]:
        started = time.perf_counter_ns()
        qv = _to_vectors(
            self.model.encode(
                [query],
                normalize_embeddings=True,
                convert_to_numpy=True,
                show_progress_bar=False,
            ).tolist()
        )[0]
        ranking = sorted(
            (
                (
                    self.schema_weight * _cosine(qv, self.schema_vectors[r])
                    + self.action_weight * _cosine(qv, self.action_vectors[r]),
                    r,
                )
                for r in self.route_ids
            ),
            key=lambda row: (-row[0], row[1]),
        )
        elapsed = (time.perf_counter_ns() - started) / 1_000_000
        return {
            "predicted": ranking[0][1],
            "top_score": ranking[0][0],
            "top2_margin": ranking[0][0] - ranking[1][0],
            "latency_ms": elapsed,
        }


def evaluate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    from sentence_transformers import SentenceTransformer

    if len(rows) != 228 or any(row.get("expected") is None for row in rows):
        raise ValueError("V6G GTE DEV must contain exactly 228 supported rows")

    registry = development_registry()

    load = time.perf_counter_ns()
    gte = SentenceTransformer(
        GTE_MODEL,
        revision=GTE_REVISION,
        trust_remote_code=True,
        device="cpu",
    )
    gte_load_ms = (time.perf_counter_ns() - load) / 1_000_000

    static = time.perf_counter_ns()
    gte_router = DenseDualViewRetriever(
        registry,
        gte,
        schema_weight=GTE_SCHEMA_WEIGHT,
        action_weight=GTE_ACTION_WEIGHT,
    )
    gte_static_ms = (time.perf_counter_ns() - static) / 1_000_000

    gte_rows: list[dict[str, Any]] = []
    errors = 0
    for case in rows:
        try:
            result = gte_router.route(str(case["query"]))
            gte_rows.append({**case, **result, "error": None})
        except Exception as exc:  # noqa: BLE001
            errors += 1
            gte_rows.append({
                **case,
                "predicted": None,
                "top_score": None,
                "top2_margin": None,
                "latency_ms": 0.0,
                "error": f"{type(exc).__name__}: {exc}",
            })

    del gte, gte_router
    gc.collect()

    bge = SentenceTransformer(
        BGE_MODEL,
        revision=BGE_REVISION,
        trust_remote_code=False,
        device="cpu",
    )
    bge_router = DenseDualViewRetriever(
        registry,
        bge,
        schema_weight=BGE_SCHEMA_WEIGHT,
        action_weight=BGE_ACTION_WEIGHT,
    )
    bge_rows = [bge_router.route(str(case["query"])) for case in rows]

    for row, bge_result in zip(gte_rows, bge_rows, strict=True):
        row["bge_predicted"] = bge_result["predicted"]

    exact = sum(r["predicted"] == r["expected"] for r in gte_rows)
    tool_acc = sum(
        r["predicted"] is not None
        and _tool(str(r["predicted"])) == _tool(str(r["expected"]))
        for r in gte_rows
    )
    bge_exact = sum(r["bge_predicted"] == r["expected"] for r in gte_rows)
    bge_tool = sum(
        _tool(str(r["bge_predicted"])) == _tool(str(r["expected"]))
        for r in gte_rows
    )
    disagreements = sum(r["predicted"] != r["bge_predicted"] for r in gte_rows)
    gte_better = sum(
        r["predicted"] == r["expected"] and r["bge_predicted"] != r["expected"]
        for r in gte_rows
    )
    bge_better = sum(
        r["bge_predicted"] == r["expected"] and r["predicted"] != r["expected"]
        for r in gte_rows
    )
    latencies = [float(r["latency_ms"]) for r in gte_rows]

    per_language = {}
    for lang in sorted({str(r["language"]) for r in gte_rows}):
        subset = [r for r in gte_rows if r["language"] == lang]
        per_language[lang] = {
            "cases": len(subset),
            "gte_exact": sum(r["predicted"] == r["expected"] for r in subset) / len(subset),
            "bge_exact": sum(r["bge_predicted"] == r["expected"] for r in subset) / len(subset),
        }

    per_tool = {}
    for tool in sorted({_tool(str(r["expected"])) for r in gte_rows}):
        subset = [r for r in gte_rows if _tool(str(r["expected"])) == tool]
        per_tool[tool] = {
            "cases": len(subset),
            "gte_exact": sum(r["predicted"] == r["expected"] for r in subset) / len(subset),
            "bge_exact": sum(r["bge_predicted"] == r["expected"] for r in subset) / len(subset),
        }

    metrics = {
        "gte_supported_exact_route_accuracy": exact / len(gte_rows),
        "gte_supported_tool_accuracy": tool_acc / len(gte_rows),
        "bge_supported_exact_route_accuracy": bge_exact / len(gte_rows),
        "bge_supported_tool_accuracy": bge_tool / len(gte_rows),
        "route_disagreements": disagreements,
        "gte_correct_bge_wrong": gte_better,
        "bge_correct_gte_wrong": bge_better,
        "gte_top_score": _dist(
            [
                float(r["top_score"])
                for r in gte_rows
                if r["top_score"] is not None
            ]
        ),
        "gte_top2_margin": _dist(
            [
                float(r["top2_margin"])
                for r in gte_rows
                if r["top2_margin"] is not None
            ]
        ),
        "gte_query_latency_ms": _dist(latencies),
        "gte_model_load_ms": gte_load_ms,
        "gte_static_route_encode_ms": gte_static_ms,
        "execution_errors": errors,
        "per_language": per_language,
        "per_tool": per_tool,
    }
    p95 = metrics["gte_query_latency_ms"]["p95"]
    gates = {
        "gte_exact_at_least_085": (
            metrics["gte_supported_exact_route_accuracy"] >= 0.85
        ),
        "gte_matches_or_exceeds_bge": (
            metrics["gte_supported_exact_route_accuracy"]
            >= metrics["bge_supported_exact_route_accuracy"]
        ),
        "execution_errors": errors == 0,
    }
    runtime = p95 is not None and float(p95) <= 250.0
    return {
        "experiment": "frozen-gte-multilingual-positive-route-selector-v1",
        "issue": 409,
        "surface": "V6G-development",
        "metrics": metrics,
        "quality_gates": gates,
        "runtime_gate": runtime,
        "quality_pass": all(gates.values()),
        "surface_pass": all(gates.values()) and runtime,
        "policy": {
            "confirmation_scored": False,
            "supported_only": True,
            "gte_is_sole_positive_selector": True,
            "bge_is_diagnostic_only": True,
            "schema_weight": GTE_SCHEMA_WEIGHT,
            "action_weight": GTE_ACTION_WEIGHT,
            "bge_fusion": False,
            "bge_consensus": False,
            "reranker": False,
            "abstention": False,
            "score_threshold": None,
            "margin_threshold": None,
            "rank2_fallback": False,
            "pseudo_route": False,
            "dev_selected_hyperparameters": False,
        },
        "rows": gte_rows,
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
