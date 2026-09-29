from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREREG = (
    ROOT
    / "benchmarks"
    / "agent-utility-v4-final-answer-preregistration.json"
)


def _load() -> dict:
    return json.loads(PREREG.read_text(encoding="utf-8"))


def test_final_answer_protocol_is_frozen_but_not_authorized() -> None:
    data = _load()
    authorization = data["run_authorization"]

    assert data["issue"] == 424
    assert data["status"] == (
        "preregistered_protocol_only_no_answer_inference_authorized"
    )
    assert authorization["b1_terminal_required"] is True
    assert authorization["b2_model_choice_frozen_required"] is True
    assert authorization["b2_terminal_result_required"] is True
    assert authorization["current_authorized_to_run"] is False


def test_final_answer_surface_is_balanced_and_independent() -> None:
    data = _load()
    surface = data["surface"]

    assert surface["unique_semantic_tasks"] == 144
    assert len(surface["task_strata"]) == 6
    assert len(surface["languages"]) == 6
    assert surface["cross_balance"] == {
        "tasks_per_stratum": 24,
        "tasks_per_language": 24,
        "tasks_per_stratum_language_cell": 4,
        "cells": 36,
    }
    assert 6 * 6 * 4 == 144
    assert surface["each_task_one_language_only"] is True
    assert surface["prior_b1_b2_wording_or_paraphrase_allowed"] is False
    assert surface["issue_432_heldout_rows_allowed"] is False
    assert surface["final_tasks_tuning_eligible"] is False


def test_final_answer_primary_scoring_is_deterministic() -> None:
    data = _load()
    scoring = data["final_answer_surface"]
    deterministic = data["deterministic_metrics"]

    assert scoring["primary_scoring_requires_machine_readable_envelope"] is True
    assert scoring["malformed_final_envelope_counts_as_answer_failure"] is True
    assert set(scoring["envelope"]["fields"]) == {
        "answer",
        "facts",
        "sources",
    }
    assert set(deterministic) == {
        "required_fact_recall",
        "unsupported_fact_count",
        "unsupported_fact_rate",
        "numeric_value_accuracy",
        "unit_accuracy",
        "provenance_accuracy",
        "contradiction_count",
        "exact_field_completion",
    }


def test_final_answer_gate_preserves_quality_and_context_constraints() -> None:
    data = _load()
    gate = data["primary_success_gate"]

    assert gate["fact_recall_delta_vs_full_min"] == -0.02
    assert gate["numeric_accuracy_delta_vs_full_min"] == -0.02
    assert gate["unit_accuracy_delta_vs_full_min"] == -0.02
    assert gate["provenance_accuracy_delta_vs_full_min"] == -0.02
    assert gate["unsupported_fact_rate_delta_vs_full_max"] == 0.01
    assert gate["required_tool_evidence_coverage_min"] == 0.97
    assert gate["total_input_tokens_must_be_less_than_full"] is True
    assert gate["tool_schema_token_ratio_vs_full_max"] == 0.4
    assert gate["unauthorized_destructive_executions_max"] == 0


def test_final_answer_statistics_cluster_catalog_repeats_by_task() -> None:
    data = _load()
    stats = data["statistics"]
    interval = stats["primary_interval"]

    assert stats["primary_unit"] == "semantic_task_id"
    assert stats["catalog_repeats_nested_within_task"] is True
    assert stats["paired_conditions"] is True
    assert stats["no_pseudoreplication"] is True
    assert stats["no_weighted_composite_score"] is True
    assert interval == {
        "method": "stratified task-cluster bootstrap",
        "strata": "answer_task_stratum x language",
        "iterations": 10000,
        "seed": 20260929,
        "confidence_interval": 0.95,
    }


def test_final_answer_llm_judge_cannot_override_fact_scoring() -> None:
    data = _load()
    secondary = data["secondary_metrics"]

    assert secondary["llm_judge_optional"] is True
    assert secondary["judge_blinded_to_condition"] is True
    assert secondary["deterministic_factual_metrics_remain_primary"] is True
    assert secondary["judge_may_not_override_deterministic_fact_score"] is True
