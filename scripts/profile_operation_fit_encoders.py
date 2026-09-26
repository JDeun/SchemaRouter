from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from benchmark_decision_routing import (
    BenchmarkCase,
    BenchmarkRow,
    benchmark_planner,
    load_corpus,
    reference_registry,
)

from schemarouter import EmbeddingDecisionBackend, SchemaPlanner
from schemarouter.decisions import DecisionOption, DecisionRequest, DecisionResult, DecisionSelection


@dataclass(frozen=True)
class EncoderSpec:
    key: str
    model_name: str
    mode: str


ENCODERS: tuple[EncoderSpec, ...] = (
    EncoderSpec(
        key="minilm-raw",
        model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        mode="raw",
    ),
    EncoderSpec(
        key="e5-small-query-passage",
        model_name="intfloat/multilingual-e5-small",
        mode="e5-query-passage",
    ),
    EncoderSpec(
        key="mpnet-multilingual-raw",
        model_name="sentence-transformers/paraphrase-multilingual-mpnet-base-v2",
        mode="raw",
    ),
)

THRESHOLDS: tuple[float, ...] = tuple(index / 100.0 for index in range(100))


class SentenceTransformerEmbedder:
    def __init__(self, model_name: str) -> None:
        from sentence_transformers import SentenceTransformer

        self.model_name = model_name
        self.model = SentenceTransformer(model_name)

    def __call__(self, texts: list[str]) -> list[list[float]]:
        vectors = self.model.encode(
            texts,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return vectors.tolist()


class OperationRequestRecorder:
    """Accept every authorized operation request while recording its exact fit surface."""

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


def _option_text(option: DecisionOption) -> str:
    label = option.label.strip() or option.id
    description = option.description.strip()
    return f"{label}\n{description}" if description else label


def _profile_texts(
    request: DecisionRequest,
    *,
    mode: str,
) -> list[str]:
    query = request.query
    options = [_option_text(option) for option in request.options]
    if mode == "e5-query-passage":
        return [
            f"query: {query}",
            *(f"passage: {option}" for option in options),
        ]
    return [query, *options]


def _batched_operation_scores(
    requests: dict[str, DecisionRequest],
    *,
    spec: EncoderSpec,
    existing_model: Any | None = None,
) -> dict[str, list[float]]:
    if existing_model is None:
        from sentence_transformers import SentenceTransformer

        model = SentenceTransformer(spec.model_name)
    else:
        model = existing_model

    flattened: list[str] = []
    spans: dict[str, tuple[int, int]] = {}
    for query, request in requests.items():
        start = len(flattened)
        payload = _profile_texts(request, mode=spec.mode)
        flattened.extend(payload)
        spans[query] = (start, len(payload))

    vectors = model.encode(
        flattened,
        batch_size=64,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
    ).tolist()

    scores: dict[str, list[float]] = {}
    for query, (start, length) in spans.items():
        query_vector = vectors[start]
        option_vectors = vectors[start + 1 : start + length]
        similarities = [
            sum(a * b for a, b in zip(query_vector, vector, strict=True))
            for vector in option_vectors
        ]
        scores[query] = sorted(similarities, reverse=True)
    return scores


def _correct(case: BenchmarkCase, predicted: str | None) -> bool:
    return predicted is None if case.expect_abstain else predicted == case.expected


def _split_metrics(
    cases: list[BenchmarkCase],
    rows_by_id: dict[str, BenchmarkRow],
    similarities: dict[str, list[float]],
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
        scores = similarities.get(case.query)
        if scores is None:
            predicted = row.predicted
        else:
            operation_invoked += 1
            accepted = bool(scores and scores[0] >= threshold)
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
    similarities: dict[str, list[float]],
    *,
    encoder: EncoderSpec,
    threshold: float,
) -> dict[str, Any]:
    dev = _split_metrics(
        cases,
        rows_by_id,
        similarities,
        split="dev",
        threshold=threshold,
    )
    calibration = _split_metrics(
        cases,
        rows_by_id,
        similarities,
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
        "encoder": encoder.key,
        "model_name": encoder.model_name,
        "mode": encoder.mode,
        "threshold": threshold,
        "dev": dev,
        "calibration": calibration,
        "robustness": robustness,
        "mean_supported_accuracy": mean_supported,
        "mean_near_domain_rejection": mean_rejection,
    }


async def _profile(corpus: Path) -> dict[str, Any]:
    registry = reference_registry()
    allowed_routes = {
        f"{tool.key}.{endpoint.name}"
        for tool in registry.tools()
        for endpoint in tool.endpoints
    }
    cases = load_corpus(corpus, allowed_routes=allowed_routes)

    upstream = SentenceTransformerEmbedder(ENCODERS[0].model_name)
    operation = OperationRequestRecorder()
    planner = SchemaPlanner(
        registry,
        candidate_recall_backend=EmbeddingDecisionBackend(upstream),
        candidate_recall_limit=2,
        candidate_fit_backend=EmbeddingDecisionBackend(
            upstream,
            min_similarity=0.25,
        ),
        operation_fit_backend=operation,
        endpoint_disambiguation_backend=EmbeddingDecisionBackend(
            upstream,
            min_margin=0.03,
        ),
    )
    rows = await benchmark_planner(
        "operation-encoder-profile",
        planner,
        cases,
        allowed_routes=allowed_routes,
    )
    rows_by_id = {row.case_id: row for row in rows}

    scores_by_encoder: dict[str, dict[str, list[float]]] = {}
    for spec in ENCODERS:
        scores_by_encoder[spec.key] = _batched_operation_scores(
            operation.requests,
            spec=spec,
            existing_model=upstream.model if spec.key == "minilm-raw" else None,
        )

    results: list[dict[str, Any]] = []
    per_encoder_winners: dict[str, dict[str, Any]] = {}
    for spec in ENCODERS:
        scores = scores_by_encoder[spec.key]
        candidates = [
            _candidate(
                cases,
                rows_by_id,
                scores,
                encoder=spec,
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
        per_encoder_winners[spec.key] = ranked[0]
        results.extend(candidates)

    encoder_order = {spec.key: index for index, spec in enumerate(ENCODERS)}
    ranked_results = sorted(
        results,
        key=lambda item: (
            -float(item["robustness"]),
            -float(item["mean_supported_accuracy"]),
            -float(item["mean_near_domain_rejection"]),
            -float(item["threshold"]),
            encoder_order[str(item["encoder"])],
        ),
    )
    for rank, item in enumerate(ranked_results, start=1):
        item["rank"] = rank

    return {
        "corpus": str(corpus),
        "case_count": len(cases),
        "operation_request_count": len(operation.requests),
        "encoders": [
            {
                "key": spec.key,
                "model_name": spec.model_name,
                "mode": spec.mode,
            }
            for spec in ENCODERS
        ],
        "threshold_grid": {
            "min": THRESHOLDS[0],
            "max": THRESHOLDS[-1],
            "step": 0.01,
        },
        "selection_rule": (
            "maximize min(dev balanced, calibration balanced); "
            "tie: mean supported, mean near-domain rejection, "
            "higher threshold, stable encoder declaration order"
        ),
        "per_encoder_winners": per_encoder_winners,
        "winner": ranked_results[0],
        "results": ranked_results,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--corpus",
        default="benchmarks/decision-routing-v5-operation-calibration.json",
    )
    parser.add_argument("--json-out", required=True)
    args = parser.parse_args()

    report = asyncio.run(_profile(Path(args.corpus)))
    output = Path(args.json_out)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report["per_encoder_winners"], sort_keys=True))
    print(json.dumps(report["winner"], sort_keys=True))


if __name__ == "__main__":
    main()
