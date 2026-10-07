import json
from pathlib import Path


MANIFEST = Path("benchmarks/adaptive-context-confirmation-v1/manifest.json")


def test_adaptive_confirmation_protocol_is_frozen_unscored() -> None:
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert data["status"] == "protocol_frozen_unscored"
    assert data["development_results_tuning_eligible"] is False
    assert data["configuration"]["prior_weight"] == 0.5
    assert data["corpus_contract"]["must_be_created_after_this_protocol_is_merged"]
    assert data["corpus_contract"]["must_not_reuse_development_queries"]
    assert data["corpus_contract"]["minimum_tasks"] >= 100
    assert data["corpus_contract"]["one_shot"]
    assert data["promotion_gate"]["required_tool_recall_regression_max_pp"] == 0.0
    assert data["promotion_gate"]["unsupported_rejection_regression_max_pp"] == 0.0
    assert data["promotion_gate"]["oracle_execution_completion_regression_max_pp"] == 0.0
    assert data["promotion_gate"]["session_schema_context_reduction_min_fraction"] == 0.1
    assert data["guardrails"]["post_freeze_semantic_tuning_allowed"] is False
    assert data["guardrails"]["default_enablement_before_gate_pass_allowed"] is False
    assert data["evidence"]["scored"] is False
    assert data["evidence"]["performance_claims_allowed"] is False
