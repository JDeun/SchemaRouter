from scripts.evaluate_adaptive_context_unsupported_dev import evaluate


def test_adaptive_prior_preserves_frozen_unsupported_rejection() -> None:
    result = evaluate()
    assert result["performance_evidence"] is False
    assert result["unsupported_cases"] == 4
    assert result["metrics"]["stateless_unsupported_rejection"] == 1.0
    assert result["metrics"]["adaptive_unsupported_rejection"] == 1.0
    assert all(not row["adaptive_candidates"] for row in result["rows"])
