"""DEV-only typed contradiction-veto diagnostic over raw BGE-M3 top-1 routing."""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_SCRIPTS_DIR = Path(__file__).resolve().parent
for _path in (_PROJECT_ROOT, _SCRIPTS_DIR):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from benchmark_decision_routing import reference_registry  # noqa: E402

from benchmarks.bge_m3_frozen_candidate import (  # noqa: E402
    MODEL_NAME as RANKER_MODEL_NAME,
)
from benchmarks.bge_m3_frozen_candidate import (  # noqa: E402
    MODEL_REVISION as RANKER_MODEL_REVISION,
)
from benchmarks.bge_m3_frozen_candidate import (  # noqa: E402
    FrozenBgeM3DualViewBackend,
)
from benchmarks.multilingual_nli_typed import (  # noqa: E402
    MODEL_NAME as NLI_MODEL_NAME,
)
from benchmarks.multilingual_nli_typed import (  # noqa: E402
    MODEL_REVISION as NLI_MODEL_REVISION,
)
from benchmarks.multilingual_nli_typed import (  # noqa: E402
    score_pair_typed,
    score_pairs_typed,
    unload,
)

CONTRADICTION_THRESHOLDS = (0.50, 0.65, 0.80, 0.90, 0.95, 0.98, 0.99)
SCHEMA_WEIGHT = 0.55
ACTION_WEIGHT = 0.45


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


def _tool(route: str | None) -> str | None:
    if not isinstance(route, str) or "." not in route:
        return None
    return route.split(".", 1)[0]


def _load_ranker():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(
        RANKER_MODEL_NAME,
        revision=RANKER_MODEL_REVISION,
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


def _operation_surfaces(registry: Any) -> dict[str, str]:
    result: dict[str, str] = {}
    for tool in registry.tools():
        for endpoint in tool.endpoints:
            route_id = f"{tool.key}.{endpoint.name}"
            operation_name = endpoint.name.replace("_", " ").replace("-", " ")
            parts = [
                operation_name,
                *endpoint.operation_aliases,
                endpoint.description.strip(),
            ]
            result[route_id] = "\n".join(
                dict.fromkeys(part for part in parts if part)
            )
    return result


def _dominant_state(probabilities: dict[str, float]) -> str:
    return max(
        ("contradiction", "neutral", "entailment"),
        key=lambda name: (
            float(probabilities[name]),
            name,
        ),
    )


def _metrics_at_threshold(
    rows: list[dict[str, Any]],
    threshold: float,
) -> dict[str, Any]:
    predictions: list[str | None] = []
    for row in rows:
        veto = float(row["contradiction"]) >= threshold
        predictions.append(None if veto else str(row["raw_top_route"]))

    paired = list(zip(rows, predictions, strict=True))
    supported = [row for row in rows if row["expected"] is not None]
    near = [
        row
        for row in rows
        if row["category"] == "near_domain_unsupported_operation"
    ]
    ood = [row for row in rows if row["category"] == "out_of_domain"]
    unsupported = [row for row in rows if row["expected"] is None]

    supported_correct = sum(
        predicted == row["expected"]
        for row, predicted in paired
        if row["expected"] is not None
    )
    near_rejected = sum(
        predicted is None
        for row, predicted in paired
        if row["category"] == "near_domain_unsupported_operation"
    )
    ood_rejected = sum(
        predicted is None
        for row, predicted in paired
        if row["category"] == "out_of_domain"
    )
    false_routes = sum(
        predicted is not None
        for row, predicted in paired
        if row["expected"] is None
    )
    wrong_tool = sum(
        predicted is not None
        and row["expected"] is not None
        and _tool(predicted) != _tool(str(row["expected"]))
        for row, predicted in paired
        if row["expected"] is not None
    )
    wrong_endpoint = sum(
        predicted is not None
        and row["expected"] is not None
        and _tool(predicted) == _tool(str(row["expected"]))
        and predicted != row["expected"]
        for row, predicted in paired
        if row["expected"] is not None
    )
    vetoed_supported_correct_winners = sum(
        row["expected"] is not None
        and row["raw_top_route"] == row["expected"]
        and float(row["contradiction"]) >= threshold
        for row in rows
    )
    vetoed_unsupported = sum(
        row["expected"] is None
        and float(row["contradiction"]) >= threshold
        for row in rows
    )

    per_language: dict[str, Any] = {}
    for language in sorted({str(row["language"]) for row in rows}):
        subset = [
            (row, predicted)
            for row, predicted in paired
            if row["language"] == language
        ]
        lang_supported = [
            (row, predicted)
            for row, predicted in subset
            if row["expected"] is not None
        ]
        lang_unsupported = [
            (row, predicted)
            for row, predicted in subset
            if row["expected"] is None
        ]
        per_language[language] = {
            "supported_cases": len(lang_supported),
            "supported_exact_route_accuracy": (
                sum(
                    predicted == row["expected"]
                    for row, predicted in lang_supported
                )
                / len(lang_supported)
                if lang_supported
                else 0.0
            ),
            "unsupported_cases": len(lang_unsupported),
            "unsupported_rejection": (
                sum(predicted is None for _, predicted in lang_unsupported)
                / len(lang_unsupported)
                if lang_unsupported
                else 1.0
            ),
        }

    per_route: dict[str, Any] = {}
    for route in sorted({str(row["expected"]) for row in supported}):
        subset = [
            (row, predicted)
            for row, predicted in paired
            if row["expected"] == route
        ]
        correct = sum(predicted == route for _, predicted in subset)
        per_route[route] = {
            "cases": len(subset),
            "accepted_correct": correct,
            "supported_recall": correct / len(subset) if subset else 0.0,
        }

    family_rejection: dict[str, Any] = {}
    families = sorted(
        {
            str(row["unsupported_family"])
            for row in unsupported
            if row.get("unsupported_family") is not None
        }
    )
    for family in families:
        subset = [
            (row, predicted)
            for row, predicted in paired
            if row.get("unsupported_family") == family
        ]
        family_rejection[family] = {
            "cases": len(subset),
            "rejected": sum(predicted is None for _, predicted in subset),
            "rejection_rate": (
                sum(predicted is None for _, predicted in subset) / len(subset)
                if subset
                else 1.0
            ),
        }

    metrics = {
        "contradiction_threshold": threshold,
        "supported_correct": supported_correct,
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
        "wrong_tool": wrong_tool,
        "wrong_endpoint": wrong_endpoint,
        "vetoed_supported_correct_winners": vetoed_supported_correct_winners,
        "vetoed_unsupported": vetoed_unsupported,
        "per_language": per_language,
        "per_route": per_route,
        "unsupported_family_rejection": family_rejection,
    }
    metrics["quality_gate_pass"] = (
        float(metrics["supported_exact_route_accuracy"]) >= 0.85
        and float(metrics["near_domain_unsupported_rejection"]) >= 0.97
        and float(metrics["false_route_rate"]) <= 0.01
        and float(metrics["out_of_domain_rejection"]) == 1.0
    )
    return metrics


def evaluate(cases: list[dict[str, Any]]) -> dict[str, Any]:
    registry = reference_registry()
    surfaces = _operation_surfaces(registry)

    ranker_load_started = time.perf_counter_ns()
    ranker_model = _load_ranker()
    ranker_load_ms = (time.perf_counter_ns() - ranker_load_started) / 1_000_000

    ranker_init_started = time.perf_counter_ns()
    ranker = FrozenBgeM3DualViewBackend(registry, _embedder(ranker_model))
    ranker_init_ms = (time.perf_counter_ns() - ranker_init_started) / 1_000_000

    # Load NLI outside measured per-case latency without using any corpus evidence.
    nli_load_started = time.perf_counter_ns()
    score_pair_typed("warmup request", "warmup registered operation")
    nli_load_ms = (time.perf_counter_ns() - nli_load_started) / 1_000_000

    rows: list[dict[str, Any]] = []
    ranker_latencies: list[float] = []
    nli_latencies: list[float] = []
    sequential_latencies: list[float] = []

    for case in cases:
        query = str(case["query"])

        total_started = time.perf_counter_ns()
        rank_started = time.perf_counter_ns()
        ranked = ranker.score_routes(query, ranker.route_ids)
        rank_ms = (time.perf_counter_ns() - rank_started) / 1_000_000

        top_route = str(ranked["top_route"])
        nli_started = time.perf_counter_ns()
        probabilities = score_pair_typed(query, surfaces[top_route])
        nli_ms = (time.perf_counter_ns() - nli_started) / 1_000_000
        total_ms = (time.perf_counter_ns() - total_started) / 1_000_000

        ranker_latencies.append(rank_ms)
        nli_latencies.append(nli_ms)
        sequential_latencies.append(total_ms)
        rows.append(
            {
                "case_id": case.get("id"),
                "category": case.get("category"),
                "language": case.get("language"),
                "unsupported_family": case.get("unsupported_family"),
                "expected": case.get("expected"),
                "raw_top_route": top_route,
                "raw_top_score": float(ranked["top_score"]),
                "raw_top_margin": float(ranked["top_margin"]),
                "raw_correct": top_route == case.get("expected"),
                "contradiction": float(probabilities["contradiction"]),
                "neutral": float(probabilities["neutral"]),
                "entailment": float(probabilities["entailment"]),
                "dominant_nli_state": _dominant_state(probabilities),
                "ranker_latency_ms": rank_ms,
                "nli_latency_ms": nli_ms,
                "sequential_latency_ms": total_ms,
            }
        )

    supported = [row for row in rows if row["expected"] is not None]
    unsupported = [row for row in rows if row["expected"] is None]
    raw_supported_correct = sum(bool(row["raw_correct"]) for row in supported)

    probability_groups: dict[str, dict[str, Any]] = {}
    groups = {
        "supported_correct_winner": [
            row
            for row in supported
            if bool(row["raw_correct"])
        ],
        "supported_wrong_winner": [
            row
            for row in supported
            if not bool(row["raw_correct"])
        ],
        "near_domain_unsupported": [
            row
            for row in rows
            if row["category"] == "near_domain_unsupported_operation"
        ],
        "out_of_domain": [
            row
            for row in rows
            if row["category"] == "out_of_domain"
        ],
    }
    for name, group in groups.items():
        probability_groups[name] = {
            "cases": len(group),
            "contradiction": _distribution(
                [float(row["contradiction"]) for row in group]
            ),
            "neutral": _distribution(
                [float(row["neutral"]) for row in group]
            ),
            "entailment": _distribution(
                [float(row["entailment"]) for row in group]
            ),
            "dominant_states": {
                state: sum(row["dominant_nli_state"] == state for row in group)
                for state in ("contradiction", "neutral", "entailment")
            },
        }

    batch_sample = sorted(
        rows,
        key=lambda row: str(row["case_id"]),
    )[: min(128, len(rows))]
    batch_pairs = [
        (
            str(row["query"]),
            surfaces[str(row["raw_top_route"])],
        )
        for row in batch_sample
    ]
    batch_started = time.perf_counter_ns()
    batch_scores = score_pairs_typed(batch_pairs) if batch_pairs else []
    batch_latency_ms = (
        (time.perf_counter_ns() - batch_started) / 1_000_000
        if batch_pairs
        else 0.0
    )
    if len(batch_scores) != len(batch_pairs):
        raise RuntimeError("typed NLI batch score count mismatch")

    threshold_results = [
        _metrics_at_threshold(rows, threshold)
        for threshold in CONTRADICTION_THRESHOLDS
    ]
    passing = [
        item
        for item in threshold_results
        if bool(item["quality_gate_pass"])
    ]
    passing.sort(
        key=lambda item: (
            -float(item["supported_exact_route_accuracy"]),
            int(item["false_routes"]),
            -float(item["contradiction_threshold"]),
        )
    )

    latency = {
        "ranker_ms": _distribution(ranker_latencies),
        "nli_single_pair_ms": _distribution(nli_latencies),
        "sequential_ms": _distribution(sequential_latencies),
        "nli_batch_sample_cases": len(batch_pairs),
        "nli_batch_latency_ms": batch_latency_ms,
        "nli_batch_cases_per_second": (
            len(batch_pairs) / (batch_latency_ms / 1000.0)
            if batch_latency_ms > 0
            else None
        ),
    }
    p95 = latency["sequential_ms"]["p95"]
    candidate_worthy = [
        item
        for item in passing
        if p95 is not None and float(p95) <= 250.0
    ]

    return {
        "experiment": "typed-contradiction-only-nli-veto-v1",
        "models": {
            "ranker": {
                "name": RANKER_MODEL_NAME,
                "revision": RANKER_MODEL_REVISION,
                "schema_weight": SCHEMA_WEIGHT,
                "action_weight": ACTION_WEIGHT,
                "route_local_positive_gate_used": False,
            },
            "nli": {
                "name": NLI_MODEL_NAME,
                "revision": NLI_MODEL_REVISION,
                "semantics": {
                    "contradiction": "no_match_veto",
                    "neutral": "unknown_no_veto",
                    "entailment": "match_no_authority_upgrade",
                },
            },
        },
        "summary": {
            "cases": len(rows),
            "supported_cases": len(supported),
            "unsupported_cases": len(unsupported),
            "raw_supported_correct": raw_supported_correct,
            "raw_supported_top1_accuracy": (
                raw_supported_correct / len(supported) if supported else 0.0
            ),
            "ranker_model_load_ms": ranker_load_ms,
            "ranker_static_init_ms": ranker_init_ms,
            "nli_model_load_warmup_ms": nli_load_ms,
            "latency": latency,
            "typed_probability_groups": probability_groups,
            "candidate_worthy_threshold_count": len(candidate_worthy),
            "candidate_worthy_thresholds": candidate_worthy,
            "best_candidate": candidate_worthy[0] if candidate_worthy else None,
        },
        "threshold_results": threshold_results,
        "rows": rows,
        "policy": {
            "data_role": "tuning_eligible_development",
            "failed_fresh_confirmation_used_for_tuning": False,
            "calibration_or_blind_used": False,
            "nli_can_select_route": False,
            "nli_can_create_authority": False,
            "contradiction_veto_only": True,
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
                "raw_supported_top1_accuracy": result["summary"][
                    "raw_supported_top1_accuracy"
                ],
                "latency": result["summary"]["latency"],
                "candidate_worthy_threshold_count": result["summary"][
                    "candidate_worthy_threshold_count"
                ],
                "best_candidate": result["summary"]["best_candidate"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    unload()


if __name__ == "__main__":
    main()
