"""DEV-only external Qwen3 semantic capability verifier diagnostic."""

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

QWEN_MODEL_NAME = "Qwen/Qwen3-Reranker-0.6B"
QWEN_MODEL_REVISION = "e61197ed45024b0ed8a2d74b80b4d909f1255473"
MAX_LENGTH = 256
BATCH_SIZE = 8
LATENCY_SAMPLE_PER_LANGUAGE = 20
ACCEPTANCE_THRESHOLDS = (
    0.50,
    0.70,
    0.80,
    0.90,
    0.95,
    0.98,
    0.99,
    0.995,
)
CAPABILITY_INSTRUCTION = (
    "Decide whether the registered endpoint capability can fully execute the "
    "user request. Judge exact operational capability, not topical similarity. "
    "Answer yes only if every requested operation is explicitly supported by "
    "the endpoint contract. Do not infer capabilities that are not stated. "
    "If the request asks for an operation outside the explicit contract, "
    "answer no."
)
SYSTEM_PROMPT = (
    "Judge whether the Document meets the requirements based on the Query and "
    "the Instruct provided. Note that the answer can only be \"yes\" or "
    "\"no\"."
)
PREFIX = (
    "<|im_start|>system\n"
    + SYSTEM_PROMPT
    + "<|im_end|>\n<|im_start|>user\n"
)
SUFFIX = (
    "<|im_end|>\n<|im_start|>assistant\n"
    "<think>\n\n</think>\n\n"
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
    route_id = f"{tool.key}.{endpoint.name}"
    aliases = ", ".join(sorted(set(endpoint.operation_aliases)))
    return "\n".join(
        [
            f"Registered endpoint: {route_id}",
            f"Tool scope: {tool.description.strip()}",
            f"Explicit endpoint capability: {endpoint.description.strip()}",
            f"Trusted operation aliases: {aliases}",
            (
                "Scope rule: This endpoint supports only the capability "
                "explicitly stated above. Unlisted operations are not "
                "supported by this endpoint."
            ),
        ]
    )


def _registered_contracts(registry: Any) -> dict[str, str]:
    contracts: dict[str, str] = {}
    for tool in registry.tools():
        for endpoint in tool.endpoints:
            route_id = f"{tool.key}.{endpoint.name}"
            contracts[route_id] = _capability_contract(tool, endpoint)
    return contracts


def _format_verifier_input(query: str, document: str) -> str:
    body = (
        f"<Instruct>: {CAPABILITY_INSTRUCTION}\n"
        f"<Query>: {query}\n"
        f"<Document>: {document}"
    )
    return PREFIX + body + SUFFIX


def _route_rows(
    cases: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, str]]:
    registry = reference_registry()
    contracts = _registered_contracts(registry)

    model_started = time.perf_counter_ns()
    bge_model = _load_bge_model()
    model_load_ms = (
        time.perf_counter_ns() - model_started
    ) / 1_000_000
    backend_started = time.perf_counter_ns()
    backend = FrozenBgeM3DualViewBackend(
        registry,
        _bge_embedder(bge_model),
    )
    backend_init_ms = (
        time.perf_counter_ns() - backend_started
    ) / 1_000_000

    rows: list[dict[str, Any]] = []
    bge_latencies: list[float] = []
    allowed_routes = set(backend.route_ids)

    for case in cases:
        started = time.perf_counter_ns()
        scored = backend.score_routes(
            str(case["query"]),
            backend.route_ids,
        )
        latency_ms = (
            time.perf_counter_ns() - started
        ) / 1_000_000
        bge_latencies.append(latency_ms)
        raw_route = str(scored["top_route"])
        expected = case.get("expected")
        rows.append(
            {
                "case_id": str(case.get("id")),
                "query": str(case["query"]),
                "category": case.get("category"),
                "language": case.get("language"),
                "unsupported_family": case.get("unsupported_family"),
                "expected": expected,
                "raw_top_route": raw_route,
                "raw_top_score": float(scored["top_score"]),
                "raw_top_margin": float(scored["top_margin"]),
                "raw_correct": (
                    expected is not None and raw_route == expected
                ),
                "endpoint_contract": contracts[raw_route],
                "bge_latency_ms": latency_ms,
                "authority_violation": raw_route not in allowed_routes,
            }
        )

    del backend
    del bge_model
    gc.collect()

    return rows, {
        "model_load_ms": model_load_ms,
        "backend_static_init_ms": backend_init_ms,
        "query_latency_ms": _distribution(bge_latencies),
    }, contracts


def _load_qwen():
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    started = time.perf_counter_ns()
    tokenizer = AutoTokenizer.from_pretrained(
        QWEN_MODEL_NAME,
        revision=QWEN_MODEL_REVISION,
        trust_remote_code=False,
        padding_side="left",
    )
    model = AutoModelForCausalLM.from_pretrained(
        QWEN_MODEL_NAME,
        revision=QWEN_MODEL_REVISION,
        trust_remote_code=False,
        torch_dtype=torch.float32,
    )
    model.eval()
    load_ms = (time.perf_counter_ns() - started) / 1_000_000

    yes_ids = tokenizer(
        "yes",
        add_special_tokens=False,
    ).input_ids
    no_ids = tokenizer(
        "no",
        add_special_tokens=False,
    ).input_ids
    if len(yes_ids) != 1 or len(no_ids) != 1:
        raise RuntimeError(
            "Qwen yes/no labels must tokenize to exactly one token"
        )
    return tokenizer, model, int(yes_ids[0]), int(no_ids[0]), load_ms


def _score_batch(
    *,
    tokenizer: Any,
    model: Any,
    yes_token_id: int,
    no_token_id: int,
    texts: list[str],
) -> list[float]:
    import torch

    inputs = tokenizer(
        texts,
        padding=True,
        truncation=True,
        max_length=MAX_LENGTH,
        return_tensors="pt",
        add_special_tokens=False,
    )
    with torch.inference_mode():
        logits = model(**inputs).logits[:, -1, :]
        binary = torch.stack(
            [
                logits[:, no_token_id],
                logits[:, yes_token_id],
            ],
            dim=1,
        )
        probabilities = torch.softmax(binary, dim=1)[:, 1]
    values = [float(value) for value in probabilities.tolist()]
    if any(not math.isfinite(value) for value in values):
        raise RuntimeError("Qwen verifier produced non-finite probability")
    return values


def _latency_sample_indexes(rows: list[dict[str, Any]]) -> list[int]:
    import hashlib

    selected: list[int] = []
    languages = sorted({str(row["language"]) for row in rows})
    for language in languages:
        candidates = [
            (
                hashlib.sha256(
                    str(row["case_id"]).encode()
                ).hexdigest(),
                index,
            )
            for index, row in enumerate(rows)
            if str(row["language"]) == language
        ]
        candidates.sort()
        selected.extend(
            index
            for _, index in candidates[:LATENCY_SAMPLE_PER_LANGUAGE]
        )
    return sorted(selected)


def _score_qwen(
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    tokenizer, model, yes_id, no_id, load_ms = _load_qwen()
    texts = [
        _format_verifier_input(
            str(row["query"]),
            str(row["endpoint_contract"]),
        )
        for row in rows
    ]

    batch_started = time.perf_counter_ns()
    probabilities: list[float] = []
    batch_latencies: list[float] = []
    for start in range(0, len(texts), BATCH_SIZE):
        batch = texts[start : start + BATCH_SIZE]
        started = time.perf_counter_ns()
        probabilities.extend(
            _score_batch(
                tokenizer=tokenizer,
                model=model,
                yes_token_id=yes_id,
                no_token_id=no_id,
                texts=batch,
            )
        )
        elapsed_ms = (
            time.perf_counter_ns() - started
        ) / 1_000_000
        batch_latencies.append(elapsed_ms)
    total_batch_ms = (
        time.perf_counter_ns() - batch_started
    ) / 1_000_000

    sample_indexes = _latency_sample_indexes(rows)
    single_latencies: list[float] = []
    combined_latencies: list[float] = []
    for index in sample_indexes:
        started = time.perf_counter_ns()
        _score_batch(
            tokenizer=tokenizer,
            model=model,
            yes_token_id=yes_id,
            no_token_id=no_id,
            texts=[texts[index]],
        )
        latency_ms = (
            time.perf_counter_ns() - started
        ) / 1_000_000
        single_latencies.append(latency_ms)
        combined_latencies.append(
            float(rows[index]["bge_latency_ms"]) + latency_ms
        )

    return {
        "probabilities": probabilities,
        "model_load_ms": load_ms,
        "batch_size": BATCH_SIZE,
        "batch_latency_ms": _distribution(batch_latencies),
        "batched_total_ms": total_batch_ms,
        "batched_amortized_ms_per_case": (
            total_batch_ms / len(rows)
            if rows
            else None
        ),
        "single_request_sample_cases": len(sample_indexes),
        "single_request_latency_ms": _distribution(single_latencies),
        "combined_single_request_latency_ms": _distribution(
            combined_latencies
        ),
    }


def _safe_rate(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def _evaluate_threshold(
    rows: list[dict[str, Any]],
    probabilities: list[float],
    threshold: float,
) -> dict[str, Any]:
    accepted = [
        probability >= threshold
        for probability in probabilities
    ]
    supported = [
        i for i, row in enumerate(rows)
        if row["expected"] is not None
    ]
    near = [
        i for i, row in enumerate(rows)
        if row["category"] == "near_domain_unsupported_operation"
    ]
    ood = [
        i for i, row in enumerate(rows)
        if row["category"] == "out_of_domain"
    ]
    unsupported = [
        i for i, row in enumerate(rows)
        if row["expected"] is None
    ]

    supported_correct = sum(
        accepted[i] and bool(rows[i]["raw_correct"])
        for i in supported
    )
    wrong_supported_accepted = sum(
        accepted[i] and not bool(rows[i]["raw_correct"])
        for i in supported
    )
    near_rejected = sum(not accepted[i] for i in near)
    ood_rejected = sum(not accepted[i] for i in ood)
    false_routes = sum(accepted[i] for i in unsupported)

    supported_exact = _safe_rate(
        supported_correct,
        len(supported),
    )
    near_rejection = _safe_rate(near_rejected, len(near))
    ood_rejection = _safe_rate(ood_rejected, len(ood))
    false_rate = _safe_rate(false_routes, len(unsupported))

    per_language: dict[str, Any] = {}
    for language in sorted({str(row["language"]) for row in rows}):
        indexes = [
            i for i, row in enumerate(rows)
            if str(row["language"]) == language
        ]
        lang_supported = [
            i for i in indexes
            if rows[i]["expected"] is not None
        ]
        lang_unsupported = [
            i for i in indexes
            if rows[i]["expected"] is None
        ]
        per_language[language] = {
            "cases": len(indexes),
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
            "false_routes": sum(
                accepted[i] for i in lang_unsupported
            ),
        }

    per_route: dict[str, Any] = {}
    for route in sorted({str(row["raw_top_route"]) for row in rows}):
        indexes = [
            i for i, row in enumerate(rows)
            if str(row["raw_top_route"]) == route
        ]
        per_route[route] = {
            "cases": len(indexes),
            "accepted": sum(accepted[i] for i in indexes),
            "accepted_correct": sum(
                accepted[i] and bool(rows[i]["raw_correct"])
                for i in indexes
            ),
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
            i for i, row in enumerate(rows)
            if str(row["unsupported_family"]) == family
        ]
        per_family[family] = {
            "cases": len(indexes),
            "rejected": sum(not accepted[i] for i in indexes),
            "rejection_rate": _safe_rate(
                sum(not accepted[i] for i in indexes),
                len(indexes),
            ),
        }

    quality_pass = (
        supported_exact >= 0.85
        and near_rejection >= 0.97
        and ood_rejection == 1.0
        and false_rate <= 0.01
    )
    return {
        "rule_id": f"qwen3-p{threshold:.3f}",
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
        "per_route": per_route,
        "unsupported_family_rejection": per_family,
        "quality_gate_pass": quality_pass,
    }


def _probability_geometry(
    rows: list[dict[str, Any]],
    probabilities: list[float],
) -> dict[str, Any]:
    groups = {
        "supported_correct_winner": [
            i for i, row in enumerate(rows)
            if row["expected"] is not None and row["raw_correct"]
        ],
        "supported_wrong_winner": [
            i for i, row in enumerate(rows)
            if row["expected"] is not None and not row["raw_correct"]
        ],
        "near_domain_unsupported": [
            i for i, row in enumerate(rows)
            if row["category"] == "near_domain_unsupported_operation"
        ],
        "out_of_domain": [
            i for i, row in enumerate(rows)
            if row["category"] == "out_of_domain"
        ],
    }
    return {
        name: _distribution(
            [probabilities[index] for index in indexes]
        )
        for name, indexes in groups.items()
    }


def evaluate(cases: list[dict[str, Any]]) -> dict[str, Any]:
    rows, bge_runtime, contracts = _route_rows(cases)
    qwen = _score_qwen(rows)
    probabilities = list(qwen.pop("probabilities"))
    if len(probabilities) != len(rows):
        raise RuntimeError("Qwen probability count mismatch")

    rules = [
        _evaluate_threshold(rows, probabilities, threshold)
        for threshold in ACCEPTANCE_THRESHOLDS
    ]
    authority_violations = sum(
        bool(row["authority_violation"]) for row in rows
    )
    p95 = qwen["combined_single_request_latency_ms"]["p95"]
    runtime_pass = (
        p95 is not None and float(p95) <= 250.0
    )

    quality_worthy = [
        rule for rule in rules
        if bool(rule["quality_gate_pass"])
        and authority_violations == 0
    ]
    quality_worthy.sort(
        key=lambda rule: (
            -float(rule["supported_exact_route_accuracy"]),
            int(rule["false_routes"]),
            -float(rule["near_domain_unsupported_rejection"]),
            -float(rule["out_of_domain_rejection"]),
            float(rule["threshold"]),
        )
    )
    promotable = (
        quality_worthy if runtime_pass else []
    )

    supported = [
        row for row in rows if row["expected"] is not None
    ]
    raw_supported_correct = sum(
        bool(row["raw_correct"]) for row in supported
    )

    artifact_rows = [
        {
            "case_id": row["case_id"],
            "category": row["category"],
            "language": row["language"],
            "unsupported_family": row["unsupported_family"],
            "expected": row["expected"],
            "raw_top_route": row["raw_top_route"],
            "raw_correct": row["raw_correct"],
            "raw_top_score": row["raw_top_score"],
            "raw_top_margin": row["raw_top_margin"],
            "p_yes": probability,
            "bge_latency_ms": row["bge_latency_ms"],
        }
        for row, probability in zip(
            rows,
            probabilities,
            strict=True,
        )
    ]

    return {
        "experiment": "external-qwen3-semantic-capability-verifier-v1",
        "models": {
            "ranker": {
                "name": BGE_MODEL_NAME,
                "revision": BGE_MODEL_REVISION,
                "schema_weight": SCHEMA_WEIGHT,
                "action_weight": ACTION_WEIGHT,
            },
            "verifier": {
                "name": QWEN_MODEL_NAME,
                "revision": QWEN_MODEL_REVISION,
                "max_length": MAX_LENGTH,
                "instruction": CAPABILITY_INSTRUCTION,
            },
        },
        "summary": {
            "cases": len(rows),
            "supported_cases": len(supported),
            "raw_supported_correct": raw_supported_correct,
            "raw_supported_top1_accuracy": _safe_rate(
                raw_supported_correct,
                len(supported),
            ),
            "authority_violations": authority_violations,
            "execution_errors": 0,
            "fixed_rule_count": len(rules),
            "quality_worthy_rule_count": len(quality_worthy),
            "runtime_target_pass": runtime_pass,
            "promotable_rule_count": len(promotable),
            "best_quality_rule": (
                quality_worthy[0] if quality_worthy else None
            ),
            "best_promotable_rule": (
                promotable[0] if promotable else None
            ),
            "probability_geometry": _probability_geometry(
                rows,
                probabilities,
            ),
        },
        "bge_runtime": bge_runtime,
        "qwen_runtime": qwen,
        "endpoint_contracts": contracts,
        "quality_worthy_rules": quality_worthy,
        "promotable_rules": promotable,
        "rule_results": rules,
        "rows": artifact_rows,
        "policy": {
            "data_role": "tuning_eligible_development",
            "schemarouter_training_performed": False,
            "failed_270_fresh_used": False,
            "failed_287_fresh_used": False,
            "calibration_or_blind_used": False,
            "verifier_can_select_route": False,
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

    cases = json.loads(
        args.corpus.read_text(encoding="utf-8")
    )
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
                "runtime_target_pass": result["summary"][
                    "runtime_target_pass"
                ],
                "promotable_rule_count": result["summary"][
                    "promotable_rule_count"
                ],
                "best_quality_rule": result["summary"][
                    "best_quality_rule"
                ],
                "combined_single_request_latency_ms": result[
                    "qwen_runtime"
                ]["combined_single_request_latency_ms"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
