"""No-model regression for 0.14 failure triage and retry classification."""
from __future__ import annotations

from copy import deepcopy

import pytest

from scripts.research_014_heldout_recovery import FROZEN_SOURCE
from scripts.triage_research_014_recovery import (
    EVALUATION_STEP,
    classify_failed_steps,
    triage,
)


class RecoveryAPI:
    def __init__(self, *, terminal: bool = False) -> None:
        self.terminal = terminal
        self.details_called: list[str] = []
        self.jobs = [
            {
                "id": 40000 + i,
                "name": f"recover (c500-g{i // 5:02d}-p{i % 5:02d}, 500, task)",
                "status": "completed",
                "conclusion": "success",
            }
            for i in range(250)
        ]
        self.jobs[0] = {
            **self.jobs[0],
            "status": "completed",
            "conclusion": "failure",
        }

    def run(self, run_id: int) -> dict:
        return {
            "path": ".github/workflows/research-0.14-heldout-recovery.yml",
            "display_title": (
                f"Held-out recovery parent=38012340016 wave=0 source={FROZEN_SOURCE}"
            ),
            "status": "completed" if self.terminal else "queued",
            "conclusion": "failure" if self.terminal else None,
        }

    def get(self, path: str) -> dict:
        self.details_called.append(path)
        if path.startswith("/actions/jobs/"):
            return {
                "steps": [
                    {"name": EVALUATION_STEP, "status": "in_progress",
                     "conclusion": None}
                ]
            }
        page = int(path.rsplit("page=", 1)[-1])
        return {"jobs": self.jobs[(page - 1) * 100:page * 100]}

    def artifacts(self, run_id: int) -> list[dict]:
        return [
            {
                "name": (
                    f"heldout-recovery-part-c500-g{j // 5:02d}"
                    f"-p{j % 5:02d}-{run_id}"
                ),
                "expired": False,
            }
            for j in range(250)
            if j != 0
        ]


def test_failed_job_cause_unproven_and_rerun_blocked_while_active() -> None:
    api = RecoveryAPI()
    report = triage(api, 38107675261)
    assert report["expected_microshards"] == 250
    assert report["successful_jobs"] == 249
    assert report["failed_jobs"] == 1
    assert report["scoring_values_inspected"] is False
    fail = report["failures"][0]
    assert fail["microshard"] == "c500-g00-p00"
    assert fail["stage_evidence"] == (
        "evaluator_step_incomplete_runner_or_telemetry_unknown"
    )
    assert fail["eligible_for_bounded_retry_after_run_ends"] is False
    assert fail["artifact_uploaded_not_proof_of_success"] is False
    assert api.details_called == ["/actions/jobs/40000"]


def test_terminal_failure_marks_only_incomplete_microshard_retryable() -> None:
    report = triage(RecoveryAPI(terminal=True), 38107675261)
    assert report["failed_jobs"] == 1
    assert report["failures"][0]["eligible_for_bounded_retry_after_run_ends"]
    assert report["successful_jobs"] == 249
    assert report["conclusion"] == "failure"


@pytest.mark.parametrize(
    ("steps", "expected"),
    [
        ([], "missing_step_telemetry"),
        (
            [{"name": EVALUATION_STEP, "status": "completed",
              "conclusion": "failure"}],
            "evaluator_step_failed_cause_unverified",
        ),
        (
            [{"name": EVALUATION_STEP, "status": "completed",
              "conclusion": "success"}],
            "evaluation_passed_but_later_job_failed",
        ),
        (
            [{"name": "Install runtime", "status": "completed",
              "conclusion": "failure"}],
            "setup_or_pre_evaluation_step_failed",
        ),
    ],
)
def test_failure_stage_labels_are_observations_not_oom_guesses(
    steps: list[dict], expected: str,
) -> None:
    assert classify_failed_steps(steps) == expected


def test_extra_or_duplicate_microshards_fail_closed() -> None:
    api = RecoveryAPI()
    api.jobs[1] = deepcopy(api.jobs[0])
    with pytest.raises(ValueError, match="duplicate"):
        triage(api, 38107675261)


def test_wrong_source_or_workflow_is_not_treated_as_recovery() -> None:
    api = RecoveryAPI()
    original = api.run

    def wrong_run(run_id: int) -> dict:
        value = original(run_id)
        value["display_title"] = value["display_title"].replace(
            FROZEN_SOURCE, "f" * 40
        )
        return value

    api.run = wrong_run
    with pytest.raises(ValueError, match="unfrozen"):
        triage(api, 38107675261)


def test_failed_evaluator_artifact_is_not_completion_evidence() -> None:
    api = RecoveryAPI(terminal=True)
    original = api.artifacts

    def with_partial(run_id: int) -> list[dict]:
        result = original(run_id)
        result.append({
            "name": f"heldout-recovery-part-c500-g00-p00-{run_id}",
            "expired": False,
        })
        return result

    api.artifacts = with_partial
    report = triage(api, 38107675261)
    assert report["failed_jobs"] == 1
    assert report["failures"][0]["artifact_uploaded_not_proof_of_success"]
