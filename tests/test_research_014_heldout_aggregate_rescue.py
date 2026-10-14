"""One-shot GitHub 502 aggregation rescue: synthetic metadata only, no model."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from scripts.research_014_heldout_recovery import (
    AGGREGATE_RESCUE_PARENT,
    AGGREGATE_RESCUE_RUN,
    FROZEN_SOURCE,
    latest_jobs,
    validate_aggregate_only_rescue,
)


def plan():
    parts = [
        f"c500-g{group:02d}-p{part:02d}"
        for group in range(37) for part in range(5)
    ]
    assert len(parts) == 185
    return {
        "parent_run_id": AGGREGATE_RESCUE_PARENT,
        "source_sha": FROZEN_SOURCE,
        "wave": 2,
        "total_waves": 3,
        "matrix": [{"job_id": part} for part in parts],
    }


class API:
    def __init__(self):
        self.details = {
            "status": "completed",
            "conclusion": "failure",
            "path": ".github/workflows/research-0.14-heldout-recovery.yml",
            "display_title": (
                f"Held-out recovery parent={AGGREGATE_RESCUE_PARENT} "
                f"wave=2 source={FROZEN_SOURCE}"
            ),
        }
        self.jobs = [
            {"name": "prepare", "conclusion": "success"},
            {"name": "aggregate", "conclusion": "failure"},
            *(
                {"name": f"recover ({entry['job_id']}, 500, tasks...)",
                 "conclusion": "success"}
                for entry in plan()["matrix"]
            ),
        ]
        self.pages = []

    def run(self, run_id):
        assert run_id == AGGREGATE_RESCUE_RUN
        return self.details

    def get(self, path):
        self.pages.append(path)
        assert f"/actions/runs/{AGGREGATE_RESCUE_RUN}/jobs?" in path
        assert "filter=latest" in path
        page = int(path.rsplit("page=", 1)[-1])
        size = int(path.split("per_page=", 1)[1].split("&", 1)[0])
        return {"jobs": self.jobs[(page - 1) * size:page * size]}


def test_paginated_jobs_use_small_idempotent_get_pages():
    api = API()
    jobs = latest_jobs(api, AGGREGATE_RESCUE_RUN)
    assert len(jobs) == 187
    assert len(api.pages) == 8
    assert all("per_page=25" in path for path in api.pages)


def test_rescue_accepts_only_complete_original_successful_evaluators():
    api = API()
    validate_aggregate_only_rescue(
        api, plan(), source_run=AGGREGATE_RESCUE_RUN
    )


@pytest.mark.parametrize("mutation", [
    lambda api, p: api.details.update(status="in_progress"),
    lambda api, p: api.details.update(conclusion="success"),
    lambda api, p: api.details.update(path="other-workflow.yml"),
    lambda api, p: api.details.update(display_title="unverified"),
    lambda api, p: api.jobs[2].update(conclusion="failure"),
    lambda api, p: api.jobs.pop(),
    lambda api, p: api.jobs.append(deepcopy(api.jobs[2])),
    lambda api, p: api.jobs[1].update(conclusion="success"),
    lambda api, p: p.update(source_sha="unfrozen"),
    lambda api, p: p.update(parent_run_id=1),
    lambda api, p: p.update(wave=1),
])
def test_aggregate_rescue_fails_closed_for_invalid_source(mutation):
    api, frozen = API(), plan()
    mutation(api, frozen)
    with pytest.raises(ValueError):
        validate_aggregate_only_rescue(
            api, frozen, source_run=AGGREGATE_RESCUE_RUN
        )


def test_aggregate_rescue_rejects_different_run_id_before_api():
    api = API()
    with pytest.raises(ValueError, match="unapproved"):
        validate_aggregate_only_rescue(
            api, plan(), source_run=AGGREGATE_RESCUE_RUN + 1
        )
    assert api.pages == []


def test_rescue_workflow_never_dispatches_recovery_matrix_in_aggregate_only_mode():
    root = Path(__file__).resolve().parents[1]
    workflow = (
        root / ".github/workflows/research-0.14-heldout-recovery.yml"
    ).read_text(encoding="utf-8")
    assert 'if: "${{ !inputs.aggregate_only }}"' in workflow
    assert 'if: "${{ inputs.aggregate_only }}"' in workflow
    assert "--aggregate-only-source-run 38342986866" in workflow
    assert "heldout-recovery-plan-38342986866" in workflow
    assert "scientific/scripts/aggregate_agent_utility_v3_heldout.py" in workflow
    assert "scripts/evaluate_agent_utility_v3_heldout.py" in workflow
    assert "Aggregate exclusively with the frozen historical scorer" in workflow
