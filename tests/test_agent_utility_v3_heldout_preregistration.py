from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREREG = ROOT / "benchmarks" / "agent-utility-v3-heldout-preregistration.json"


def _load() -> dict:
    return json.loads(PREREG.read_text(encoding="utf-8"))


def test_heldout_surface_is_independent_and_balanced() -> None:
    data = _load()
    surface = data["heldout_surface"]
    independence = data["independence"]

    assert data["issue"] == 432
    assert surface["unique_semantic_tasks"] == 780
    assert len(surface["task_strata"]) == 13
    assert len(surface["languages"]) == 6
    assert surface["cross_balance"] == {
        "semantic_tasks_per_task_stratum": 60,
        "semantic_tasks_per_language": 130,
        "semantic_tasks_per_stratum_language_cell": 10,
        "cells": 78,
    }
    assert 13 * 6 * 10 == 780
    assert surface["final_heldout_tuning_eligible"] is False

    assert independence["b1_row_content_allowed"] is False
    assert independence["b1_failure_tuning_allowed"] is False
    assert independence["b2_row_content_allowed"] is False
    assert independence["b2_failure_tuning_allowed"] is False
    assert independence["representation_dev_434_queries_allowed"] is False
    assert independence["paraphrases_of_prior_benchmark_rows_allowed"] is False


def test_heldout_catalog_and_condition_plan_is_frozen() -> None:
    data = _load()
    scaling = data["catalog_scaling"]
    conditions = data["conditions"]

    assert scaling["retrieval_catalog_endpoint_counts"] == [100, 250, 500, 1000]
    assert scaling["downstream_agent_catalog_endpoint_counts"] == [100, 250, 500]
    assert scaling["catalog_repeat_is_independent_sample"] is False
    assert conditions["required"] == [
        "FULL",
        "SR-5",
        "SR-10",
        "SR-PROGRESSIVE",
        "ORACLE",
    ]
    assert conditions["rank_scores_visible_to_agent"] is False
    assert conditions["rank_positions_visible_to_agent"] is False


def test_heldout_statistics_do_not_pseudoreplicate_catalog_repeats() -> None:
    data = _load()
    statistics = data["statistics"]
    primary = statistics["primary_interval"]

    assert statistics["primary_pairing_unit"] == "semantic_task_id"
    assert statistics["repeated_catalogs_nested_within_task"] is True
    assert statistics["language_is_between_task_stratum"] is True
    assert statistics["task_type_is_between_task_stratum"] is True
    assert statistics["pseudoreplication_forbidden"] is True
    assert primary == {
        "method": "stratified task-cluster bootstrap",
        "strata": "task_stratum x language",
        "resample_unit": "semantic_task_id",
        "preserve_cell_size": True,
        "iterations": 10000,
        "seed": 20260929,
        "confidence_interval": 0.95,
    }


def test_heldout_sample_size_does_not_overclaim_minus_2pp_precision() -> None:
    data = _load()
    sample = data["sample_size"]
    derivation = sample["derivation"]
    claim = data["broad_claim_gate"]

    assert sample["practical_noninferiority_margin"] == -0.02
    assert derivation["b1_effect_size_used"] is False
    assert derivation["b2_effect_size_used"] is False
    assert derivation["chosen_unique_semantic_tasks"] == 780
    assert derivation["tasks_needed_for_guaranteed_0_02_worst_case_half_width"] == 9604
    assert derivation["worst_case_95pct_half_width"] > 0.02
    assert claim["paired_95pct_ci_lower_bound_vs_full_must_be_at_least"] == -0.02
    assert "do not claim statistical noninferiority" in claim[
        "if_ci_does_not_clear_margin"
    ]


def test_heldout_safety_and_final_answer_claim_boundaries_are_explicit() -> None:
    data = _load()
    gate = data["product_utility_gate"]
    governance = data["governance"]

    assert gate["required_tool_set_recall_min"] == 0.97
    assert gate["tool_schema_token_ratio_vs_full_max"] == 0.4
    assert gate["unauthorized_destructive_executions_max"] == 0
    assert gate["execution_policy_integrity"] == 1.0
    assert governance["no_final_answer_quality_claim_from_this_benchmark_alone"] is True
    assert governance["final_answer_quality_requires_issue_424"] is True
