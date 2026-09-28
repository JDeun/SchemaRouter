"""DEV-only threshold-free BGE/GTE raw-route consensus diagnostic (#336)."""

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

from benchmark_decision_routing import load_corpus, reference_registry  # noqa: E402

from benchmarks.bge_m3_frozen_candidate import (  # noqa: E402
    _action_text,
    _cosine,
    _schema_text,
    _to_vectors,
)

GTE_MODEL = "Alibaba-NLP/gte-multilingual-base"
GTE_REVISION = "087a024525fd6e2fe749cb4679d218d8bcc95bdd"
GTE_SCHEMA_WEIGHT = 0.25
GTE_ACTION_WEIGHT = 0.75
MANIFEST_PATH = (
    _PROJECT_ROOT
    / "benchmarks"
    / "operation-routing-v4-bge-gte-consensus.json"
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


def _safe_rate(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def _catalog() -> list[dict[str, str]]:
    registry = reference_registry()
    rows: list[dict[str, str]] = []
    for tool in registry.tools():
        for endpoint in tool.endpoints:
            rows.append(
                {
                    "route_id": f"{tool.key}.{endpoint.name}",
                    "schema_text": _schema_text(tool, endpoint),
                    "action_text": _action_text(endpoint),
                }
            )
    return sorted(rows, key=lambda item: item["route_id"])


def _load_bge_reference(path: Path) -> dict[str, dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = data.get("rows")
    if not isinstance(rows, list) or len(rows) != 1800:
        raise ValueError("BGE reference report must contain exactly 1800 rows")

    indexed: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("BGE reference row must be an object")
        case_id = row.get("case_id")
        route = row.get("direct_top_route")
        if not isinstance(case_id, str) or not case_id:
            raise ValueError("BGE reference row has invalid case_id")
        if not isinstance(route, str) or not route:
            raise ValueError(f"BGE reference row {case_id!r} has invalid raw route")
        if case_id in indexed:
            raise ValueError(f"duplicate BGE reference case_id: {case_id}")
        indexed[case_id] = {
            "raw_route": route,
            "direct_latency_ms": row.get("direct_latency_ms"),
        }
    return indexed


def _rank(
    route_ids: list[str],
    scores: list[float],
) -> tuple[str, float, float, float]:
    ranked = sorted(
        zip(route_ids, scores, strict=True),
        key=lambda item: (-item[1], item[0]),
    )
    top_route, top_score = ranked[0]
    second_score = ranked[1][1]
    return top_route, top_score, second_score, top_score - second_score


def _metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    supported = [row for row in rows if row["expected"] is not None]
    near = [
        row
        for row in rows
        if row["category"] == "near_domain_unsupported_operation"
    ]
    ood = [row for row in rows if row["category"] == "out_of_domain"]
    unsupported = [row for row in rows if row["expected"] is None]

    def accepted(row: dict[str, Any]) -> bool:
        return bool(row["consensus"])

    supported_correct = sum(
        accepted(row) and row["bge_raw_route"] == row["expected"]
        for row in supported
    )
    wrong_supported = sum(
        accepted(row) and row["bge_raw_route"] != row["expected"]
        for row in supported
    )
    near_rejected = sum(not accepted(row) for row in near)
    ood_rejected = sum(not accepted(row) for row in ood)
    false_routes = sum(accepted(row) for row in unsupported)

    per_language: dict[str, Any] = {}
    for language in sorted({str(row["language"]) for row in rows}):
        subset = [row for row in rows if str(row["language"]) == language]
        lang_supported = [row for row in subset if row["expected"] is not None]
        lang_unsupported = [row for row in subset if row["expected"] is None]
        per_language[language] = {
            "cases": len(subset),
            "supported_exact_route_accuracy": _safe_rate(
                sum(
                    accepted(row) and row["bge_raw_route"] == row["expected"]
                    for row in lang_supported
                ),
                len(lang_supported),
            ),
            "unsupported_rejection": _safe_rate(
                sum(not accepted(row) for row in lang_unsupported),
                len(lang_unsupported),
            ),
            "false_routes": sum(accepted(row) for row in lang_unsupported),
        }

    per_route: dict[str, Any] = {}
    for route in sorted(
        {
            str(row["expected"])
            for row in supported
            if row["expected"] is not None
        }
    ):
        subset = [row for row in supported if row["expected"] == route]
        exact = sum(
            accepted(row) and row["bge_raw_route"] == route
            for row in subset
        )
        per_route[route] = {
            "cases": len(subset),
            "exact": exact,
            "exact_rate": _safe_rate(exact, len(subset)),
        }

    per_family: dict[str, Any] = {}
    names = sorted(
        {
            str(row["unsupported_family"])
            for row in unsupported
            if row.get("unsupported_family") is not None
        }
    )
    for name in names:
        subset = [
            row
            for row in unsupported
            if str(row.get("unsupported_family")) == name
        ]
        rejected = sum(not accepted(row) for row in subset)
        per_family[name] = {
            "cases": len(subset),
            "rejected": rejected,
            "rejection_rate": _safe_rate(rejected, len(subset)),
            "false_routes": len(subset) - rejected,
        }

    return {
        "supported_correct": supported_correct,
        "supported_exact_route_accuracy": _safe_rate(
            supported_correct, len(supported)
        ),
        "wrong_supported_accepted": wrong_supported,
        "near_domain_rejected": near_rejected,
        "near_domain_unsupported_rejection": _safe_rate(
            near_rejected, len(near)
        ),
        "ood_rejected": ood_rejected,
        "out_of_domain_rejection": _safe_rate(ood_rejected, len(ood)),
        "false_routes": false_routes,
        "false_route_rate": _safe_rate(false_routes, len(unsupported)),
        "per_language": per_language,
        "per_expected_route": per_route,
        "per_unsupported_family": per_family,
    }


def _quality_pass(metrics: dict[str, Any], *, errors: int, authority: int) -> bool:
    return (
        float(metrics["supported_exact_route_accuracy"]) >= 0.85
        and float(metrics["near_domain_unsupported_rejection"]) >= 0.97
        and float(metrics["out_of_domain_rejection"]) == 1.0
        and float(metrics["false_route_rate"]) <= 0.01
        and errors == 0
        and authority == 0
    )


def evaluate(
    cases: list[Any],
    *,
    reference_path: Path,
) -> dict[str, Any]:
    from sentence_transformers import SentenceTransformer

    catalog = _catalog()
    route_ids = [item["route_id"] for item in catalog]
    allowed_routes = set(route_ids)
    reference = _load_bge_reference(reference_path)
    if {case.id for case in cases} != set(reference):
        raise ValueError("canonical corpus case IDs do not match #259 reference")

    load_started = time.perf_counter_ns()
    model = SentenceTransformer(
        GTE_MODEL,
        revision=GTE_REVISION,
        trust_remote_code=True,
        device="cpu",
    )
    model_load_ms = (time.perf_counter_ns() - load_started) / 1_000_000

    static_started = time.perf_counter_ns()
    texts = [
        *(item["schema_text"] for item in catalog),
        *(item["action_text"] for item in catalog),
    ]
    static_vectors = _to_vectors(
        model.encode(
            texts,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
    )
    split = len(route_ids)
    schema_vectors = dict(
        zip(route_ids, static_vectors[:split], strict=True)
    )
    action_vectors = dict(
        zip(route_ids, static_vectors[split:], strict=True)
    )
    static_init_ms = (time.perf_counter_ns() - static_started) / 1_000_000

    gte_latencies: list[float] = []
    bge_reference_latencies: list[float] = []
    rows: list[dict[str, Any]] = []
    execution_errors = 0
    authority_violations = 0

    for case in cases:
        started = time.perf_counter_ns()
        try:
            query_vector = _to_vectors(
                model.encode(
                    [case.query],
                    normalize_embeddings=True,
                    convert_to_numpy=True,
                    show_progress_bar=False,
                )
            )[0]
            scores = [
                GTE_SCHEMA_WEIGHT * _cosine(query_vector, schema_vectors[route])
                + GTE_ACTION_WEIGHT * _cosine(query_vector, action_vectors[route])
                for route in route_ids
            ]
            gte_route, gte_score, gte_second, gte_margin = _rank(
                route_ids, scores
            )
            gte_ms = (time.perf_counter_ns() - started) / 1_000_000
            bge_route = str(reference[case.id]["raw_route"])
            consensus = gte_route == bge_route
            if consensus and bge_route not in allowed_routes:
                authority_violations += 1
            error = None
        except Exception as exc:  # noqa: BLE001 - preserve every diagnostic failure.
            execution_errors += 1
            gte_ms = (time.perf_counter_ns() - started) / 1_000_000
            gte_route = ""
            gte_score = gte_second = gte_margin = 0.0
            bge_route = str(reference[case.id]["raw_route"])
            consensus = False
            error = f"{type(exc).__name__}: {exc}"

        ref_latency = reference[case.id].get("direct_latency_ms")
        if isinstance(ref_latency, (int, float)):
            bge_reference_latencies.append(float(ref_latency))
        gte_latencies.append(gte_ms)
        rows.append(
            {
                "case_id": case.id,
                "category": case.category,
                "language": case.language,
                "unsupported_family": case.unsupported_family,
                "expected": case.expected,
                "bge_raw_route": bge_route,
                "gte_raw_route": gte_route,
                "gte_top_score": gte_score,
                "gte_second_score": gte_second,
                "gte_margin": gte_margin,
                "consensus": consensus,
                "gte_query_plus_scoring_latency_ms": gte_ms,
                "bge_reference_direct_latency_ms": ref_latency,
                "error": error,
            }
        )

    supported = [row for row in rows if row["expected"] is not None]
    bge_raw_correct = sum(
        row["bge_raw_route"] == row["expected"] for row in supported
    )
    gte_raw_correct = sum(
        row["gte_raw_route"] == row["expected"] for row in supported
    )
    agreement_count = sum(row["consensus"] for row in rows)
    metrics = _metrics(rows)

    return {
        "experiment": "bge-gte-threshold-free-route-consensus-v1",
        "summary": {
            "cases": len(rows),
            "bge_raw_supported_top1_accuracy": _safe_rate(
                bge_raw_correct, len(supported)
            ),
            "gte_raw_supported_top1_accuracy": _safe_rate(
                gte_raw_correct, len(supported)
            ),
            "bge_gte_route_agreement_rate": _safe_rate(
                agreement_count, len(rows)
            ),
            "quality_gate_pass": _quality_pass(
                metrics,
                errors=execution_errors,
                authority=authority_violations,
            ),
            "execution_errors": execution_errors,
            "authority_violations": authority_violations,
            "gte_model_load_ms": model_load_ms,
            "gte_static_init_ms": static_init_ms,
            "gte_query_plus_scoring_latency_ms": _distribution(gte_latencies),
            "bge_reference_direct_latency_ms": _distribution(
                bge_reference_latencies
            ),
            "runtime_policy": (
                "source-model latencies reported separately; no fabricated "
                "combined executable latency"
            ),
        },
        "consensus_metrics": metrics,
        "rows": rows,
        "policy": {
            "data_role": "tuning_eligible_development",
            "bge_authority_from_frozen_259_artifact": True,
            "gte_can_change_route": False,
            "score_threshold": False,
            "margin_threshold": False,
            "route_local_threshold": False,
            "rank2_fallback": False,
            "pseudo_route": False,
            "fresh_270_used": False,
            "fresh_287_used": False,
            "fresh_326_used": False,
            "calibration_or_blind_used": False,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--reference-report", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    registry = reference_registry()
    allowed_routes = {
        f"{tool.key}.{endpoint.name}"
        for tool in registry.tools()
        for endpoint in tool.endpoints
    }
    cases = load_corpus(args.corpus, allowed_routes=allowed_routes)
    result = evaluate(cases, reference_path=args.reference_report)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result["summary"], sort_keys=True))


if __name__ == "__main__":
    main()
