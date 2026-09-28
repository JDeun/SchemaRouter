"""Evaluate frozen V6G relative multilingual cross-encoder gate on DEV only."""

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

from benchmarks.operation_routing_v6g_catalog import development_registry  # noqa: E402
from benchmarks.schema_adb_baseline import BGE_MODEL, BGE_REVISION  # noqa: E402
from benchmarks.schema_cross_encoder_membership import (  # noqa: E402
    RERANKER_MAX_LENGTH,
    RERANKER_MODEL,
    RERANKER_REVISION,
    RelativeCrossEncoderCapabilityGate,
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


def _tool(route_id: str) -> str:
    return route_id.split(".", 1)[0]


class BGEEncoder:
    def __init__(self) -> None:
        from sentence_transformers import SentenceTransformer

        started = time.perf_counter_ns()
        self.model = SentenceTransformer(
            BGE_MODEL,
            revision=BGE_REVISION,
            trust_remote_code=False,
            device="cpu",
        )
        self.load_ms = (time.perf_counter_ns() - started) / 1_000_000

    def __call__(self, texts: list[str]) -> list[list[float]]:
        vectors = self.model.encode(
            texts,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return vectors.tolist()


class CrossEncoderScorer:
    def __init__(self) -> None:
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        self.torch = torch
        started = time.perf_counter_ns()
        self.tokenizer = AutoTokenizer.from_pretrained(
            RERANKER_MODEL,
            revision=RERANKER_REVISION,
            trust_remote_code=False,
        )
        self.model = AutoModelForSequenceClassification.from_pretrained(
            RERANKER_MODEL,
            revision=RERANKER_REVISION,
            torch_dtype=torch.float32,
            trust_remote_code=False,
        )
        self.model.to("cpu")
        self.model.eval()
        self.load_ms = (time.perf_counter_ns() - started) / 1_000_000
        self.batch_latencies_ms: list[float] = []
        self.batch_sizes: list[int] = []
        self.max_seen_tokens = 0

    def __call__(self, query: str, documents: list[str]) -> list[float]:
        if not documents:
            raise ValueError("cross-encoder document batch must not be empty")
        queries = [query] * len(documents)
        encoded_untruncated = self.tokenizer(
            queries,
            documents,
            add_special_tokens=True,
            truncation=False,
        )
        lengths = [len(row) for row in encoded_untruncated["input_ids"]]
        self.max_seen_tokens = max(self.max_seen_tokens, *lengths)

        inputs = self.tokenizer(
            queries,
            documents,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=RERANKER_MAX_LENGTH,
        )
        inputs = {key: value.to("cpu") for key, value in inputs.items()}
        started = time.perf_counter_ns()
        with self.torch.inference_mode():
            logits = self.model(**inputs).logits
        elapsed_ms = (time.perf_counter_ns() - started) / 1_000_000
        self.batch_latencies_ms.append(elapsed_ms)
        self.batch_sizes.append(len(documents))

        if logits.ndim != 2 or logits.shape[1] != 1:
            raise ValueError(
                f"expected one relevance logit per pair, got shape={tuple(logits.shape)}"
            )
        return logits[:, 0].detach().cpu().float().tolist()


def evaluate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    registry = development_registry()

    bge = BGEEncoder()
    cross_encoder = CrossEncoderScorer()

    compile_started = time.perf_counter_ns()
    gate = RelativeCrossEncoderCapabilityGate(
        registry,
        bge_embedder=bge,
        pair_scorer=cross_encoder,
    )
    static_compile_ms = (time.perf_counter_ns() - compile_started) / 1_000_000

    allowed = set(gate.route_ids)
    result_rows: list[dict[str, Any]] = []
    latencies: list[float] = []
    execution_errors = 0
    authority_violations = 0
    positive_route_switches = 0
    raw_supported_correct = 0
    raw_supported_tool_correct = 0
    raw_correct_winner_vetoed = 0
    vetoes = 0
    true_unsupported_vetoes = 0
    complement_vetoes = 0
    background_vetoes = 0

    for case in rows:
        started = time.perf_counter_ns()
        try:
            result = gate.route(str(case["query"]))
            elapsed_ms = (time.perf_counter_ns() - started) / 1_000_000
            latencies.append(elapsed_ms)

            predicted = result["predicted"]
            raw_top = str(result["raw_top_route"])
            expected = case.get("expected")
            vetoed = predicted is None

            if predicted is not None and predicted not in allowed:
                authority_violations += 1
            if predicted is not None and predicted != raw_top:
                authority_violations += 1
                positive_route_switches += 1

            if expected is not None:
                if raw_top == expected:
                    raw_supported_correct += 1
                    if vetoed:
                        raw_correct_winner_vetoed += 1
                if _tool(raw_top) == _tool(str(expected)):
                    raw_supported_tool_correct += 1

            if vetoed:
                vetoes += 1
                if expected is None:
                    true_unsupported_vetoes += 1
                if result["negative_source"] == "complement":
                    complement_vetoes += 1
                elif result["negative_source"] == "background":
                    background_vetoes += 1

            result_rows.append(
                {
                    "id": case["id"],
                    "query": case["query"],
                    "category": case["category"],
                    "language": case["language"],
                    "expected": expected,
                    "predicted": predicted,
                    "raw_top_route": raw_top,
                    "raw_tool": result["raw_tool"],
                    "supported_max": result["supported_max"],
                    "complement_max": result["complement_max"],
                    "background_max": result["background_max"],
                    "negative_max": result["negative_max"],
                    "negative_advantage": result["negative_advantage"],
                    "negative_source": result["negative_source"],
                    "best_supported": result["best_supported"],
                    "best_complement": result["best_complement"],
                    "reason": result["reason"],
                    "latency_ms": elapsed_ms,
                    "error": None,
                }
            )
        except Exception as exc:  # noqa: BLE001
            elapsed_ms = (time.perf_counter_ns() - started) / 1_000_000
            latencies.append(elapsed_ms)
            execution_errors += 1
            result_rows.append(
                {
                    "id": case["id"],
                    "query": case["query"],
                    "category": case["category"],
                    "language": case["language"],
                    "expected": case.get("expected"),
                    "predicted": None,
                    "raw_top_route": None,
                    "raw_tool": None,
                    "supported_max": None,
                    "complement_max": None,
                    "background_max": None,
                    "negative_max": None,
                    "negative_advantage": None,
                    "negative_source": None,
                    "best_supported": None,
                    "best_complement": None,
                    "reason": "exception",
                    "latency_ms": elapsed_ms,
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

    supported_correct = sum(
        row["predicted"] == row["expected"] for row in supported
    )
    near_rejected = sum(row["predicted"] is None for row in near)
    ood_rejected = sum(row["predicted"] is None for row in ood)
    false_routes = sum(row["predicted"] is not None for row in unsupported)

    def values(category_rows: list[dict[str, Any]], key: str) -> list[float]:
        return [
            float(row[key])
            for row in category_rows
            if row[key] is not None
        ]

    score_keys = (
        "supported_max",
        "complement_max",
        "background_max",
        "negative_max",
        "negative_advantage",
    )
    score_distributions = {
        key: {
            "supported": _distribution(values(supported, key)),
            "near_domain": _distribution(values(near, key)),
            "ood": _distribution(values(ood, key)),
        }
        for key in score_keys
    }

    metrics: dict[str, Any] = {
        "supported_exact_route_accuracy": supported_correct / len(supported),
        "raw_supported_exact_route_accuracy": raw_supported_correct / len(supported),
        "raw_supported_tool_accuracy": raw_supported_tool_correct / len(supported),
        "near_domain_unsupported_rejection": near_rejected / len(near),
        "out_of_domain_rejection": ood_rejected / len(ood),
        "false_routes": false_routes,
        "false_route_rate": false_routes / len(unsupported),
        "vetoes": vetoes,
        "true_unsupported_vetoes": true_unsupported_vetoes,
        "veto_precision": (
            true_unsupported_vetoes / vetoes if vetoes else 0.0
        ),
        "veto_recall": (
            true_unsupported_vetoes / len(unsupported)
            if unsupported
            else 0.0
        ),
        "raw_correct_winner_vetoed": raw_correct_winner_vetoed,
        "raw_correct_winner_veto_rate": (
            raw_correct_winner_vetoed / raw_supported_correct
            if raw_supported_correct
            else 0.0
        ),
        "complement_vetoes": complement_vetoes,
        "background_vetoes": background_vetoes,
        **score_distributions,
        "model_load_ms": {
            "bge": bge.load_ms,
            "cross_encoder": cross_encoder.load_ms,
        },
        "static_compile_ms": static_compile_ms,
        "cross_encoder_batch_latency_ms": _distribution(
            cross_encoder.batch_latencies_ms
        ),
        "cross_encoder_batch_size": _distribution(
            [float(value) for value in cross_encoder.batch_sizes]
        ),
        "cross_encoder_max_untruncated_tokens": cross_encoder.max_seen_tokens,
        "latency_ms": _distribution(latencies),
        "positive_route_switches": positive_route_switches,
        "authority_violations": authority_violations,
        "execution_errors": execution_errors,
    }

    per_language: dict[str, dict[str, float | int]] = {}
    for language in sorted({str(row["language"]) for row in result_rows}):
        lang_rows = [row for row in result_rows if row["language"] == language]
        lang_supported = [
            row for row in lang_rows if row["category"] == "supported"
        ]
        lang_unsupported = [
            row for row in lang_rows if row["category"] != "supported"
        ]
        per_language[language] = {
            "cases": len(lang_rows),
            "supported_exact": (
                sum(
                    row["predicted"] == row["expected"]
                    for row in lang_supported
                )
                / len(lang_supported)
            ),
            "unsupported_rejection": (
                sum(row["predicted"] is None for row in lang_unsupported)
                / len(lang_unsupported)
            ),
        }
    metrics["per_language"] = per_language

    p95 = metrics["latency_ms"]["p95"]
    quality_gates = {
        "supported_exact_route_accuracy": (
            metrics["supported_exact_route_accuracy"] >= 0.85
        ),
        "near_domain_unsupported_rejection": (
            metrics["near_domain_unsupported_rejection"] >= 0.97
        ),
        "out_of_domain_rejection": (
            metrics["out_of_domain_rejection"] == 1.0
        ),
        "false_route_rate": metrics["false_route_rate"] <= 0.01,
        "authority_violations": authority_violations == 0,
        "positive_route_switches": positive_route_switches == 0,
        "execution_errors": execution_errors == 0,
    }
    runtime_gate = p95 is not None and float(p95) <= 250.0

    return {
        "experiment": "relative-multilingual-cross-encoder-capability-gate-v1",
        "issue": 408,
        "surface": "V6G-development",
        "models": {
            "bge": {"name": BGE_MODEL, "revision": BGE_REVISION},
            "cross_encoder": {
                "name": RERANKER_MODEL,
                "revision": RERANKER_REVISION,
                "max_length": RERANKER_MAX_LENGTH,
                "device": "cpu",
                "dtype": "float32",
            },
        },
        "metrics": metrics,
        "quality_gates": quality_gates,
        "runtime_gate": runtime_gate,
        "quality_pass": all(quality_gates.values()),
        "surface_pass": all(quality_gates.values()) and runtime_gate,
        "policy": {
            "confirmation_scored": False,
            "prior_failed_rows_used_for_tuning": False,
            "raw_bge_is_sole_positive_selector": True,
            "cross_encoder_veto_only": True,
            "registered_supported_documents": True,
            "schema_derived_complement_documents": True,
            "frozen_background_documents": True,
            "benchmark_rows_used_for_evidence_fit": False,
            "positive_rerank": False,
            "endpoint_switch": False,
            "rank2_fallback": False,
            "pseudo_route": False,
            "probability_threshold": None,
            "margin_threshold": None,
            "temperature": None,
            "score_normalization": None,
            "exact_ties_preserve": True,
            "dev_selected_hyperparameters": False,
        },
        "rows": result_rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--development", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    rows = json.loads(args.development.read_text(encoding="utf-8"))
    if not isinstance(rows, list) or any(
        not isinstance(row, dict) for row in rows
    ):
        raise ValueError("development corpus must be a list of objects")

    result = evaluate(rows)
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
