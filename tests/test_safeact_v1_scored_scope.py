"""Prevent a one-rollout SafeAct V1 result from becoming an unwarranted generalization claim."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts import aggregate_safeact_v1_metrics as metrics


def test_scored_summary_discloses_single_rollout_and_manual_qa_limitations(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    arms = metrics.CONDITIONS
    outputs = {arm: tmp_path / arm for arm in arms}

    monkeypatch.setattr(
        metrics, "verify_comparison",
        lambda output_dirs, *, expected_cases: {
            "official_strict_success_rate": {arm: 0.0 for arm in arms},
            "attested_model": "frozen-test-model",
        },
    )
    monkeypatch.setattr(
        metrics, "verify_arm_interventions",
        lambda output_dirs, *, expected_cases: {
            arm: {"model_action_attempts": 0, "denied_action_attempts": 0}
            for arm in arms
        },
    )
    monkeypatch.setattr(
        metrics, "derive_condition_metrics",
        lambda root, expected_cases: {
            "evaluated_cases": expected_cases,
            "exact_case_success_rate": 0.0,
        },
    )
    monkeypatch.setattr(
        metrics, "paired_success_contrasts",
        lambda output_dirs, *, expected_cases: {},
    )

    report = metrics.aggregate_scored_v1(outputs, expected_cases=131)
    scope = report["evaluation_scope"]
    assert scope["rollouts_per_case_and_arm"] == 1
    assert scope["repeated_rollout_effect_estimated"] is False
    assert scope["manual_trajectory_annotation_completed"] is False
    assert scope["contract_authoring_transfer_tested"] is False
    assert scope["claim_level"] == "single_rollout_v1_observed_outcomes_only"
    assert report["causal_improvement_claim"] is None
    assert "false_refusal_rate" in report["not_yet_measured"]


def test_followup_protocol_is_explicitly_prospective_and_gold_free() -> None:
    path = (
        Path(__file__).resolve().parents[1]
        / "research/safeact-v1/repeated-evaluation-protocol.md"
    )
    text = path.read_text(encoding="utf-8")
    for condition in (
        "UNFROZEN",
        "hidden evaluator",
        "SCGR-Select",
        "rollout",
        "blinded manual",
        "cluster",
        "independent reviewer",
    ):
        assert condition.casefold() in text.casefold()
