from __future__ import annotations

import argparse
import asyncio
import json
import math
from pathlib import Path
from typing import Any, Iterable

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


GRID: tuple[tuple[float, float], ...] = (
    (0.40, 0.00),
    (0.20, 0.03),
    (0.20, 0.06),
    (0.20, 0.10),
    (0.25, 0.03),
    (0.25, 0.06),
    (0.25, 0.10),
    (0.30, 0.03),
    (0.30, 0.06),
    (0.30, 0.10),
    (0.35, 0.03),
    (0.35, 0.06),
    (0.35, 0.10),
)


def _operation_gate_accepts(
    similarities: list[float],
    *,
    min_similarity: float,
    min_margin: float,
) -> bool:
    eligible = [value for value in similarities if value >= min_similarity]
    if not eligible:
        return False
    if min_margin > 0.0 and len(eligible) > 1:
        if eligible[0] - eligible[1] < min_margin:
            return False
    return True


def _correct(case: BenchmarkCase, predicted: str | None) -> bool:
    return predicted is None if case.expect_abstain else predicted == case.expected


def _split_metrics(
    cases: list[BenchmarkCase],
    rows_by_id: dict[str, BenchmarkRow],
    similarities: dict[str, list[float]],
    *,
    split: str,
    min_similarity: float,
    min_margin: float,
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
            accepted = _operation_gate_accepts(
                scores,
                min_similarity=min_similarity,
                min_margin=min_margin,
            )
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
    balanced = (supported_accuracy + unsupported_rejection) / 2.0
    return {
        "cases": len(selected),
        "accuracy": correct / len(selected),
        "supported_accuracy": supported_accuracy,
        "near_domain_unsupported_rejection": unsupported_rejection,
        "balanced_operation_score": balanced,
        "operation_invoked": operation_invoked,
        "operation_accepted": operation_accepted,
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
    for min_similarity, min_margin in GRID:
        dev = _split_metrics(
            cases,
            rows_by_id,
            operation.similarities,
            split="dev",
            min_similarity=min_similarity,
            min_margin=min_margin,
        )
        calibration = _split_metrics(
            cases,
            rows_by_id,
            operation.similarities,
            split="calibration",
            min_similarity=min_similarity,
            min_margin=min_margin,
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
                "min_similarity": min_similarity,
                "min_margin": min_margin,
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
            -float(item["min_similarity"]),
            -float(item["min_margin"]),
        ),
    )
    for rank, item in enumerate(ranked, start=1):
        item["rank"] = rank

    return {
        "corpus": str(corpus),
        "case_count": len(cases),
        "operation_score_count": len(operation.similarities),
        "selection_rule": (
            "maximize min(dev balanced, calibration balanced); "
            "tie: mean supported, mean near-domain rejection, "
            "higher min_similarity, higher min_margin"
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

    report = asyncio.run(
        _profile(Path(args.corpus), args.embedding_callable)
    )
    output = Path(args.json_out)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    winner = report["winner"]
    print(
        "winner",
        f"similarity={winner['min_similarity']:.2f}",
        f"margin={winner['min_margin']:.2f}",
        f"robustness={winner['robustness']:.6f}",
    )


if __name__ == "__main__":
    main()
