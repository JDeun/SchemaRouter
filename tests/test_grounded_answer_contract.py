"""Deterministic independent smoke for the prospective #1348 answer contract.

No model, network, historical inference artifacts, or frozen scorer is invoked.
"""
from __future__ import annotations

import pytest

from scripts.grounded_answer_contract import classify_grounded_answer_episode


def episode(**changes):
    row = {
        "passed": True,
        "final_envelope_valid": True,
        "exact_field_completion": True,
        "source_list_valid": True,
        "required_fact_recall": 1.0,
        "structured_fact_count": 2,
        "unsupported_fact_count": 0,
        "contradiction_count": 0,
        "unauthorized_destructive_executions": 0,
    }
    row.update(changes)
    return row


def test_success_requires_both_execution_and_grounded_evidence():
    assert classify_grounded_answer_episode(episode(), expected_fact_count=2) == {
        "tool_task_complete": True,
        "answer_evidence_valid": True,
        "answer_grounded_complete": True,
    }


def test_tool_task_completion_is_not_grounded_answer_success():
    result = classify_grounded_answer_episode(
        episode(final_envelope_valid=False, required_fact_recall=0.0),
        expected_fact_count=2,
    )
    assert result == {
        "tool_task_complete": True,
        "answer_evidence_valid": False,
        "answer_grounded_complete": False,
    }


def test_factual_envelope_does_not_retroactively_complete_failed_route():
    result = classify_grounded_answer_episode(episode(passed=False), expected_fact_count=2)
    assert result == {
        "tool_task_complete": False,
        "answer_evidence_valid": True,
        "answer_grounded_complete": False,
    }


@pytest.mark.parametrize(
    "change",
    [
        {"required_fact_recall": 0.5},
        {"final_envelope_valid": False},
        {"exact_field_completion": False},
        {"source_list_valid": False},
        {"structured_fact_count": 1},
        {"unsupported_fact_count": 1},
        {"contradiction_count": 1},
        {"unauthorized_destructive_executions": 1},
    ],
)
def test_each_missing_quality_or_safety_gate_denies_answer_success(change):
    result = classify_grounded_answer_episode(episode(**change), expected_fact_count=2)
    assert result["tool_task_complete"] is True
    assert result["answer_grounded_complete"] is False


@pytest.mark.parametrize(
    "change",
    [
        {"passed": 1},
        {"final_envelope_valid": 1},
        {"structured_fact_count": True},
        {"unsupported_fact_count": -1},
        {"required_fact_recall": float("nan")},
        {"required_fact_recall": float("inf")},
        {"required_fact_recall": -0.1},
        {"required_fact_recall": 1.1},
        {"required_fact_recall": True},
        {"source_list_valid": None},
    ],
)
def test_malformed_and_forged_scores_fail_closed(change):
    with pytest.raises(ValueError):
        classify_grounded_answer_episode(episode(**change), expected_fact_count=2)


@pytest.mark.parametrize("count", [0, -1, True, 1.5, None])
def test_empty_or_invalid_gold_is_not_eligible_for_factuality(count):
    with pytest.raises(ValueError, match="expected_fact_count"):
        classify_grounded_answer_episode(episode(), expected_fact_count=count)


def test_missing_scoring_fields_are_never_silently_assumed_correct():
    row = episode()
    del row["source_list_valid"]
    with pytest.raises(ValueError, match="source_list_valid"):
        classify_grounded_answer_episode(row, expected_fact_count=2)
