"""Chain only successful, budgeted, synthetic DEV Actions research batches."""
from __future__ import annotations

import copy
from pathlib import Path

import pytest

from scripts.research_actions_continuation import MAX_BATCHES, should_dispatch


def receipt(*, epoch: int = 1, generated: int = 24) -> tuple[dict, dict]:
    digest = "1" * 64
    state = {
        "schema_version": 1,
        "contract_sha256": digest,
        "epoch": epoch,
        "total_trials": epoch * generated,
        "champion": None,
    }
    report = {
        "schema_version": 1,
        "status": "ACTIONS_CPU_RESEARCH_ONLY",
        "source_commit": "a" * 40,
        "contract_sha256": digest,
        "previous_epoch": epoch - 1,
        "new_epoch": epoch,
        "total_new_trials": generated,
        "history": [{} for _ in range(generated)],
        "champion": None,
        "may_promote_to_product": False,
        "independent_validation": False,
        "search_space": "continuous_safe_weights_not_generated_code",
    }
    return report, state


def test_completion_triggers_next_only_inside_bounded_chain() -> None:
    report, state = receipt()
    assert should_dispatch(report, state, MAX_BATCHES)
    assert should_dispatch(*receipt(epoch=11), remaining=2)
    assert should_dispatch(*receipt(epoch=12), remaining=1) is False
    assert should_dispatch(report, state, 1) is False
    no_new, no_new_state = receipt(generated=0)
    assert should_dispatch(no_new, no_new_state, MAX_BATCHES) is False


@pytest.mark.parametrize("bad", [0, 13, True, -1])
def test_invalid_chain_budget_rejected(bad: object) -> None:
    with pytest.raises(ValueError):
        should_dispatch(*receipt(), remaining=bad)


@pytest.mark.parametrize("section,key,value", [
    ("report", "status", "PRODUCTION_RELEASE"),
    ("report", "independent_validation", True),
    ("report", "may_promote_to_product", True),
    ("report", "contract_sha256", "2" * 64),
    ("report", "source_commit", "bad-commit"),
    ("report", "previous_epoch", 20),
    ("report", "total_new_trials", 1000),
    ("report", "search_space", "arbitrary-executable-code"),
    ("state", "contract_sha256", "2" * 64),
    ("state", "epoch", 5),
    ("state", "champion", {"base": 1.0}),
])
def test_tampered_or_drifted_artifact_fails_closed(
    section: str, key: str, value: object,
) -> None:
    report, state = receipt()
    changed = {"report": copy.deepcopy(report), "state": copy.deepcopy(state)}
    changed[section][key] = value
    with pytest.raises(ValueError):
        should_dispatch(changed["report"], changed["state"], MAX_BATCHES)


def test_no_cron_and_no_write_token_on_compute_job() -> None:
    workflow = (
        Path(__file__).resolve().parents[1]
        / ".github/workflows/research-actions-only-cpu-search.yml"
    ).read_text(encoding="utf-8")
    assert "\n  schedule:" not in workflow
    assert "workflow_dispatch:" in workflow
    assert "previous_run_id" in workflow
    research, dispatcher = workflow.split("\n  dispatch-next:", 1)
    assert "actions: write" not in research
    assert "actions: write" in dispatcher
    assert "needs: adaptive-research" in dispatcher
