from __future__ import annotations

import argparse
import asyncio
import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from benchmark_decision_routing import (
    BenchmarkCase,
    BenchmarkRow,
    benchmark_planner,
    load_callable,
    load_corpus,
    reference_registry,
)

from schemarouter import EmbeddingDecisionBackend, SchemaPlanner
from schemarouter.decisions import DecisionRequest, DecisionResult


class ScoreRecordingEmbeddingDecisionBackend(EmbeddingDecisionBackend):
    """Permissive operation gate that records ranked cosine similarities."""

    def __init__(self, embedder: Any) -> None:
        super().__init__(embedder, min_similarity=-1.0, min_margin=0.0)
        self.similarities: dict[str, list[float]] = {}

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
        return super()._result(request, vectors)


BASELINE = (0.40, None, None)
GRID: tuple[tuple[float, float | None, float | None], ...] = (
    BASELINE,
    (0.40, 0.20, 0.05),
    (0.40, 0.20, 0.10),
    (0.40, 0.20, 0.15),
    (0.40, 0.20, 0.20),
    (0.40, 0.25, 0.05),
    (0.40, 0.25, 0.10),
    (0.40, 0.25, 0.15),
    (0.40, 0.25, 0.20),
    (0.40, 0.30, 0.05),
    (0.40, 0.30, 0.10),
    (0.40, 0.30, 0.15),
    (0.40, 0.30, 0.20),
    (0.40, 0.35, 0.05),
    (0.40, 0.35, 0.10),
    (0.40, 0.35, 0.15),
    (0.40, 0.35, 0.20),
)


def _accepts(
    similarities: list[float],
    *,
    baseline_similarity: float,
    rescue_similarity: float | None,
    rescue_margin: float | None,
) -> bool:
    if not similarities:
        return False
    top = similarities[0]
    if top >= baseline_similarity:
        return True
    if rescue_similarity is None or rescue_margin is None:
        return False
    if top < rescue_similarity:
        return False
    margin = top - similarities[1] if len(similarities) > 1 else 2.0
    return margin >= rescue_margin


def _correct(case: BenchmarkCase, predicted: str | None) -> bool:
    return predicted is None if case.expect_abstain else predicted == case.expected


def _split_metrics(
    cases: list[BenchmarkCase],
    rows_by_id: dict[str, BenchmarkRow],
    similarities: dict[str, list[float]],
    *,
    split: str,
    baseline_similarity: float,
    rescue_similarity: float | None,
    rescue_margin: float | None,
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
    rescued = 0

    for case in selected:
        row = rows_by_id[case.id]
        scores = similarities.get(case.query)
        if scores is None:
            predicted = row.predicted
        else:
            operation_invoked += 1
            baseline_accept = bool(scores and scores[0] >= baseline_similarity)
            accepted = _accepts(
                scores,
                baseline_similarity=baseline_similarity,
                rescue_similarity=rescue_similarity,
                rescue_margin=rescue_margin,
            )
            if accepted:
                operation_accepted += 1
                if not baseline_accept:
                    rescued += 1
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
        "rescued": rescued,
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
        "permissive-operation-profile",
        planner,
        cases,
        allowed_routes=allowed_routes,
    )
    rows_by_id = {row.case_id: row for row in rows}

    results: list[dict[str, Any]] = []
    for baseline_similarity, rescue_similarity, rescue_margin in GRID:
        dev = _split_metrics(
            cases,
            rows_by_id,
            operation.similarities,
            split="dev",
            baseline_similarity=baseline_similarity,
            rescue_similarity=rescue_similarity,
            rescue_margin=rescue_margin,
        )
        calibration = _split_metrics(
            cases,
            rows_by_id,
            operation.similarities,
            split="calibration",
            baseline_similarity=baseline_similarity,
            rescue_similarity=rescue_similarity,
            rescue_margin=rescue_margin,
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
        results.append(
            {
                "baseline_similarity": baseline_similarity,
                "rescue_similarity": rescue_similarity,
                "rescue_margin": rescue_margin,
                "dev": dev,
                "calibration": calibration,
                "robustness": robustness,
                "mean_supported_accuracy": mean_supported,
                "mean_near_domain_rejection": mean_rejection,
            }
        )

    ranked = sorted(
        results,
        key=lambda item: (
            -float(item["robustness"]),
            -float(item["mean_supported_accuracy"]),
            -float(item["mean_near_domain_rejection"]),
            -(float(item["rescue_similarity"]) if item["rescue_similarity"] is not None else 1.0),
            -(float(item["rescue_margin"]) if item["rescue_margin"] is not None else 1.0),
        ),
    )
    for rank, item in enumerate(ranked, start=1):
        item["rank"] = rank

    return {
        "corpus": str(corpus),
        "case_count": len(cases),
        "operation_score_count": len(operation.similarities),
        "rule": (
            "accept top>=0.40 OR "
            "(top>=rescue_similarity AND top-second>=rescue_margin)"
        ),
        "selection_rule": (
            "maximize min(dev balanced, calibration balanced); "
            "tie: mean supported, mean near-domain rejection, "
            "more conservative rescue_similarity, then rescue_margin"
        ),
        "results": ranked,
        "winner": ranked[0],
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
    report = asyncio.run(_profile(Path(args.corpus), args.embedding_callable))
    output = Path(args.json_out)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report["winner"], sort_keys=True))


if __name__ == "__main__":
    main()
