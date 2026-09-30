from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OLD = (
    ROOT
    / "benchmarks"
    / "agent-utility-v5-adaptive-shortlist-preregistration.json"
)
NEW = (
    ROOT
    / "benchmarks"
    / "agent-utility-v5-structural-adaptive-depth-preregistration.json"
)
CONFIRMED = (
    ROOT
    / "benchmarks"
    / "agent-utility-v5-structural-confirmation-result.json"
)


def test_structural_adaptive_reuses_original_policy_family_unchanged() -> None:
    old = json.loads(OLD.read_text(encoding="utf-8"))
    new = json.loads(NEW.read_text(encoding="utf-8"))

    assert new["candidate_policies"] == old["candidate_policies"]
    assert (
        new["score_semantics"]["formula"]
        == old["score_semantics"]["formula"]
    )
    assert (
        new["score_semantics"]["evaluated_positions"]
        == old["score_semantics"]["evaluated_positions"]
    )
    assert (
        new["dev_selection"]["eligibility_thresholds"]
        == old["dev_selection"]["eligibility_thresholds"]
    )


def test_structural_adaptive_uses_exact_original_dev_identity() -> None:
    new = json.loads(NEW.read_text(encoding="utf-8"))
    surface = new["development_surface"]

    assert surface["semantic_task_count"] == 240
    assert surface["task_rows_sha256"] == (
        "7f2e4903642ad6aa6586540c30d2704e"
        "f20f7d0ff2c76ad73136aa55bb873534"
    )
    assert surface["catalog_family_sha256"] == (
        "39a91721ef8d960adf626686b23eb6c8"
        "7e154fa858a0381ee8027026fb26d677"
    )


def test_structural_adaptive_binds_confirmed_fixed_retriever() -> None:
    new = json.loads(NEW.read_text(encoding="utf-8"))
    confirmed = json.loads(
        CONFIRMED.read_text(encoding="utf-8")
    )

    assert confirmed["status"] == "independent_confirmation_passed"
    assert confirmed["gates"]["passed"] is True
    assert new["fixed_retriever"]["candidate_id"] == "STRUCT-4.5-1.5"
    assert new["fixed_retriever"]["tool_identifier_bonus"] == 4.5
    assert new["fixed_retriever"]["operation_family_bonus"] == 1.5
    assert (
        new["independence"][
            "structural_confirmation_rows_allowed_for_adaptive_tuning"
        ]
        is False
    )
    assert (
        new["after_dev"]["structural_confirmation_surface_reuse_allowed"]
        is False
    )


def test_structural_adaptive_restores_frozen_evaluator_contract() -> None:
    old = json.loads(OLD.read_text(encoding="utf-8"))
    new = json.loads(NEW.read_text(encoding="utf-8"))

    for key in (
        "unique_semantic_tasks",
        "task_strata",
        "languages",
        "tasks_per_stratum_language_cell",
        "cells",
        "each_task_one_language_only",
    ):
        assert new["development_surface"][key] == old["development_surface"][key]

    assert new["catalogs"] == old["catalogs"]
    assert new["metric_populations"] == old["metric_populations"]
