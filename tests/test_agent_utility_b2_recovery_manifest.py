from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "benchmarks" / "agent-utility-v1-b2-recovery-manifest.json"


def _load() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def test_b2_recovery_is_same_run_infra_only_and_bounded() -> None:
    data = _load()
    policy = data["retry_policy"]
    eligibility = data["retry_eligibility"]

    assert data["issue"] == 423
    assert data["workflow_run_id"] == 36561002246
    assert data["trigger_sha"] == "20fee33e09d4a2c64a3ae5022818996e4744a11a"
    assert data["status"] == "frozen_before_terminal_result"

    assert policy["mechanism"] == "github_actions_rerun_failed_jobs_same_workflow_run"
    assert policy["same_github_sha_required"] is True
    assert policy["same_github_ref_required"] is True
    assert policy["max_failed_job_rerun_attempts"] == 5
    assert policy["successful_jobs_must_not_be_reselected_for_outcome"] is True
    assert policy["partial_task_outcomes_must_not_be_inspected_between_retries"] is True

    assert eligibility["infra_only_required"] is True
    assert eligibility["semantic_or_benchmark_failure_retryable"] is False
    assert eligibility["runtime_contract_failure_retryable"] is False
    assert eligibility["scoring_assertion_failure_retryable"] is False
    assert eligibility["model_prompt_k_condition_change_allowed"] is False


def test_b2_recovery_accepts_only_exact_frozen_460_episode_surface() -> None:
    data = _load()
    acceptance = data["canonical_acceptance"]

    assert acceptance["exact_episode_count"] == 460
    assert acceptance["exact_unique_episode_keys"] == 460
    assert acceptance["episode_key"] == ["catalog_size", "task_id", "condition"]
    assert acceptance["all_identity_checks_must_pass"] is True
    assert acceptance["unauthorized_destructive_executions_max"] == 0


def test_b2_recovery_does_not_change_benchmark_semantics() -> None:
    governance = _load()["governance"]

    assert governance["b2_scores_used_to_define_recovery"] is False
    for key in (
        "model_changed",
        "prompt_changed",
        "k_changed",
        "tasks_changed",
        "catalogs_changed",
        "candidate_sets_changed",
        "conditions_changed",
        "scoring_changed",
        "statistics_changed",
    ):
        assert governance[key] is False
