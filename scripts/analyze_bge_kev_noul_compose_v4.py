"""Offline composition of frozen BGE route authority with frozen Kev global noul."""

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

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_SCRIPTS_DIR = Path(__file__).resolve().parent
for _path in (_PROJECT_ROOT, _SCRIPTS_DIR):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from benchmark_decision_routing import load_corpus, reference_registry  # noqa: E402

from benchmarks.bge_m3_frozen_candidate import (  # noqa: E402
    ACTION_WEIGHT,
    SCHEMA_WEIGHT,
    FrozenBgeM3DualViewBackend,
)
from benchmarks.bge_m3_frozen_candidate import (  # noqa: E402
    MODEL_NAME as BGE_MODEL_NAME,
)
from benchmarks.bge_m3_frozen_candidate import (  # noqa: E402
    MODEL_REVISION as BGE_MODEL_REVISION,
)

THRESHOLDS = (0.50, 0.70, 0.80, 0.90, 0.95, 0.98, 0.99, 0.995)
EXPECTED_KEV_EXPERIMENT = "kev-0.8b-choice-noul-v1"


def _safe_rate(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


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
        "p05": _quantile(values, 0.05),
        "p25": _quantile(values, 0.25),
        "p50": _quantile(values, 0.50),
        "p75": _quantile(values, 0.75),
        "p95": _quantile(values, 0.95),
        "max": max(values) if values else None,
        "mean": statistics.fmean(values) if values else None,
    }


def _load_bge_model():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(
        BGE_MODEL_NAME,
        revision=BGE_MODEL_REVISION,
        trust_remote_code=False,
    )


def _bge_embedder(model: Any):
    def embed(texts: list[str]) -> list[list[float]]:
        vectors = model.encode(
            texts,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return vectors.tolist()

    return embed


def _load_kev_rows(path: Path) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    analysis = json.loads(path.read_text(encoding="utf-8"))
    if analysis.get("experiment") != EXPECTED_KEV_EXPERIMENT:
        raise ValueError(
            "Kev analysis experiment mismatch: "
            f"{analysis.get('experiment')!r}"
        )

    rows = analysis.get("rows")
    if not isinstance(rows, list) or len(rows) != 1800:
        raise ValueError("Kev analysis must contain exactly 1800 row records")

    by_id: dict[str, dict[str, Any]] = {}
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ValueError(f"Kev row {index} is not an object")
        case_id = str(row.get("case_id", "")).strip()
        if not case_id or case_id in by_id:
            raise ValueError(f"Kev row {index} has missing/duplicate case_id")

        if row.get("error") is not None:
            raise ValueError(
                f"Kev row {case_id!r} contains an execution error"
            )

        probability = row.get("supported_probability")
        latency = row.get("latency_ms")
        if not isinstance(probability, (int, float)):
            raise ValueError(
                f"Kev row {case_id!r} is missing supported_probability"
            )
        if not math.isfinite(float(probability)) or not 0.0 <= float(probability) <= 1.0:
            raise ValueError(
                f"Kev row {case_id!r} has invalid supported_probability"
            )
        if not isinstance(latency, (int, float)):
            raise ValueError(f"Kev row {case_id!r} is missing latency_ms")
        if not math.isfinite(float(latency)) or float(latency) < 0.0:
            raise ValueError(f"Kev row {case_id!r} has invalid latency_ms")

        by_id[case_id] = row

    return by_id, analysis


def _score_bge(
    corpus_path: Path,
    kev_rows: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    registry = reference_registry()
    allowed = {
        f"{tool.key}.{endpoint.name}"
        for tool in registry.tools()
        for endpoint in tool.endpoints
    }
    cases = load_corpus(corpus_path, allowed_routes=allowed)
    if len(cases) != 1800:
        raise ValueError("canonical corpus must contain exactly 1800 cases")
    if {case.id for case in cases} != set(kev_rows):
        raise ValueError("Kev artifact case IDs do not exactly match canonical corpus")

    load_started = time.perf_counter_ns()
    model = _load_bge_model()
    model_load_ms = (time.perf_counter_ns() - load_started) / 1_000_000

    init_started = time.perf_counter_ns()
    backend = FrozenBgeM3DualViewBackend(registry, _bge_embedder(model))
    backend_init_ms = (time.perf_counter_ns() - init_started) / 1_000_000

    rows: list[dict[str, Any]] = []
    bge_latencies: list[float] = []
    combined_latencies: list[float] = []
    authority_violations = 0

    for case in cases:
        started = time.perf_counter_ns()
        scored = backend.score_routes(case.query, backend.route_ids)
        bge_latency_ms = (time.perf_counter_ns() - started) / 1_000_000
        raw_top_route = str(scored["top_route"])
        if raw_top_route not in allowed:
            authority_violations += 1

        kev = kev_rows[case.id]
        supported_probability = float(kev["supported_probability"])
        kev_latency_ms = float(kev["latency_ms"])
        bge_latencies.append(bge_latency_ms)
        combined_latencies.append(bge_latency_ms + kev_latency_ms)

        rows.append(
            {
                "case_id": case.id,
                "category": case.category,
                "language": case.language,
                "unsupported_family": case.unsupported_family,
                "expected": case.expected,
                "raw_top_route": raw_top_route,
                "raw_correct": (
                    case.expected is not None
                    and raw_top_route == case.expected
                ),
                "supported_probability": supported_probability,
                "bge_latency_ms": bge_latency_ms,
                "kev_latency_ms": kev_latency_ms,
                "combined_latency_ms": bge_latency_ms + kev_latency_ms,
            }
        )

    del backend
    del model
    gc.collect()

    return rows, {
        "model_load_ms": model_load_ms,
        "backend_static_init_ms": backend_init_ms,
        "bge_query_latency_ms": _distribution(bge_latencies),
        "combined_single_request_latency_ms": _distribution(combined_latencies),
        "authority_violations": authority_violations,
    }


def _accepted(row: dict[str, Any], threshold: float) -> bool:
    return float(row["supported_probability"]) >= threshold


def _evaluate_rule(
    rows: list[dict[str, Any]],
    threshold: float,
) -> dict[str, Any]:
    supported = [row for row in rows if row["expected"] is not None]
    near = [
        row
        for row in rows
        if row["category"] == "near_domain_unsupported_operation"
    ]
    ood = [row for row in rows if row["category"] == "out_of_domain"]
    unsupported = [row for row in rows if row["expected"] is None]

    supported_correct = sum(
        _accepted(row, threshold) and bool(row["raw_correct"])
        for row in supported
    )
    wrong_supported_accepted = sum(
        _accepted(row, threshold) and not bool(row["raw_correct"])
        for row in supported
    )
    near_rejected = sum(not _accepted(row, threshold) for row in near)
    ood_rejected = sum(not _accepted(row, threshold) for row in ood)
    false_routes = sum(_accepted(row, threshold) for row in unsupported)

    supported_exact = _safe_rate(supported_correct, len(supported))
    near_rejection = _safe_rate(near_rejected, len(near))
    ood_rejection = _safe_rate(ood_rejected, len(ood))
    false_rate = _safe_rate(false_routes, len(unsupported))

    per_language: dict[str, Any] = {}
    for language in sorted({str(row["language"]) for row in rows}):
        subset = [row for row in rows if str(row["language"]) == language]
        lang_supported = [row for row in subset if row["expected"] is not None]
        lang_unsupported = [row for row in subset if row["expected"] is None]
        per_language[language] = {
            "supported_exact_route_accuracy": _safe_rate(
                sum(
                    _accepted(row, threshold) and bool(row["raw_correct"])
                    for row in lang_supported
                ),
                len(lang_supported),
            ),
            "unsupported_rejection": _safe_rate(
                sum(not _accepted(row, threshold) for row in lang_unsupported),
                len(lang_unsupported),
            ),
            "false_routes": sum(
                _accepted(row, threshold) for row in lang_unsupported
            ),
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
            _accepted(row, threshold) and bool(row["raw_correct"])
            for row in subset
        )
        per_route[route] = {
            "cases": len(subset),
            "exact": exact,
            "exact_rate": _safe_rate(exact, len(subset)),
        }

    per_family: dict[str, Any] = {}
    families = sorted(
        {
            str(row["unsupported_family"])
            for row in rows
            if row["unsupported_family"] is not None
        }
    )
    for family in families:
        subset = [
            row
            for row in rows
            if str(row["unsupported_family"]) == family
        ]
        rejected = sum(not _accepted(row, threshold) for row in subset)
        per_family[family] = {
            "cases": len(subset),
            "rejected": rejected,
            "rejection_rate": _safe_rate(rejected, len(subset)),
        }

    quality_pass = (
        supported_exact >= 0.85
        and near_rejection >= 0.97
        and ood_rejection == 1.0
        and false_rate <= 0.01
    )
    return {
        "rule_id": f"bge-kev-noul-p{threshold:.3f}",
        "threshold": threshold,
        "supported_correct": supported_correct,
        "supported_exact_route_accuracy": supported_exact,
        "wrong_supported_accepted": wrong_supported_accepted,
        "near_domain_rejected": near_rejected,
        "near_domain_unsupported_rejection": near_rejection,
        "ood_rejected": ood_rejected,
        "out_of_domain_rejection": ood_rejection,
        "false_routes": false_routes,
        "false_route_rate": false_rate,
        "per_language": per_language,
        "per_expected_route": per_route,
        "unsupported_family_rejection": per_family,
        "quality_gate_pass": quality_pass,
    }


def _probability_geometry(rows: list[dict[str, Any]]) -> dict[str, Any]:
    groups = {
        "supported_correct_bge_winner": [
            row
            for row in rows
            if row["expected"] is not None and row["raw_correct"]
        ],
        "supported_wrong_bge_winner": [
            row
            for row in rows
            if row["expected"] is not None and not row["raw_correct"]
        ],
        "near_domain_unsupported": [
            row
            for row in rows
            if row["category"] == "near_domain_unsupported_operation"
        ],
        "out_of_domain": [
            row for row in rows if row["category"] == "out_of_domain"
        ],
    }
    return {
        name: _distribution(
            [float(row["supported_probability"]) for row in group]
        )
        for name, group in groups.items()
    }


def evaluate(corpus_path: Path, kev_analysis_path: Path) -> dict[str, Any]:
    kev_rows, kev_analysis = _load_kev_rows(kev_analysis_path)

    summary = kev_analysis.get("summary", {})
    if summary.get("execution_errors") != 0:
        raise ValueError("Kev source analysis contains execution errors")
    if summary.get("authority_violations") != 0:
        raise ValueError("Kev source analysis contains authority violations")

    rows, runtime = _score_bge(corpus_path, kev_rows)
    rules = [_evaluate_rule(rows, threshold) for threshold in THRESHOLDS]
    passing = [
        rule
        for rule in rules
        if rule["quality_gate_pass"] and runtime["authority_violations"] == 0
    ]
    passing.sort(
        key=lambda rule: (
            -float(rule["supported_exact_route_accuracy"]),
            int(rule["false_routes"]),
            -float(rule["near_domain_unsupported_rejection"]),
            float(rule["threshold"]),
        )
    )

    supported = [row for row in rows if row["expected"] is not None]
    raw_correct = sum(bool(row["raw_correct"]) for row in supported)
    combined_p95 = runtime["combined_single_request_latency_ms"]["p95"]
    runtime_pass = (
        combined_p95 is not None and float(combined_p95) <= 250.0
    )

    return {
        "experiment": "bge-authority-kev-global-noul-compose-v1",
        "source_kev_experiment": EXPECTED_KEV_EXPERIMENT,
        "summary": {
            "cases": len(rows),
            "raw_bge_supported_top1_accuracy": _safe_rate(
                raw_correct,
                len(supported),
            ),
            "fixed_rule_count": len(rules),
            "quality_worthy_rule_count": len(passing),
            "best_quality_rule": passing[0] if passing else None,
            "runtime_target_pass": runtime_pass,
            "promotable_rule_count": len(passing) if runtime_pass else 0,
            "authority_violations": runtime["authority_violations"],
            "execution_errors": 0,
            "probability_geometry": _probability_geometry(rows),
        },
        "models": {
            "ranker": {
                "name": BGE_MODEL_NAME,
                "revision": BGE_MODEL_REVISION,
                "schema_weight": SCHEMA_WEIGHT,
                "action_weight": ACTION_WEIGHT,
            },
            "kev_evidence": {
                "new_inference": False,
                "field": "supported_probability",
                "source_runtime": kev_analysis.get("runtime"),
            },
        },
        "runtime": runtime,
        "quality_worthy_rules": passing,
        "rule_results": rules,
        "rows": rows,
        "policy": {
            "data_role": "tuning_eligible_development",
            "failed_270_fresh_used": False,
            "failed_287_fresh_used": False,
            "calibration_or_blind_used": False,
            "kev_choice_used": False,
            "kev_choice_confidence_used": False,
            "kev_new_inference": False,
            "rank2_fallback": False,
            "route_switching": False,
            "prompt_variants_tested": 1,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--kev-analysis", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    result = evaluate(args.corpus, args.kev_analysis)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "raw_bge_supported_top1_accuracy": result["summary"][
                    "raw_bge_supported_top1_accuracy"
                ],
                "quality_worthy_rule_count": result["summary"][
                    "quality_worthy_rule_count"
                ],
                "best_quality_rule": result["summary"]["best_quality_rule"],
                "runtime_target_pass": result["summary"][
                    "runtime_target_pass"
                ],
                "combined_latency_ms": result["runtime"][
                    "combined_single_request_latency_ms"
                ],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
