from __future__ import annotations

from scripts.evaluate_adaptive_context_agent_utility_dev import evaluate


def test_adaptive_context_agent_utility_dev_is_bounded_and_unclaimed() -> None:
    result = evaluate()
    metrics = result["metrics"]

    assert result["performance_evidence"] is False
    assert result["status"] == "development_scored"
    assert len(result["rows"]) == 23
    assert 0.0 <= metrics["required_route_recall"] <= 1.0
    assert 0.0 <= metrics["required_field_recall"] <= 1.0
    assert 0.0 <= metrics["task_success_proxy"] <= 1.0
    assert metrics["session_unique_schema_candidate_exposures"] <= (
        metrics["stateless_schema_candidate_exposures"]
    )
    assert 0.0 <= metrics["session_context_ratio_vs_stateless"] <= 1.0
    assert metrics["unsupported_rejection"] is None
