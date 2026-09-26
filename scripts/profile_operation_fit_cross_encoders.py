from __future__ import annotations

import argparse
import asyncio
import gc
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

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
from schemarouter.decisions import (
    DecisionRequest,
    DecisionResult,
    DecisionSelection,
)


@dataclass(frozen=True)
class RerankerSpec:
    key: str
    model_name: str
    batch_size: int


RERANKERS: tuple[RerankerSpec, ...] = (
    RerankerSpec(
        key="mmarco-minilm-cross-encoder",
        model_name="cross-encoder/mmarco-mMiniLMv2-L12-H384-v1",
        batch_size=24,
    ),
    RerankerSpec(
        key="bge-reranker-v2-m3",
        model_name="BAAI/bge-reranker-v2-m3",
        batch_size=8,
    ),
)

THRESHOLDS: tuple[float, ...] = tuple(index / 100.0 for index in range(101))
BASELINE_ROBUSTNESS = 0.6979166666666666


class RecordingOperationBackend:
    """Accept every reached operation request while recording its bounded options."""

    def __init__(self) -> None:
        self.requests: dict[str, DecisionRequest] = {}

    def decide(self, request: DecisionRequest) -> DecisionResult:
        self.requests[request.query] = request
        return DecisionResult(
            selections=[
                DecisionSelection(
                    option_id=request.options[0].id,
                    score=1.0,
                )
            ],
            metadata={"provider": "operation-request-recorder"},
        )


def _option_text(option: Any) -> str:
    label = option.label.strip() or option.id
    description = option.description.strip()
    return f"{label}\n{description}" if description else label


def _score_requests(
    spec: RerankerSpec,
    requests: dict[str, DecisionRequest],
) -> dict[str, list[float]]:
    tokenizer = AutoTokenizer.from_pretrained(spec.model_name)
    model = AutoModelForSequenceClassification.from_pretrained(spec.model_name)
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
        for start in range(0, len(pair_queries), spec.batch_size):
            end = min(start + spec.batch_size, len(pair_queries))
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
                    f"{spec.model_name} returned {flattened.shape[1]} logits per pair"
                )
            batch = torch.sigmoid(flattened[:, 0].float()).cpu().tolist()
            probabilities.extend(float(value) for value in batch)

    result = {
        query: sorted(probabilities[start:end], reverse=True)
        for query, start, end in spans
    }

    del model
    del tokenizer
    gc.collect()
    return result


def _correct(case: BenchmarkCase, predicted: str | None) -> bool:
    return predicted is None if case.expect_abstain else predicted == case.expected


def _split_metrics(
    cases: list[BenchmarkCase],
    rows_by_id: dict[str, BenchmarkRow],
    scores: dict[str, list[float]],
    *,
    split: str,
    threshold: float,
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
    operation_invoked = 0
    operation_accepted = 0

    for case in selected:
        row = rows_by_id[case.id]
        pair_scores = scores.get(case.query)
        if pair_scores is None:
            predicted = row.predicted
        else:
            operation_invoked += 1
            accepted = bool(pair_scores and pair_scores[0] >= threshold)
            if accepted:
                operation_accepted += 1
                predicted = row.predicted
            else:
                predicted = None

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
        "operation_invoked": operation_invoked,
        "operation_accepted": operation_accepted,
    }


def _candidate(
    cases: list[BenchmarkCase],
    rows_by_id: dict[str, BenchmarkRow],
    scores: dict[str, list[float]],
    *,
    spec: RerankerSpec,
    threshold: float,
) -> dict[str, Any]:
    dev = _split_metrics(
        cases,
        rows_by_id,
        scores,
        split="dev",
        threshold=threshold,
    )
    calibration = _split_metrics(
        cases,
        rows_by_id,
        scores,
        split="calibration",
        threshold=threshold,
    )
    robustness = min(
        float(dev["balanced_operation_score"]),
        float(calibration["balanced_operation_score"]),
    )
    mean_supported = (
        float(dev["supported_accuracy"])
        + float(calibration["supported_accuracy"])
    ) / 2.0
    mean_rejection = (
        float(dev["near_domain_unsupported_rejection"])
        + float(calibration["near_domain_unsupported_rejection"])
    ) / 2.0
    return {
        "reranker": spec.key,
        "model_name": spec.model_name,
        "threshold": threshold,
        "dev": dev,
        "calibration": calibration,
        "robustness": robustness,
        "mean_supported_accuracy": mean_supported,
        "mean_near_domain_rejection": mean_rejection,
    }


async def _profile(corpus: Path, upstream_embedding_callable: str) -> dict[str, Any]:
    registry = reference_registry()
    allowed_routes = {
        f"{tool.key}.{endpoint.name}"
        for tool in registry.tools()
        for endpoint in tool.endpoints
    }
    cases = load_corpus(corpus, allowed_routes=allowed_routes)
    upstream = load_callable(
        upstream_embedding_callable,
        option_name="--upstream-embedding-callable",
    )

    recorder = RecordingOperationBackend()
    planner = SchemaPlanner(
        registry,
        candidate_recall_backend=EmbeddingDecisionBackend(upstream),
        candidate_recall_limit=2,
        candidate_fit_backend=EmbeddingDecisionBackend(
            upstream,
            min_similarity=0.25,
        ),
        operation_fit_backend=recorder,
        endpoint_disambiguation_backend=EmbeddingDecisionBackend(
            upstream,
            min_margin=0.03,
        ),
    )
    rows = await benchmark_planner(
        "cross-encoder-operation-profile",
        planner,
        cases,
        allowed_routes=allowed_routes,
    )
    rows_by_id = {row.case_id: row for row in rows}

    results: list[dict[str, Any]] = []
    per_reranker_winners: dict[str, dict[str, Any]] = {}
    for spec in RERANKERS:
        scores = _score_requests(spec, recorder.requests)
        candidates = [
            _candidate(
                cases,
                rows_by_id,
                scores,
                spec=spec,
                threshold=threshold,
            )
            for threshold in THRESHOLDS
        ]
        ranked = sorted(
            candidates,
            key=lambda item: (
                -float(item["robustness"]),
                -float(item["mean_supported_accuracy"]),
                -float(item["mean_near_domain_rejection"]),
                -float(item["threshold"]),
            ),
        )
        per_reranker_winners[spec.key] = ranked[0]
        results.extend(candidates)

    order = {spec.key: index for index, spec in enumerate(RERANKERS)}
    ranked_results = sorted(
        results,
        key=lambda item: (
            -float(item["robustness"]),
            -float(item["mean_supported_accuracy"]),
            -float(item["mean_near_domain_rejection"]),
            -float(item["threshold"]),
            order[str(item["reranker"])],
        ),
    )
    for rank, item in enumerate(ranked_results, start=1):
        item["rank"] = rank

    winner = ranked_results[0]
    return {
        "corpus": str(corpus),
        "case_count": len(cases),
        "operation_request_count": len(recorder.requests),
        "baseline": {
            "method": "MiniLM bi-encoder cosine",
            "robustness": BASELINE_ROBUSTNESS,
            "source": "v5 dev/cal encoder comparison",
        },
        "rerankers": [
            {
                "key": spec.key,
                "model_name": spec.model_name,
                "batch_size": spec.batch_size,
            }
            for spec in RERANKERS
        ],
        "threshold_grid": {
            "min": THRESHOLDS[0],
            "max": THRESHOLDS[-1],
            "step": 0.01,
        },
        "selection_rule": (
            "maximize min(dev balanced, calibration balanced); "
            "tie: mean supported, mean near-domain rejection, "
            "higher threshold, stable reranker declaration order"
        ),
        "beats_baseline": float(winner["robustness"]) > BASELINE_ROBUSTNESS,
        "per_reranker_winners": per_reranker_winners,
        "winner": winner,
        "results": ranked_results,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--corpus",
        default="benchmarks/decision-routing-v5-operation-calibration.json",
    )
    parser.add_argument(
        "--upstream-embedding-callable",
        default="benchmarks.multilingual_embedder:embed",
    )
    parser.add_argument("--json-out", required=True)
    args = parser.parse_args()

    report = asyncio.run(
        _profile(
            Path(args.corpus),
            args.upstream_embedding_callable,
        )
    )
    output = Path(args.json_out)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report["per_reranker_winners"], sort_keys=True))
    print(json.dumps(report["winner"], sort_keys=True))
    print("beats_baseline", report["beats_baseline"])


if __name__ == "__main__":
    main()
