"""Frozen 0.14 aggregation wrapper regression; synthetic metadata only."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from scripts.research_014_conveyor import exclusively_failed_aggregate_only_wrapper


def jobs():
    return [
        {"name": "aggregate-only", "conclusion": "failure"},
        {"name": "prepare", "conclusion": "skipped"},
        {"name": "recover", "conclusion": "skipped"},
        {"name": "aggregate", "conclusion": "skipped"},
        {"name": "next-wave", "conclusion": "skipped"},
    ]


def test_exact_failed_no_model_wrapper_is_eligible_for_corrected_dispatch():
    assert exclusively_failed_aggregate_only_wrapper(jobs())
    assert exclusively_failed_aggregate_only_wrapper(list(reversed(jobs())))


@pytest.mark.parametrize(("name", "conclusion"), [
    ("aggregate-only", "success"),
    ("aggregate-only", "in_progress"),
    ("recover", "success"),
    ("recover", "failure"),
    ("prepare", "success"),
    ("next-wave", "success"),
])
def test_no_replay_when_original_wrapper_has_unexpected_job(name, conclusion):
    mutated = deepcopy(jobs())
    next(j for j in mutated if j["name"] == name)["conclusion"] = conclusion
    assert not exclusively_failed_aggregate_only_wrapper(mutated)


def test_no_replay_when_job_missing_repeated_or_unknown():
    original = jobs()
    assert not exclusively_failed_aggregate_only_wrapper(original[:-1])
    assert not exclusively_failed_aggregate_only_wrapper(original + [original[0]])
    unexpected = deepcopy(original)
    unexpected[-1]["name"] = "evaluate"
    assert not exclusively_failed_aggregate_only_wrapper(unexpected)


def test_frozen_aggregate_workflow_installs_the_scientific_checkout_not_head():
    workflow = (
        Path(__file__).resolve().parents[1]
        / ".github/workflows/research-0.14-heldout-recovery.yml"
    ).read_text(encoding="utf-8")
    assert workflow.count("python -m pip install -e ./scientific") == 2
    assert workflow.count("scientific/scripts/aggregate_agent_utility_v3_heldout.py") == 2
    assert workflow.count('ref: "${{ inputs.source_sha }}"') >= 2
    assert "Install precisely checked-out frozen scientific package" in workflow
    assert '--aggregate-only-source-run 38342986866' in workflow
    # Normal model-evaluator matrix remains disabled for aggregate_only=true.
    assert 'if: "${{ !inputs.aggregate_only }}"' in workflow
