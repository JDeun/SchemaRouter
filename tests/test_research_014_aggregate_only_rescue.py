"""Only rescore zero tasks when recovering a failed held-out aggregate."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

from scripts.research_014_heldout_recovery import (
    FROZEN_SOURCE,
    JOBS_PAGE_SIZE,
    latest_jobs,
    verify_aggregate_only_source,
)


PARENT = 38012340016
RECOVERY = 38342986866
WAVE = 2


def snapshot() -> list[dict]:
    evaluators = [
        {
            "id": index + 10,
            "name": (
                f"recover (c500-g{index // 5:02d}-p{index % 5:02d},"
                " 500, frozen-tasks)"
            ),
            "status": "completed",
            "conclusion": "success",
        }
        for index in range(185)
    ]
    return [
        {"id": 1, "name": "prepare", "conclusion": "success"},
        *evaluators,
        {"id": 2, "name": "aggregate", "conclusion": "failure"},
        {"id": 3, "name": "next-wave", "conclusion": "skipped"},
    ]


class FakeAPI:
    def __init__(self, jobs=None):
        self.jobs = snapshot() if jobs is None else jobs
        self.calls: list[str] = []
        self.source = {
            "path": ".github/workflows/research-0.14-heldout-recovery.yml",
            "display_title": (
                f"Held-out recovery parent={PARENT} wave={WAVE}"
                f" source={FROZEN_SOURCE}"
            ),
            "status": "completed",
            "conclusion": "failure",
            "run_attempt": 3,
        }

    def run(self, run_id):
        assert run_id == RECOVERY
        return self.source

    def get(self, path):
        self.calls.append(path)
        params = parse_qs(urlsplit("https://example.invalid" + path).query)
        size = int(params["per_page"][0])
        page = int(params["page"][0])
        assert params["filter"] == ["latest"]
        assert size == JOBS_PAGE_SIZE
        return {"jobs": self.jobs[(page - 1) * size:page * size]}


def verify(api):
    return verify_aggregate_only_source(
        api, recovery_run=RECOVERY, parent_run=PARENT, wave=WAVE,
    )


def test_188_jobs_are_paginated_and_verified_without_reexecution():
    api = FakeAPI()
    jobs = latest_jobs(api, RECOVERY)
    assert len(jobs) == 188
    assert len(api.calls) == 8
    assert all("per_page=25" in call for call in api.calls)
    api.calls.clear()
    verify(api)
    assert len(api.calls) == 8


@pytest.mark.parametrize(("mutation", "message"), [
    (lambda api: api.source.update(status="in_progress"), "terminal"),
    (lambda api: api.source.update(conclusion="success"), "terminal"),
    (lambda api: api.source.update(run_attempt=2), "retry budget"),
    (lambda api: api.source.update(run_attempt=True), "retry budget"),
    (lambda api: api.source.update(display_title="forged"), "marker"),
    (lambda api: api.source.update(path="other.yml"), "workflow"),
    (lambda api: api.jobs[1].update(conclusion="failure"), "evaluator"),
    (lambda api: api.jobs[0].update(conclusion="failure"), "aggregate-only"),
    (lambda api: api.jobs[-2].update(conclusion="success"), "aggregate-only"),
    (lambda api: api.jobs.append({"name": "unknown", "conclusion": "success"}),
     "unknown"),
])
def test_reject_unsafe_aggregate_only_sources(mutation, message):
    api = FakeAPI()
    mutation(api)
    with pytest.raises(ValueError, match=message):
        verify(api)


def test_job_pagination_refuses_malformed_page():
    api = FakeAPI()
    old_get = api.get
    api.get = lambda path: {"jobs": [dict(name="faked")] * (JOBS_PAGE_SIZE + 1)}
    with pytest.raises(ValueError, match="malformed"):
        latest_jobs(api, RECOVERY)
    api.get = old_get


def test_rescue_workflow_has_no_model_evaluator_and_only_frozen_aggregator():
    workflow = (
        Path(__file__).resolve().parents[1]
        / ".github/workflows/research-0.14-heldout-aggregate-rescue.yml"
    ).read_text(encoding="utf-8")
    assert "workflow_dispatch:" in workflow
    assert "--aggregate-only-from-run" in workflow
    assert "scientific/scripts/aggregate_agent_utility_v3_heldout.py" in workflow
    assert "evaluate_agent_utility_v3_heldout.py" not in workflow
    assert "torch==2.14" not in workflow
    assert "rerun-failed-jobs" not in workflow
    assert "inputs.source_sha" in workflow
    assert "heldout-recovery-plan-" in workflow
