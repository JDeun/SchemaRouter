"""DEV-only AnyJev L0 content-free noul veto over immutable BGE-M3 winner."""

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
from benchmarks.bge_m3_frozen_candidate import (  # noqa: E402
    MODEL_NAME as BGE_MODEL_NAME,
)
from benchmarks.bge_m3_frozen_candidate import (  # noqa: E402
    MODEL_REVISION as BGE_MODEL_REVISION,
)

ANYJEV_SOURCE_REVISION = "45add301a7aa60ed3420c83d15c061e84e5bce61"
BASE_MODEL = "Qwen/Qwen3-0.6B"
BASE_MODEL_REVISION = "c1899de289a04d12100db370d81485cdf75e47ca"
TRANSFORMERS_VERSION = "4.57.6"
BATCH_SIZE = 8
LATENCY_SAMPLE_PER_LANGUAGE = 12
ACCEPTANCE_THRESHOLDS = (0.50, 0.70, 0.80, 0.90, 0.95, 0.98, 0.99, 0.995)
QUESTION_TEXT = (
    "Can this registered endpoint fully execute the user's requested operation exactly "
    "as requested? Judge operational capability, not topical similarity. Answer Yes "
    "only when every requested operation is explicitly supported by the endpoint "
    "contract. Do not infer any unlisted capability."
)
SCOPE_RULE = (
    "This endpoint supports only the capability explicitly stated above. "
    "Unlisted operations are not supported by this endpoint."
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


def _capability_contract(tool: Any, endpoint: Any) -> str:
    aliases = ", ".join(sorted(set(endpoint.operation_aliases)))
    return "\n".join(
        [
            f"Registered endpoint: {tool.key}.{endpoint.name}",
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
        f"{tool.key}.{endpoint.name}": _capability_contract(tool, endpoint)
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
        route = str(scored["top_route"])
        expected = case.get("expected")
        rows.append(
            {
                "case_id": str(case["id"]),
                "query": str(case["query"]),
                "category": case.get("category"),
                "language": case.get("language"),
                "unsupported_family": case.get("unsupported_family"),
                "expected": expected,
                "raw_top_route": route,
                "raw_correct": expected is not None and route == expected,
                "endpoint_contract": contracts[route],
                "bge_latency_ms": elapsed_ms,
                "authority_violation": route not in allowed,
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


def build_state(row: dict[str, Any]) -> dict[str, str]:
    return {
        "user_request": str(row["query"]),
        "endpoint_contract": str(row["endpoint_contract"]),
    }


def _latency_sample_indexes(rows: list[dict[str, Any]]) -> list[int]:
    selected: list[int] = []
    for language in sorted({str(row["language"]) for row in rows}):
        values = [
            (hashlib.sha256(str(row["case_id"]).encode()).hexdigest(), index)
            for index, row in enumerate(rows)
            if str(row["language"]) == language
        ]
        values.sort()
        selected.extend(index for _, index in values[:LATENCY_SAMPLE_PER_LANGUAGE])
    return sorted(selected)


def _score_anyjev(rows: list[dict[str, Any]]) -> dict[str, Any]:
    from anyjev.backends.hf import HFBackend
    from anyjev.decider import Decider
    from anyjev.question import Question

    load_started = time.perf_counter_ns()
    backend = HFBackend(
        BASE_MODEL,
        device="cpu",
        dtype="float32",
        batch_size=BATCH_SIZE,
        trust_remote_code=False,
        revision=BASE_MODEL_REVISION,
    )
    decider = Decider(
        backend,
        level="L0",
        prior="content_free",
        prior_strength=1.0,
        adaptive_shifts=False,
        shared_prefix="auto",
    )
    load_ms = (time.perf_counter_ns() - load_started) / 1_000_000

    question = Question.noul(QUESTION_TEXT, name="supported")
    states = [build_state(row) for row in rows]

    started = time.perf_counter_ns()
    decisions = decider.decide_batch(states, question, level="L0", require="L0")
    batch_total_ms = (time.perf_counter_ns() - started) / 1_000_000

    probabilities: list[float] = []
    levels: list[str] = []
    diagnostics: list[dict[str, Any]] = []
    for decision in decisions:
        value = float(decision.p_true)
        if not math.isfinite(value) or not 0.0 <= value <= 1.0:
            raise RuntimeError("AnyJev returned an invalid P(true)")
        if decision.level != "L0":
            raise RuntimeError(f"AnyJev returned unexpected level {decision.level!r}")
        probabilities.append(value)
        levels.append(decision.level)
        diagnostics.append(dict(decision.diagnostics))

    single_latencies: list[float] = []
    combined_latencies: list[float] = []
    for index in _latency_sample_indexes(rows):
        started = time.perf_counter_ns()
        decision_set = decider.decide(
            states[index],
            [question],
            level="L0",
            require="L0",
        )
        elapsed_ms = (time.perf_counter_ns() - started) / 1_000_000
        value = float(decision_set["supported"].p_true)
        if not 0.0 <= value <= 1.0:
            raise RuntimeError("AnyJev latency sample returned invalid P(true)")
        single_latencies.append(elapsed_ms)
        combined_latencies.append(
            float(rows[index]["bge_latency_ms"]) + elapsed_ms
        )

    return {
        "probabilities": probabilities,
        "levels": levels,
        "diagnostics": diagnostics,
        "model_load_ms": load_ms,
        "batch_size": BATCH_SIZE,
        "batched_total_ms": batch_total_ms,
        "batched_amortized_ms_per_case": batch_total_ms / len(rows),
        "backend_stats": dict(decider.stats),
        "single_request_latency_ms": _distribution(single_latencies),
        "combined_single_request_latency_ms": _distribution(combined_latencies),
    }


def _evaluate_threshold(
    rows: list[dict[str, Any]],
    probabilities: list[float],
    threshold: float,
) -> dict[str, Any]:
    accepted = [value >= threshold for value in probabilities]
    supported = [i for i, row in enumerate(rows) if row["expected"] is not None]
    near = [
        i
        for i, row in enumerate(rows)
        if row["category"] == "near_domain_unsupported_operation"
    ]
    ood = [i for i, row in enumerate(rows) if row["category"] == "out_of_domain"]
    unsupported = [i for i, row in enumerate(rows) if row["expected"] is None]

    supported_correct = sum(
        accepted[i] and bool(rows[i]["raw_correct"]) for i in supported
    )
    wrong_supported_accepted = sum(
        accepted[i] and not bool(rows[i]["raw_correct"]) for i in supported
    )
    near_rejected = sum(not accepted[i] for i in near)
    ood_rejected = sum(not accepted[i] for i in ood)
    false_routes = sum(accepted[i] for i in unsupported)

    supported_exact = _safe_rate(supported_correct, len(supported))
    near_rejection = _safe_rate(near_rejected, len(near))
    ood_rejection = _safe_rate(ood_rejected, len(ood))
    false_rate = _safe_rate(false_routes, len(unsupported))

    per_language: dict[str, Any] = {}
    for language in sorted({str(row["language"]) for row in rows}):
        indexes = [
            i for i, row in enumerate(rows) if str(row["language"]) == language
        ]
        lang_supported = [i for i in indexes if rows[i]["expected"] is not None]
        lang_unsupported = [i for i in indexes if rows[i]["expected"] is None]
        per_language[language] = {
            "supported_exact_route_accuracy": _safe_rate(
                sum(
                    accepted[i] and bool(rows[i]["raw_correct"])
                    for i in lang_supported
                ),
                len(lang_supported),
            ),
            "unsupported_rejection": _safe_rate(
                sum(not accepted[i] for i in lang_unsupported),
                len(lang_unsupported),
            ),
            "false_routes": sum(accepted[i] for i in lang_unsupported),
        }

    per_route: dict[str, Any] = {}
    for route in sorted(
        {
            str(row["expected"])
            for row in rows
            if row["expected"] is not None
        }
    ):
        indexes = [i for i, row in enumerate(rows) if row["expected"] == route]
        exact = sum(
            accepted[i] and bool(rows[i]["raw_correct"]) for i in indexes
        )
        per_route[route] = {
            "cases": len(indexes),
            "exact": exact,
            "exact_rate": _safe_rate(exact, len(indexes)),
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
        indexes = [
            i
            for i, row in enumerate(rows)
            if str(row["unsupported_family"]) == family
        ]
        rejected = sum(not accepted[i] for i in indexes)
        per_family[family] = {
            "cases": len(indexes),
            "rejected": rejected,
            "rejection_rate": _safe_rate(rejected, len(indexes)),
        }

    quality_pass = (
        supported_exact >= 0.85
        and near_rejection >= 0.97
        and ood_rejection == 1.0
        and false_rate <= 0.01
    )
    return {
        "rule_id": f"anyjev-l0-p{threshold:.3f}",
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


def _diagnostic_summary(
    diagnostics: list[dict[str, Any]],
) -> dict[str, Any]:
    numeric_keys = (
        "order_flip_raw",
        "order_flip_l0",
        "permutations",
        "shifts_used",
        "prior_strength",
    )
    numeric: dict[str, Any] = {}
    for key in numeric_keys:
        values = [
            float(item[key])
            for item in diagnostics
            if isinstance(item.get(key), (int, float))
            and math.isfinite(float(item[key]))
        ]
        numeric[key] = _distribution(values)

    categorical: dict[str, dict[str, int]] = {}
    for key in ("prior_method", "readout"):
        counts: dict[str, int] = {}
        for item in diagnostics:
            value = item.get(key)
            if value is not None:
                label = str(value)
                counts[label] = counts.get(label, 0) + 1
        categorical[key] = counts

    return {
        "numeric": numeric,
        "categorical": categorical,
    }


def _probability_geometry(
    rows: list[dict[str, Any]],
    probabilities: list[float],
) -> dict[str, Any]:
    groups = {
        "supported_correct_winner": [
            i
            for i, row in enumerate(rows)
            if row["expected"] is not None and row["raw_correct"]
        ],
        "supported_wrong_winner": [
            i
            for i, row in enumerate(rows)
            if row["expected"] is not None and not row["raw_correct"]
        ],
        "near_domain_unsupported": [
            i
            for i, row in enumerate(rows)
            if row["category"] == "near_domain_unsupported_operation"
        ],
        "out_of_domain": [
            i for i, row in enumerate(rows) if row["category"] == "out_of_domain"
        ],
    }
    return {
        name: _distribution([probabilities[index] for index in indexes])
        for name, indexes in groups.items()
    }


def evaluate(cases: list[dict[str, Any]]) -> dict[str, Any]:
    rows, bge_runtime = _route_rows(cases)
    anyjev = _score_anyjev(rows)
    probabilities = list(anyjev.pop("probabilities"))
    levels = list(anyjev.pop("levels"))
    diagnostics = list(anyjev.pop("diagnostics"))

    rules = [
        _evaluate_threshold(rows, probabilities, threshold)
        for threshold in ACCEPTANCE_THRESHOLDS
    ]
    authority_violations = sum(bool(row["authority_violation"]) for row in rows)
    worthy = [
        rule
        for rule in rules
        if rule["quality_gate_pass"] and authority_violations == 0
    ]
    worthy.sort(
        key=lambda rule: (
            -float(rule["supported_exact_route_accuracy"]),
            int(rule["false_routes"]),
            float(rule["threshold"]),
        )
    )

    combined_p95 = anyjev["combined_single_request_latency_ms"]["p95"]
    runtime_pass = combined_p95 is not None and float(combined_p95) <= 250.0
    supported = [row for row in rows if row["expected"] is not None]
    raw_correct = sum(bool(row["raw_correct"]) for row in supported)

    diagnostic_keys: dict[str, int] = {}
    for item in diagnostics:
        for key in item:
            diagnostic_keys[key] = diagnostic_keys.get(key, 0) + 1

    return {
        "experiment": "anyjev-l0-content-free-noul-veto-v1",
        "models": {
            "ranker": {
                "name": BGE_MODEL_NAME,
                "revision": BGE_MODEL_REVISION,
                "schema_weight": SCHEMA_WEIGHT,
                "action_weight": ACTION_WEIGHT,
            },
            "verifier": {
                "source_revision": ANYJEV_SOURCE_REVISION,
                "base_model": BASE_MODEL,
                "base_model_revision": BASE_MODEL_REVISION,
                "transformers": TRANSFORMERS_VERSION,
                "level": "L0",
                "prior": "content_free",
                "prior_strength": 1.0,
                "device": "cpu",
                "dtype": "float32",
            },
        },
        "summary": {
            "cases": len(rows),
            "raw_supported_top1_accuracy": _safe_rate(raw_correct, len(supported)),
            "fixed_rule_count": len(rules),
            "quality_worthy_rule_count": len(worthy),
            "best_quality_rule": worthy[0] if worthy else None,
            "runtime_target_pass": runtime_pass,
            "promotable_rule_count": len(worthy) if runtime_pass else 0,
            "authority_violations": authority_violations,
            "execution_errors": 0,
            "decision_levels": {
                level: levels.count(level) for level in sorted(set(levels))
            },
            "diagnostic_key_counts": diagnostic_keys,
            "anyjev_diagnostics": _diagnostic_summary(diagnostics),
            "probability_geometry": _probability_geometry(rows, probabilities),
        },
        "bge_runtime": bge_runtime,
        "anyjev_runtime": anyjev,
        "quality_worthy_rules": worthy,
        "rule_results": rules,
        "rows": [
            {
                "case_id": row["case_id"],
                "category": row["category"],
                "language": row["language"],
                "unsupported_family": row["unsupported_family"],
                "expected": row["expected"],
                "raw_top_route": row["raw_top_route"],
                "raw_correct": row["raw_correct"],
                "p_true": probability,
                "level": level,
                "order_flip_raw": diagnostic.get("order_flip_raw"),
                "order_flip_l0": diagnostic.get("order_flip_l0"),
                "permutations": diagnostic.get("permutations"),
                "prior_method": diagnostic.get("prior_method"),
                "prior_strength": diagnostic.get("prior_strength"),
                "bge_latency_ms": row["bge_latency_ms"],
            }
            for row, probability, level, diagnostic in zip(
                rows, probabilities, levels, diagnostics, strict=True
            )
        ],
        "policy": {
            "data_role": "tuning_eligible_development",
            "failed_270_fresh_used": False,
            "failed_287_fresh_used": False,
            "calibration_or_blind_used": False,
            "schemarouter_labels_used": False,
            "anyjev_level": "L0",
            "prior": "content_free",
            "anyjev_can_select_route": False,
            "veto_only": True,
            "rank2_fallback": False,
            "prompt_variants_tested": 1,
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
                "quality_worthy_rule_count": result["summary"][
                    "quality_worthy_rule_count"
                ],
                "best_quality_rule": result["summary"]["best_quality_rule"],
                "runtime_target_pass": result["summary"]["runtime_target_pass"],
                "combined_latency_ms": result["anyjev_runtime"][
                    "combined_single_request_latency_ms"
                ],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
