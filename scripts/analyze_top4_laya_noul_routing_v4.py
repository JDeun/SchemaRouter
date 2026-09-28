"""Manual-only DEV diagnostic: BGE top-4 recall + pinned Laya per-candidate noul routing."""

from __future__ import annotations

import argparse
import gc
import hashlib
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
    ACTION_WEIGHT,
    SCHEMA_WEIGHT,
    FrozenBgeM3DualViewBackend,
)
from benchmarks.bge_m3_frozen_candidate import MODEL_NAME as BGE_MODEL_NAME  # noqa: E402
from benchmarks.bge_m3_frozen_candidate import (  # noqa: E402
    MODEL_REVISION as BGE_MODEL_REVISION,
)

RECALL_WIDTH = 4
LAYA_PACKAGE_VERSION = "0.3.11"
LAYA_HUB_REPO = "convaiinnovations/laya"
LAYA_HUB_REVISION = "458d7563c5cab85ff9f7f6e06cf2dd166fb697e2"
BATCH_SIZE = 24
LATENCY_SAMPLE_PER_LANGUAGE = 12
ACCEPTANCE_THRESHOLDS = (0.50, 0.70, 0.80, 0.90, 0.95, 0.98, 0.99, 0.995)
SCOPE_RULE = (
    "This endpoint supports only the capability explicitly stated above. "
    "Unlisted operations are not supported by this endpoint."
)
NOUL_INSTRUCTION = (
    "Can this registered endpoint fully execute the user's requested operation exactly as "
    "requested? Judge operational capability, not topical similarity. Do not infer any "
    "operation or capability not explicitly stated in the endpoint contract."
)
TRUE_CRITERION = "This endpoint explicitly supports the complete requested operation."
FALSE_CRITERION = (
    "This endpoint cannot fully execute the request or requires an unlisted capability."
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
        "p05": _quantile(values, 0.05),
        "p25": _quantile(values, 0.25),
        "p50": _quantile(values, 0.50),
        "p75": _quantile(values, 0.75),
        "p95": _quantile(values, 0.95),
        "max": max(values) if values else None,
        "mean": statistics.fmean(values) if values else None,
    }


def _safe_rate(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


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


def _contract(tool: Any, endpoint: Any) -> str:
    route = f"{tool.key}.{endpoint.name}"
    aliases = ", ".join(sorted(set(endpoint.operation_aliases)))
    return "\n".join(
        [
            f"Registered endpoint: {route}",
            f"Tool scope: {tool.description.strip()}",
            f"Explicit endpoint capability: {endpoint.description.strip()}",
            f"Trusted operation aliases: {aliases}",
            f"Scope rule: {SCOPE_RULE}",
        ]
    )


def _route_rows(
    cases: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    registry = reference_registry()
    contracts = {
        f"{tool.key}.{endpoint.name}": _contract(tool, endpoint)
        for tool in registry.tools()
        for endpoint in tool.endpoints
    }

    started = time.perf_counter_ns()
    model = _load_bge_model()
    model_load_ms = (time.perf_counter_ns() - started) / 1_000_000

    started = time.perf_counter_ns()
    backend = FrozenBgeM3DualViewBackend(registry, _bge_embedder(model))
    backend_init_ms = (time.perf_counter_ns() - started) / 1_000_000

    rows: list[dict[str, Any]] = []
    latencies: list[float] = []
    allowed = set(backend.route_ids)
    for case in cases:
        started = time.perf_counter_ns()
        scored = backend.score_routes(str(case["query"]), backend.route_ids)
        elapsed_ms = (time.perf_counter_ns() - started) / 1_000_000
        latencies.append(elapsed_ms)
        ranked = [
            str(item["route_id"])
            for item in scored["ranked_routes"][:RECALL_WIDTH]
        ]
        if len(ranked) != RECALL_WIDTH or len(set(ranked)) != RECALL_WIDTH:
            raise RuntimeError("BGE returned an invalid top-k candidate set")
        if any(route not in allowed for route in ranked):
            raise RuntimeError("BGE returned an unregistered top-k route")
        expected = case.get("expected")
        rows.append(
            {
                "case_id": str(case["id"]),
                "query": str(case["query"]),
                "category": case.get("category"),
                "language": case.get("language"),
                "unsupported_family": case.get("unsupported_family"),
                "expected": expected,
                "topk_routes": ranked,
                "topk_contracts": [contracts[route] for route in ranked],
                "supported_recall_hit": expected is not None and expected in ranked,
                "bge_latency_ms": elapsed_ms,
            }
        )

    del backend
    del model
    gc.collect()
    return rows, {
        "model_load_ms": model_load_ms,
        "backend_static_init_ms": backend_init_ms,
        "query_latency_ms": _distribution(latencies),
    }


def _questions(row: dict[str, Any]) -> dict[str, Any]:
    return {
        f"candidate_{index}": {
            "type": "noul",
            "instructions": (
                f"{NOUL_INSTRUCTION}\nEndpoint contract:\n{contract}"
            ),
            "criteria": {
                "true": TRUE_CRITERION,
                "false": FALSE_CRITERION,
            },
        }
        for index, contract in enumerate(row["topk_contracts"])
    }


def _load_router(snapshot_dir: Path):
    from laya import Router

    started = time.perf_counter_ns()
    router = Router(
        models={
            "english": str(snapshot_dir),
            "multilingual": (str(snapshot_dir), "multilingual"),
        },
        device="cpu",
        preload=False,
        max_loaded=2,
    )
    router.preload(["english", "multilingual"])
    load_ms = (time.perf_counter_ns() - started) / 1_000_000
    return router, load_ms


def _latency_sample_indexes(rows: list[dict[str, Any]]) -> list[int]:
    chosen: list[int] = []
    for language in sorted({str(row["language"]) for row in rows}):
        values = [
            (hashlib.sha256(str(row["case_id"]).encode()).hexdigest(), index)
            for index, row in enumerate(rows)
            if str(row["language"]) == language
        ]
        values.sort()
        chosen.extend(index for _, index in values[:LATENCY_SAMPLE_PER_LANGUAGE])
    return sorted(chosen)


def _parse_result(row: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    scored: list[tuple[str, float]] = []
    for index, route in enumerate(row["topk_routes"]):
        answer = result["answers"][f"candidate_{index}"]
        value = float(answer["noul"])
        if not math.isfinite(value) or not 0.0 <= value <= 1.0:
            raise RuntimeError("Laya returned an invalid noul probability")
        scored.append((str(route), value))
    # Highest native capability probability wins. Exact ties are lexical by route ID,
    # never BGE order.
    scored.sort(key=lambda item: (-item[1], item[0]))
    selected_route, max_probability = scored[0]
    return {
        "selected_route": selected_route,
        "max_probability": max_probability,
        "candidate_probabilities": {
            route: value for route, value in sorted(scored)
        },
    }


def _score_laya(
    rows: list[dict[str, Any]],
    snapshot_dir: Path,
) -> dict[str, Any]:
    router, load_ms = _load_router(snapshot_dir)
    requests = [
        {
            "state": str(row["query"]),
            "questions": _questions(row),
        }
        for row in rows
    ]

    started = time.perf_counter_ns()
    results = router.predict_batch(requests, batch_size=BATCH_SIZE)
    batch_total_ms = (time.perf_counter_ns() - started) / 1_000_000
    if len(results) != len(rows):
        raise RuntimeError("Laya returned the wrong batch result count")

    selections = [
        _parse_result(row, result)
        for row, result in zip(rows, results, strict=True)
    ]

    routed_models: dict[str, int] = {}
    for result in results:
        routing = result.get("routing")
        if isinstance(routing, dict) and routing.get("model") is not None:
            key = str(routing["model"])
            routed_models[key] = routed_models.get(key, 0) + 1

    single_latencies: list[float] = []
    combined_latencies: list[float] = []
    for index in _latency_sample_indexes(rows):
        started = time.perf_counter_ns()
        result = router.predict(
            str(rows[index]["query"]),
            _questions(rows[index]),
        )
        latency_ms = (time.perf_counter_ns() - started) / 1_000_000
        # Validate the measured request path too.
        _parse_result(rows[index], result)
        single_latencies.append(latency_ms)
        combined_latencies.append(
            float(rows[index]["bge_latency_ms"]) + latency_ms
        )

    return {
        "selections": selections,
        "model_load_ms": load_ms,
        "batch_size": BATCH_SIZE,
        "batched_total_ms": batch_total_ms,
        "batched_amortized_ms_per_case": batch_total_ms / len(rows),
        "routed_model_counts": routed_models,
        "single_request_sample_cases": len(single_latencies),
        "single_request_latency_ms": _distribution(single_latencies),
        "combined_single_request_latency_ms": _distribution(combined_latencies),
    }


def _evaluate_threshold(
    rows: list[dict[str, Any]],
    selections: list[dict[str, Any]],
    threshold: float,
) -> dict[str, Any]:
    accepted = [
        float(selection["max_probability"]) >= threshold
        for selection in selections
    ]
    supported = [i for i, row in enumerate(rows) if row["expected"] is not None]
    near = [
        i for i, row in enumerate(rows)
        if row["category"] == "near_domain_unsupported_operation"
    ]
    ood = [i for i, row in enumerate(rows) if row["category"] == "out_of_domain"]
    unsupported = [i for i, row in enumerate(rows) if row["expected"] is None]

    supported_correct = sum(
        accepted[i] and selections[i]["selected_route"] == rows[i]["expected"]
        for i in supported
    )
    wrong_supported_accepted = sum(
        accepted[i] and selections[i]["selected_route"] != rows[i]["expected"]
        for i in supported
    )
    near_rejected = sum(not accepted[i] for i in near)
    ood_rejected = sum(not accepted[i] for i in ood)
    false_routes = sum(accepted[i] for i in unsupported)

    exact = _safe_rate(supported_correct, len(supported))
    near_rejection = _safe_rate(near_rejected, len(near))
    ood_rejection = _safe_rate(ood_rejected, len(ood))
    false_rate = _safe_rate(false_routes, len(unsupported))

    per_language: dict[str, Any] = {}
    for language in sorted({str(row["language"]) for row in rows}):
        idx = [i for i, row in enumerate(rows) if str(row["language"]) == language]
        sup = [i for i in idx if rows[i]["expected"] is not None]
        unsup = [i for i in idx if rows[i]["expected"] is None]
        per_language[language] = {
            "supported_exact_route_accuracy": _safe_rate(
                sum(
                    accepted[i]
                    and selections[i]["selected_route"] == rows[i]["expected"]
                    for i in sup
                ),
                len(sup),
            ),
            "unsupported_rejection": _safe_rate(
                sum(not accepted[i] for i in unsup),
                len(unsup),
            ),
            "false_routes": sum(accepted[i] for i in unsup),
        }

    return {
        "rule_id": f"top4-laya-noul-p{threshold:.3f}",
        "threshold": threshold,
        "supported_exact_route_accuracy": exact,
        "supported_correct": supported_correct,
        "wrong_supported_accepted": wrong_supported_accepted,
        "near_domain_unsupported_rejection": near_rejection,
        "out_of_domain_rejection": ood_rejection,
        "false_routes": false_routes,
        "false_route_rate": false_rate,
        "per_language": per_language,
        "quality_gate_pass": (
            exact >= 0.85
            and near_rejection >= 0.97
            and ood_rejection == 1.0
            and false_rate <= 0.01
        ),
    }


def evaluate(cases: list[dict[str, Any]], snapshot_dir: Path) -> dict[str, Any]:
    rows, bge_runtime = _route_rows(cases)
    laya = _score_laya(rows, snapshot_dir)
    selections = list(laya.pop("selections"))
    rules = [
        _evaluate_threshold(rows, selections, threshold)
        for threshold in ACCEPTANCE_THRESHOLDS
    ]
    worthy = [rule for rule in rules if rule["quality_gate_pass"]]
    worthy.sort(
        key=lambda rule: (
            -float(rule["supported_exact_route_accuracy"]),
            int(rule["false_routes"]),
            float(rule["threshold"]),
        )
    )
    combined_p95 = laya["combined_single_request_latency_ms"]["p95"]
    runtime_pass = combined_p95 is not None and float(combined_p95) <= 250.0

    supported = [row for row in rows if row["expected"] is not None]
    recall_hits = sum(bool(row["supported_recall_hit"]) for row in supported)
    raw_selector_correct = sum(
        selection["selected_route"] == row["expected"]
        for row, selection in zip(rows, selections, strict=True)
        if row["expected"] is not None
    )

    return {
        "experiment": "top4-bge-recall-laya-noul-routing-v1",
        "models": {
            "recall": {
                "name": BGE_MODEL_NAME,
                "revision": BGE_MODEL_REVISION,
                "schema_weight": SCHEMA_WEIGHT,
                "action_weight": ACTION_WEIGHT,
                "width": RECALL_WIDTH,
            },
            "selector": {
                "package": f"laya=={LAYA_PACKAGE_VERSION}",
                "hub_repo": LAYA_HUB_REPO,
                "hub_revision": LAYA_HUB_REVISION,
                "primitive": "noul",
            },
        },
        "summary": {
            "cases": len(rows),
            "supported_cases": len(supported),
            "bge_supported_recall_at_4": _safe_rate(recall_hits, len(supported)),
            "raw_laya_selector_supported_accuracy": _safe_rate(
                raw_selector_correct,
                len(supported),
            ),
            "fixed_rule_count": len(rules),
            "quality_worthy_rule_count": len(worthy),
            "best_quality_rule": worthy[0] if worthy else None,
            "runtime_target_pass": runtime_pass,
            "promotable_rule_count": len(worthy) if runtime_pass else 0,
            "authority_violations": 0,
            "execution_errors": 0,
        },
        "bge_runtime": bge_runtime,
        "laya_runtime": laya,
        "quality_worthy_rules": worthy,
        "rule_results": rules,
        "rows": [
            {
                "case_id": row["case_id"],
                "category": row["category"],
                "language": row["language"],
                "unsupported_family": row["unsupported_family"],
                "expected": row["expected"],
                "topk_routes": row["topk_routes"],
                "supported_recall_hit": row["supported_recall_hit"],
                "selected_route": selection["selected_route"],
                "max_probability": selection["max_probability"],
                "candidate_probabilities": selection["candidate_probabilities"],
                "bge_latency_ms": row["bge_latency_ms"],
            }
            for row, selection in zip(rows, selections, strict=True)
        ],
        "policy": {
            "data_role": "tuning_eligible_development",
            "failed_270_fresh_used": False,
            "failed_287_fresh_used": False,
            "calibration_or_blind_used": False,
            "bge_role": "candidate_recall_only",
            "laya_role": "sole_selector_within_finite_top4",
            "provider_can_create_route": False,
            "pseudo_route": False,
            "rank2_fallback": False,
            "exact_tie_break": "lexicographic_route_id",
            "prompt_variants_tested": 1,
            "checkpoint_snapshot_pinned": True,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--snapshot-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    cases = json.loads(args.corpus.read_text(encoding="utf-8"))
    if not isinstance(cases, list) or any(not isinstance(item, dict) for item in cases):
        raise ValueError("corpus must be a JSON object list")
    result = evaluate(cases, args.snapshot_dir)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "bge_supported_recall_at_4": result["summary"][
                    "bge_supported_recall_at_4"
                ],
                "raw_laya_selector_supported_accuracy": result["summary"][
                    "raw_laya_selector_supported_accuracy"
                ],
                "quality_worthy_rule_count": result["summary"][
                    "quality_worthy_rule_count"
                ],
                "best_quality_rule": result["summary"]["best_quality_rule"],
                "runtime_target_pass": result["summary"]["runtime_target_pass"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
