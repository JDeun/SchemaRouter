"""Evaluate frozen V5F external zero-shot membership veto on DEV only."""

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

from benchmarks.external_zeroshot_membership import (  # noqa: E402
    BGE_MODEL,
    BGE_REVISION,
    ZERO_SHOT_MODEL,
    ExternalZeroShotMembershipRouter,
)
from benchmarks.operation_routing_v5f_catalog import development_registry  # noqa: E402


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


def _load_bge() -> Any:
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(
        BGE_MODEL,
        revision=BGE_REVISION,
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


class ZeroShotRunner:
    def __init__(self, revision: str) -> None:
        from transformers import pipeline

        self.pipeline = pipeline(
            "zero-shot-classification",
            model=ZERO_SHOT_MODEL,
            tokenizer=ZERO_SHOT_MODEL,
            revision=revision,
            device=-1,
        )
        self.revision = revision
        self.latencies_ms: list[float] = []

    def __call__(
        self,
        query: str,
        labels: list[str],
        hypothesis_template: str,
    ) -> dict[str, Any]:
        started = time.perf_counter_ns()
        result = self.pipeline(
            query,
            candidate_labels=labels,
            hypothesis_template=hypothesis_template,
            multi_label=False,
            batch_size=max(1, len(labels)),
        )
        self.latencies_ms.append(
            (time.perf_counter_ns() - started) / 1_000_000
        )
        returned_labels = [str(label) for label in result["labels"]]
        returned_scores = [float(score) for score in result["scores"]]
        if not returned_labels:
            raise ValueError("zero-shot classifier returned no labels")
        return {
            "top_label": returned_labels[0],
            "scores": dict(
                zip(returned_labels, returned_scores, strict=True)
            ),
        }


def evaluate(
    rows: list[dict[str, Any]],
    *,
    zero_shot_revision: str,
) -> dict[str, Any]:
    bge_model = _load_bge()
    zero_shot = ZeroShotRunner(zero_shot_revision)
    registry = development_registry()

    static_started = time.perf_counter_ns()
    router = ExternalZeroShotMembershipRouter(
        registry,
        _bge_embedder(bge_model),
        zero_shot,
    )
    static_ms = (time.perf_counter_ns() - static_started) / 1_000_000

    allowed = set(router.route_ids)
    result_rows: list[dict[str, Any]] = []
    latencies: list[float] = []
    authority_violations = 0
    execution_errors = 0
    positive_route_switches = 0
    raw_supported_correct = 0
    raw_supported_tool_correct = 0
    raw_correct_winner_vetoed = 0
    total_vetoes = 0
    true_unsupported_vetoes = 0
    outside_top1 = 0

    for case in rows:
        started = time.perf_counter_ns()
        try:
            result = router.route(str(case["query"]))
            elapsed_ms = (time.perf_counter_ns() - started) / 1_000_000
            latencies.append(elapsed_ms)

            predicted = result["predicted"]
            raw_top = str(result["raw_top_route"])
            expected = case.get("expected")
            vetoed = predicted is None

            if predicted is not None and predicted not in allowed:
                authority_violations += 1
            if predicted is not None and predicted != raw_top:
                positive_route_switches += 1
                authority_violations += 1

            if expected is not None:
                if raw_top == expected:
                    raw_supported_correct += 1
                    if vetoed:
                        raw_correct_winner_vetoed += 1
                expected_tool = str(expected).split(".", 1)[0]
                raw_tool = raw_top.split(".", 1)[0]
                if expected_tool == raw_tool:
                    raw_supported_tool_correct += 1

            if vetoed:
                total_vetoes += 1
                if expected is None:
                    true_unsupported_vetoes += 1
            if result["veto_reason"] == "outside_label_top1":
                outside_top1 += 1

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
                    "tool_supported_leaves": result["tool_supported_leaves"],
                    "tool_has_unknown_leaf": result["tool_has_unknown_leaf"],
                    "candidate_labels": result["candidate_labels"],
                    "zero_shot_top_label": result["zero_shot_top_label"],
                    "zero_shot_scores": result["zero_shot_scores"],
                    "veto": result["veto"],
                    "veto_reason": result["veto_reason"],
                    "latency_ms": elapsed_ms,
                    "error": None,
                }
            )
        except Exception as exc:  # noqa: BLE001 -- evidence must record failures.
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
                    "tool_supported_leaves": [],
                    "tool_has_unknown_leaf": None,
                    "candidate_labels": [],
                    "zero_shot_top_label": None,
                    "zero_shot_scores": None,
                    "veto": None,
                    "veto_reason": "exception",
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
        row["predicted"] == row["expected"]
        for row in supported
    )
    near_rejected = sum(row["predicted"] is None for row in near)
    ood_rejected = sum(row["predicted"] is None for row in ood)
    false_routes = sum(
        row["predicted"] is not None
        for row in unsupported
    )

    metrics: dict[str, Any] = {
        "supported_exact_route_accuracy": supported_correct / len(supported),
        "raw_supported_exact_route_accuracy": raw_supported_correct / len(supported),
        "raw_supported_tool_accuracy": raw_supported_tool_correct / len(supported),
        "near_domain_unsupported_rejection": near_rejected / len(near),
        "out_of_domain_rejection": ood_rejected / len(ood),
        "false_routes": false_routes,
        "false_route_rate": false_routes / len(unsupported),
        "vetoes": total_vetoes,
        "true_unsupported_vetoes": true_unsupported_vetoes,
        "veto_precision": (
            true_unsupported_vetoes / total_vetoes
            if total_vetoes
            else 0.0
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
        "outside_top1_count": outside_top1,
        "positive_route_switches": positive_route_switches,
        "authority_violations": authority_violations,
        "execution_errors": execution_errors,
        "static_embedding_ms": static_ms,
        "zero_shot_latency_ms": _distribution(zero_shot.latencies_ms),
        "latency_ms": _distribution(latencies),
    }

    per_language: dict[str, dict[str, float | int]] = {}
    for language in sorted({str(row["language"]) for row in result_rows}):
        language_rows = [
            row
            for row in result_rows
            if row["language"] == language
        ]
        language_supported = [
            row for row in language_rows if row["category"] == "supported"
        ]
        language_unsupported = [
            row for row in language_rows if row["category"] != "supported"
        ]
        per_language[language] = {
            "cases": len(language_rows),
            "supported_exact": (
                sum(
                    row["predicted"] == row["expected"]
                    for row in language_supported
                )
                / len(language_supported)
            ),
            "unsupported_rejection": (
                sum(row["predicted"] is None for row in language_unsupported)
                / len(language_unsupported)
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
        "experiment": "external-multilingual-zeroshot-membership-v1",
        "issue": 371,
        "surface": "0.12-F-development",
        "models": {
            "bge": {"name": BGE_MODEL, "revision": BGE_REVISION},
            "zero_shot": {
                "name": ZERO_SHOT_MODEL,
                "resolved_revision": zero_shot_revision,
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
            "external_classifier_veto_only": True,
            "external_classifier_positive_rerank": False,
            "endpoint_filter": False,
            "confidence_or_similarity_threshold": False,
            "learned_on_schemarouter": False,
            "cross_tool_fallback": False,
            "pseudo_route": False,
        },
        "rows": result_rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--development", type=Path, required=True)
    parser.add_argument("--zero-shot-revision", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    rows = json.loads(args.development.read_text(encoding="utf-8"))
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise ValueError("development corpus must be a list of objects")

    result = evaluate(
        rows,
        zero_shot_revision=args.zero_shot_revision,
    )
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
                "models": result["models"],
                "metrics": result["metrics"],
                "quality_gates": result["quality_gates"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
