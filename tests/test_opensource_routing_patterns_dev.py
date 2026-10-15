"""Offline route-selection contract tests; these are not model quality tests."""
from __future__ import annotations

import copy
from pathlib import Path

import pytest

from scripts.evaluate_opensource_routing_patterns_dev import (
    CROSS_ENCODER,
    EXEMPLARS,
    RETRIEVE_THRESHOLD,
    ROUTE_MARGIN,
    ROUTE_THRESHOLD,
    SOURCE_SHA256,
    TOP_K,
    bounded_rerank,
    choose_exemplar_route,
    summary,
)
from scripts.evaluate_operation_intent_cpu_dev import DESCRIPTIONS, load_corpus

CORPUS = (
    Path(__file__).resolve().parents[1]
    / "benchmarks/operation-intent-trilingual-dev-20261015.json"
)


def test_frozen_dev_corpus_and_exemplar_identity() -> None:
    corpus, sha = load_corpus(CORPUS)
    assert sha == SOURCE_SHA256
    assert len(corpus["cases"]) == 72
    assert len(EXEMPLARS) == len(DESCRIPTIONS) == 9
    assert list(EXEMPLARS) == list(DESCRIPTIONS)
    assert all(len(x) == 3 for x in EXEMPLARS.values())
    assert TOP_K == 3
    assert ROUTE_THRESHOLD == RETRIEVE_THRESHOLD == 0.65
    assert ROUTE_MARGIN == 0.03
    assert CROSS_ENCODER == "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"


def test_prototype_rejects_weak_and_ambiguous_and_accepts_clear() -> None:
    scores = {"search": 0.81, "delete": 0.33, "history": 0.13}
    assert choose_exemplar_route(scores, threshold=0.65, margin=0.03) == "search"
    assert choose_exemplar_route(
        {"search": 0.64, "delete": 0.11}, threshold=0.65, margin=0.03
    ) is None
    assert choose_exemplar_route(
        {"search": 0.69, "delete": 0.68}, threshold=0.65, margin=0.03
    ) is None
    with pytest.raises(ValueError, match="finite"):
        choose_exemplar_route({"search": float("nan")}, threshold=0.65, margin=0.03)


def test_cross_encoder_is_bounded_to_retrieved_three_and_score_gate() -> None:
    retrieved = [("search", 0.72), ("delete", 0.61), ("lookup", 0.64)]
    cross_scores = [-9.0, 8.0, 0.0]
    assert bounded_rerank(retrieved, cross_scores, gate=False) == "delete"
    assert bounded_rerank(retrieved, cross_scores, gate=True) is None
    assert bounded_rerank(
        retrieved, [-1.0, -3.0, -2.0], gate=True
    ) == "search"
    assert bounded_rerank(
        [("search", 0.5)], [0.1], gate=True,
    ) is None


@pytest.mark.parametrize(
    ("candidates", "scores"),
    [
        ([], []),
        ([("a", 0.1)], []),
        ([("a", 0.1), ("a", 0.2)], [1.0, 0.0]),
        ([("a", float("nan"))], [0.2]),
        ([("a", 0.5)], [float("inf")]),
    ],
)
def test_bounded_reranker_fails_on_invalid_inputs(
    candidates: list[tuple[str, float]], scores: list[float],
) -> None:
    with pytest.raises(ValueError):
        bounded_rerank(candidates, scores, gate=True)


def test_metrics_keep_supported_and_unsupported_disjoint() -> None:
    template = {
        "language": "ko", "kind": "supported",
        "expected_operation": "lookup", "latency_ms": 10.0,
    }
    rows = [
        {**template, "prediction": "lookup"},
        {**template, "prediction": "delete"},
        {**template, "prediction": None},
        {**template, "kind": "unsupported", "expected_operation": None,
         "prediction": "delete"},
        {**template, "kind": "unsupported", "expected_operation": None,
         "prediction": None},
    ]
    metrics = summary(rows, "arm")["overall"]
    assert metrics["correct_supported"] == 1
    assert metrics["wrong_supported"] == 1
    assert metrics["false_refusal_supported"] == 1
    assert metrics["false_accept_unsupported"] == 1
    assert metrics["supported"] == 3
    assert metrics["unsupported"] == 2
    assert summary(copy.deepcopy(rows), "arm")["languages"]["ko"] == metrics
