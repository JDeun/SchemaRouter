from scripts.evaluate_adaptive_context_execution_dev import evaluate


def test_execution_oracle_development_contract() -> None:
    result = evaluate()
    assert result["status"] == "development_scored"
    assert result["performance_evidence"] is False
    assert len(result["rows"]) == 23
    for row in result["rows"]:
        if row["retrieval_covered"]:
            assert row["oracle_execution_complete"]
            assert not row["errors"]
