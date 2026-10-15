"""Offline contract tests: mocked native Laya is NEVER a quality result."""
from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import pytest

from scripts.evaluate_laya_operation_intent_cpu_dev import (
    LAYA_VERSION,
    NOUL_RESEARCH_THRESHOLD,
    SOURCE_SHA256,
    evaluate_with_router,
    parse_native_pair,
    safe_probability,
)
from scripts.evaluate_operation_intent_cpu_dev import load_corpus

CORPUS = (
    Path(__file__).resolve().parents[1]
    / "benchmarks/operation-intent-trilingual-dev-20261015.json"
)


class FakeLayaRouter:
    """Fake responses only test parsing and metrics, never model capability."""

    def __init__(self, labels: dict[str, tuple[str, float]]) -> None:
        self.labels = labels
        self.queries: list[tuple[dict[str, Any], dict[str, Any]]] = []

    def predict(
        self, state: dict[str, Any], questions: dict[str, Any], **kwargs: Any,
    ) -> dict[str, Any]:
        self.queries.append((state, questions))
        operation, probability = self.labels[state["query"]]
        answers: dict[str, Any] = {
            "selection": {
                "type": "choice", "choice": operation, "confidence": 0.8,
            },
        }
        if "one_action" in questions:
            assert questions["one_action"]["type"] == "noul"
            answers["one_action"] = {"type": "noul", "noul": probability}
        return {
            "answers": answers,
            "routing": {"model": "fake-no-weights"},
        }


def test_preregistered_protocol_matches_previous_corpus() -> None:
    corpus, digest = load_corpus(CORPUS)
    assert digest == SOURCE_SHA256
    assert len(corpus["cases"]) == 72
    assert LAYA_VERSION == "0.4.7"
    assert NOUL_RESEARCH_THRESHOLD == 0.5


def test_mock_two_arm_scoring_does_not_dispatch_or_create_policy() -> None:
    corpus, _ = load_corpus(CORPUS)
    values = {
        case["query"]: (
            case["expected_operation"] if case["kind"] == "supported"
            else "search",
            1.0 if case["kind"] == "supported" else 0.0,
        )
        for case in corpus["cases"]
    }
    stub = FakeLayaRouter(values)
    report = evaluate_with_router(stub, corpus)
    assert len(stub.queries) == 144
    assert len(report["choice"]["rows"]) == 72
    assert len(report["choice_plus_noul"]["rows"]) == 72
    first = report["choice"]["summary"]["overall"]
    second = report["choice_plus_noul"]["summary"]["overall"]
    assert first["correct_supported_rate"] == 1.0
    assert first["unsupported_false_accept_rate"] == 1.0
    assert second["correct_supported_rate"] == 1.0
    assert second["unsupported_false_accept_rate"] == 0.0
    for state, questions in stub.queries:
        assert "query" in state
        assert questions["selection"]["type"] == "choice"
        assert set(questions) in ({"selection"}, {"selection", "one_action"})


@pytest.mark.parametrize(
    "bad",
    [None, True, False, "0.5", float("nan"), float("inf"), -0.01, 1.01],
)
def test_native_probability_rejects_non_numeric_or_nonfinite(bad: Any) -> None:
    with pytest.raises(ValueError, match="native Laya"):
        safe_probability(bad, "noul")


@pytest.mark.parametrize(
    "changed",
    [
        {"answers": {}},
        {"answers": {"selection": {"type": "noul"}}},
        {"answers": {
            "selection": {"type": "choice", "choice": "delete", "confidence": 0.8},
            "one_action": {"type": "choice", "noul": 0.9},
        }},
        {"answers": {
            "selection": {"type": "choice", "choice": "arbitrary", "confidence": 0.8},
            "one_action": {"type": "noul", "noul": 0.9},
        }},
        {"answers": {
            "selection": {"type": "choice", "choice": "search", "confidence": True},
            "one_action": {"type": "noul", "noul": 0.9},
        }},
        {"answers": {
            "selection": {"type": "choice", "choice": "search", "confidence": 0.8},
            "one_action": {"type": "noul", "noul": float("nan")},
        }},
    ],
)
def test_invalid_native_responses_fail_without_score(changed: Any) -> None:
    with pytest.raises(ValueError):
        parse_native_pair(changed, {"search", "delete"})


def test_pair_outcome_preserves_raw_choice_and_veto_abstention() -> None:
    corpus, _ = load_corpus(CORPUS)
    subset = copy.deepcopy(corpus)
    subset["cases"] = [
        next(x for x in corpus["cases"] if x["kind"] == "supported"),
        next(x for x in corpus["cases"] if x["kind"] == "unsupported"),
    ]
    stub = FakeLayaRouter({
        subset["cases"][0]["query"]: ("search", 0.0),
        subset["cases"][1]["query"]: ("delete", 1.0),
    })
    # This scenario deliberately models BOTH possible safety failures.
    summary = evaluate_with_router(stub, subset)["choice_plus_noul"]["summary"]["overall"]
    assert summary["supported_false_refusal_rate"] == 1.0
    assert summary["unsupported_false_accept_rate"] == 1.0
