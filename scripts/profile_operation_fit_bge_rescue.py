from __future__ import annotations

import argparse
import asyncio
import gc
import json
from pathlib import Path
from typing import Any, Iterable

import torch
from benchmark_decision_routing import (
    BenchmarkCase,
    BenchmarkRow,
    benchmark_planner,
    load_callable,
    load_corpus,
    reference_registry,
)
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from schemarouter import EmbeddingDecisionBackend, SchemaPlanner
from schemarouter.decisions import DecisionRequest, DecisionResult


BASELINE_THRESHOLD = 0.40
BGE_MODEL = "BAAI/bge-reranker-v2-m3"
BGE_THRESHOLDS: tuple[float, ...] = (
    0.0,
    0.00000001,
    0.00000003,
    0.0000001,
    0.0000003,
    0.000001,
    0.000003,
    0.00001,
    0.00003,
    0.0001,
    0.0003,
    0.001,
    0.0015,
    0.002,
    0.003,
    0.004,
    0.005,
    0.006,
    0.007,
    0.008,
    0.009,
    0.01,
    0.0125,
    0.015,
    0.02,
    0.03,
    0.05,
)


class ScoreRecordingEmbeddingDecisionBackend(EmbeddingDecisionBackend):
    """Permissive MiniLM gate that records operation cosine scores."""

    def __init__(self, embedder: Any) -> None:
        super().__init__(embedder, min_similarity=-1.0, min_margin=0.0)
        self.similarities: dict[str, list[float]] = {}
        self.requests: dict[str, DecisionRequest] = {}

    def _result(
        self,
        request: DecisionRequest,
        raw: Iterable[Iterable[float]],
    ) -> DecisionResult:
        vectors = self._coerce_vectors(raw, expected_count=len(request.options) + 1)
        query_vector, *option_vectors = vectors
        ranked = sorted(
            (self._cosine(query_vector, vector) for vector in option_vectors),
            reverse=True,
        )
        self.similarities[request.query] = ranked
        self.requests[request.query] = request
        return super()._result(request, vectors)


def _option_text(option: Any) -> str:
    label = option.label.strip() or option.id
    description = option.description.strip()
    return f"{label}\n{description}" if description else label


def _bge_scores(
    requests: dict[str, DecisionRequest],
) -> dict[str, list[float]]:
    tokenizer = AutoTokenizer.from_pretrained(BGE_MODEL)
    model = AutoModelForSequenceClassification.from_pretrained(BGE_MODEL)
    model.eval()

    pair_queries: list[str] = []
    pair_options: list[str] = []
    spans: list[tuple[str, int, int]] = []
    for query, request in requests.items():
        start = len(pair_queries)
        for option in request.options:
            pair_queries.append(query)
            pair_options.append(_option_text(option))
        spans.append((query, start, len(pair_queries)))

    probabilities: list[float] = []
    with torch.no_grad():
        for start in range(0, len(pair_queries), 8):
            end = min(start + 8, len(pair_queries))
            encoded = tokenizer(
                pair_queries[start:end],
                pair_options[start:end],
                padding=True,
                truncation=True,
                max_length=256,
                return_tensors="pt",
            )
            logits = model(**encoded, return_dict=True).logits
            flattened = logits.reshape(logits.shape[0], -1)
            if flattened.shape[1] != 1:
                raise RuntimeError(
                    f"{BGE_MODEL} returned {flattened.shape[1]} logits per pair"
                )
            probabilities.extend(
                float(value)
                for value in torch.sigmoid(flattened[:, 0].float()).cpu().tolist()
            )

    scores = {
        query: sorted(probabilities[start:end], reverse=True)
        for query, start, end in spans
    }
    del model
    del tokenizer
    gc.collect()
    return scores


def _correct(case: BenchmarkCase, predicted: str | None) -> bool:
    return predicted is None if case.expect_abstain else predicted == case.expected


def _split_metrics(
    cases: list[BenchmarkCase],
    rows_by_id: dict[str, BenchmarkRow],
    minilm_scores: dict[str, list[float]],
    bge_scores: dict[str, list[float]],
    *,
    split: str,
    bge_threshold: float | None,
    hybrid: bool,
) -> dict[str, float | int]:
    selected = [case for case in cases if case.split == split]
    supported = [case for case in selected if case.expected is not None]
    unsupported = [
        case
        for case in selected
        if case.category == "near_domain_unsupported_operation"
    ]

    correct = 0
    supported_correct = 0
    unsupported_correct = 0
    minilm_accepted = 0
    bge_accepted = 0
    rescued = 0

    for case in selected:
        row = rows_by_id[case.id]
        mini = minilm_scores.get(case.query)
        bge = bge_scores.get(case.query)
        if mini is None:
            predicted = row.predicted
        else:
            baseline_accept = bool(mini and mini[0] >= BASELINE_THRESHOLD)
            minilm_accepted += int(baseline_accept)
            if bge_threshold is None:
                accepted = baseline_accept
            else:
                bge_accept = bool(bge and bge[0] >= bge_threshold)
                bge_accepted += int(bge_accept)
                accepted = (
                    baseline_accept or bge_accept
                    if hybrid
                    else bge_accept
                )
                if hybrid and accepted and not baseline_accept:
                    rescued += 1
            predicted = row.predicted if accepted else None

        is_correct = _correct(case, predicted)
        correct += int(is_correct)
        if case.expected is not None:
            supported_correct += int(is_correct)
        elif case.category == "near_domain_unsupported_operation":
            unsupported_correct += int(is_correct)

    supported_accuracy = supported_correct / len(supported)
    unsupported_rejection = unsupported_correct / len(unsupported)
    return {
        "cases": len(selected),
        "accuracy": correct / len(selected),
        "supported_accuracy": supported_accuracy,
        "near_domain_unsupported_rejection": unsupported_rejection,
        "balanced_operation_score": (
            supported_accuracy + unsupported_rejection
        ) / 2.0,
        "minilm_accepted": minilm_accepted,
        "bge_accepted": bge_accepted,
        "rescued": rescued,
    }


def _metrics_pair(
    cases: list[BenchmarkCase],
    rows_by_id: dict[str, BenchmarkRow],
    minilm_scores: dict[str, list[float]],
    bge_scores: dict[str, list[float]],
    *,
    bge_threshold: float | None,
    hybrid: bool,
) -> dict[str, Any]:
    dev = _split_metrics(
        cases,
        rows_by_id,
        minilm_scores,
        bge_scores,
        split="dev",
        bge_threshold=bge_threshold,
        hybrid=hybrid,
    )
    calibration = _split_metrics(
        cases,
        rows_by_id,
        minilm_scores,
        bge_scores,
        split="calibration",
        bge_threshold=bge_threshold,
        hybrid=hybrid,
    )
    return {
        "dev": dev,
        "calibration": calibration,
        "robustness": min(
            float(dev["balanced_operation_score"]),
            float(calibration["balanced_operation_score"]),
        ),
        "mean_supported_accuracy": (
            float(dev["supported_accuracy"])
            + float(calibration["supported_accuracy"])
        )
        / 2.0,
        "mean_near_domain_rejection": (
            float(dev["near_domain_unsupported_rejection"])
            + float(calibration["near_domain_unsupported_rejection"])
        )
        / 2.0,
    }


async def _profile(corpus: Path, embedding_callable: str) -> dict[str, Any]:
    registry = reference_registry()
    allowed_routes = {
        f"{tool.key}.{endpoint.name}"
        for tool in registry.tools()
        for endpoint in tool.endpoints
    }
    cases = load_corpus(corpus, allowed_routes=allowed_routes)
    embedder = load_callable(
        embedding_callable,
        option_name="--embedding-callable",
    )

    operation = ScoreRecordingEmbeddingDecisionBackend(embedder)
    planner = SchemaPlanner(
        registry,
        candidate_recall_backend=EmbeddingDecisionBackend(embedder),
        candidate_recall_limit=2,
        candidate_fit_backend=EmbeddingDecisionBackend(
            embedder,
            min_similarity=0.25,
        ),
        operation_fit_backend=operation,
        endpoint_disambiguation_backend=EmbeddingDecisionBackend(
            embedder,
            min_margin=0.03,
        ),
    )
    rows = await benchmark_planner(
        "bge-rescue-profile",
        planner,
        cases,
        allowed_routes=allowed_routes,
    )
    rows_by_id = {row.case_id: row for row in rows}
    bge_scores = _bge_scores(operation.requests)

    baseline = _metrics_pair(
        cases,
        rows_by_id,
        operation.similarities,
        bge_scores,
        bge_threshold=None,
        hybrid=True,
    )

    candidates: list[dict[str, Any]] = []
    for threshold in BGE_THRESHOLDS:
        for mode, hybrid in (("bge-only", False), ("minilm-or-bge", True)):
            metrics = _metrics_pair(
                cases,
                rows_by_id,
                operation.similarities,
                bge_scores,
                bge_threshold=threshold,
                hybrid=hybrid,
            )
            dev = metrics["dev"]
            calibration = metrics["calibration"]
            no_supported_regression = (
                float(dev["supported_accuracy"])
                >= float(baseline["dev"]["supported_accuracy"])
                and float(calibration["supported_accuracy"])
                >= float(baseline["calibration"]["supported_accuracy"])
            )
            beats_baseline = float(metrics["robustness"]) > float(
                baseline["robustness"]
            )
            candidates.append(
                {
                    "mode": mode,
                    "bge_threshold": threshold,
                    **metrics,
                    "no_supported_regression": no_supported_regression,
                    "beats_baseline": beats_baseline,
                    "eligible": no_supported_regression and beats_baseline,
                }
            )

    ranked = sorted(
        candidates,
        key=lambda item: (
            not bool(item["eligible"]),
            -float(item["robustness"]),
            -float(item["mean_supported_accuracy"]),
            -float(item["mean_near_domain_rejection"]),
            -float(item["bge_threshold"]),
            str(item["mode"]),
        ),
    )
    for rank, item in enumerate(ranked, start=1):
        item["rank"] = rank

    eligible = [item for item in ranked if item["eligible"]]
    return {
        "corpus": str(corpus),
        "case_count": len(cases),
        "operation_score_count": len(operation.similarities),
        "baseline": {
            "mode": "minilm-only",
            "minilm_threshold": BASELINE_THRESHOLD,
            **baseline,
        },
        "bge_model": BGE_MODEL,
        "bge_thresholds": list(BGE_THRESHOLDS),
        "selection_rule": (
            "candidate must not reduce supported accuracy on either dev or calibration "
            "and must exceed baseline robustness; then maximize robustness, "
            "mean supported accuracy, mean near-domain rejection, higher BGE threshold"
        ),
        "winner": eligible[0] if eligible else None,
        "results": ranked,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--corpus",
        default="benchmarks/decision-routing-v5-operation-calibration.json",
    )
    parser.add_argument(
        "--embedding-callable",
        default="benchmarks.multilingual_embedder:embed",
    )
    parser.add_argument("--json-out", required=True)
    args = parser.parse_args()

    report = asyncio.run(
        _profile(
            Path(args.corpus),
            args.embedding_callable,
        )
    )
    output = Path(args.json_out)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print("baseline", json.dumps(report["baseline"], sort_keys=True))
    print("winner", json.dumps(report["winner"], sort_keys=True))


if __name__ == "__main__":
    main()
