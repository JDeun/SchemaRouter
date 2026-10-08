from scripts.benchmark_evidence_to_action import score


def test_evidence_to_action_metrics_are_deterministic() -> None:
    metrics = score(
        [
            {
                "premature_action": False,
                "evidence_complete_action": True,
                "unsupported_action": False,
                "exact_action_success": True,
                "provenance_correct": True,
                "argument_schema_valid": True,
                "route_field_exact": True,
                "false_refusal": False,
            },
            {
                "premature_action": True,
                "evidence_complete_action": False,
                "unsupported_action": True,
                "exact_action_success": False,
                "provenance_correct": False,
                "argument_schema_valid": True,
                "route_field_exact": False,
                "false_refusal": False,
            },
        ]
    )

    assert metrics["premature_action_rate"] == 0.5
    assert metrics["evidence_complete_action_rate"] == 0.5
    assert metrics["argument_schema_validity"] == 1.0
    assert metrics["false_refusal_rate"] == 0.0
