"""Synthetic read-only 0.14 failure diagnosis; no model/score use."""
from __future__ import annotations

from copy import deepcopy

import pytest

from scripts.research_014_heldout_recovery import FROZEN_SOURCE
from scripts.research_014_recovery_forensics import inspect


class FakeAPI:
    def __init__(self) -> None:
        self.job = {
            "id": 114376765084,
            "name": "recover (c500-g27-p04, 500, frozen-task-1,frozen-task-2)",
            "status": "completed",
            "conclusion": "failure",
            "started_at": "2026-10-11T07:21:30Z",
            "completed_at": "2026-10-11T10:03:37Z",
        }
        self.state = "in_progress"
        self.title = (
            "Held-out recovery parent=38012340016 wave=0 "
            f"source={FROZEN_SOURCE}"
        )
        self.path = ".github/workflows/research-0.14-heldout-recovery.yml"
        self.read_paths: list[str] = []

    def run(self, run_id):
        assert run_id == 38107675261
        return {
            "path": self.path,
            "display_title": self.title,
            "status": self.state,
            "conclusion": None if self.state != "completed" else "failure",
            "run_attempt": 1,
        }

    def get(self, path):
        self.read_paths.append(path)
        if "/actions/runs/" in path and "/jobs?" in path:
            return {"jobs": [self.job]}
        if "/actions/jobs/" in path:
            return {"steps": [{
                "name": "Evaluate only two frozen task identities per microshard",
                "status": "in_progress", "conclusion": None,
            }]}
        raise AssertionError(f"unexpected read path: {path}")


def test_actual_failed_microshard_is_unknown_not_automatically_oom() -> None:
    api = FakeAPI()
    report = inspect(api, run_id=38107675261)
    assert report["evidence_role"].startswith("infrastructure_forensics_only")
    assert report["scientific_source_sha"] == FROZEN_SOURCE
    assert report["run_attempt"] == 1
    assert report["status_counts"] == {"completed/failure": 1}
    assert len(report["failed_jobs"]) == 1
    job = report["failed_jobs"][0]
    assert job["microshard_id"] == "c500-g27-p04"
    assert job["classification"] == "runner_interruption_possible_not_confirmed"
    assert job["duration_seconds"] == 9727
    assert job["replay_allowed_now"] is False
    assert report["deduced_root_cause"] is None
    assert all("/artifacts" not in x for x in api.read_paths)


def test_terminal_job_can_be_replayed_only_after_wave_completion() -> None:
    api = FakeAPI()
    api.state = "completed"
    report = inspect(api, run_id=38107675261)
    assert report["failed_jobs"][0]["replay_allowed_now"] is True


def test_evaluator_failure_is_separate_from_runner_interruption() -> None:
    api = FakeAPI()
    original_get = api.get

    def get(path):
        data = deepcopy(original_get(path))
        if "/actions/jobs/" in path:
            data["steps"][0]["status"] = "completed"
            data["steps"][0]["conclusion"] = "failure"
        return data

    api.get = get
    result = inspect(api, run_id=38107675261)
    assert (
        result["failed_jobs"][0]["classification"]
        == "evaluator_step_failed_cause_requires_logs"
    )


@pytest.mark.parametrize(
    "alter",
    [
        lambda api: setattr(api, "title", "random run"),
        lambda api: setattr(api, "path", ".github/workflows/ci.yml"),
        lambda api: setattr(api, "title", api.title.replace(FROZEN_SOURCE, "0" * 40)),
        lambda api: setattr(api, "title", api.title.replace("wave=0", "wave=3")),
    ],
)
def test_unfrozen_or_other_workflows_rejected(alter) -> None:
    api = FakeAPI()
    alter(api)
    with pytest.raises(ValueError):
        inspect(api, run_id=38107675261)


@pytest.mark.parametrize("bad_id", [0, -1, True])
def test_invalid_run_identity_rejected(bad_id) -> None:
    with pytest.raises(ValueError):
        inspect(FakeAPI(), run_id=bad_id)


def test_zero_materialized_jobs_is_not_success() -> None:
    api = FakeAPI()
    api.get = lambda path: {"jobs": []}
    with pytest.raises(ValueError, match="no materialized jobs"):
        inspect(api, run_id=38107675261)
