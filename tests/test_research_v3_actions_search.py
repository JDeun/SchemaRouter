"""Finite, source-bound V3 Github Actions CPU chain invariants."""
from __future__ import annotations

import json
import math
import random
from pathlib import Path

import pytest

from scripts.research_v1_v2_paired_cpu_dev import frozen_genomes
from scripts.research_v3_actions_search import (
    MAX_BATCHES,
    MAX_TRIALS_PER_BATCH,
    continue_chain,
    identity,
    propose,
    run,
    state_from_artifact,
    valid_genome,
)
from scripts.research_v3_width_pareto_cpu_dev import WIDTHS


def _receipt() -> tuple[dict, dict]:
    state = {
        "schema_version": 1, "contract_sha256": "a" * 64,
        "epoch": 1, "total_trials": 1, "seen": ["b" * 64],
        "champion": None, "best_internal_score": None,
    }
    report = {
        "schema_version": 1, "status": "V3_FINITE_ACTIONS_RESEARCH_ONLY",
        "contract_sha256": "a" * 64,
        "previous_epoch": 0, "new_epoch": 1, "new_trials": 1,
        "history": [{"genome": "reviewed"}],
        "champion": None,
        "scope": {"may_release": False, "automatic_product_promotion": False},
    }
    return report, state


def test_finite_epoch_budget_and_prior_artifact_mutation() -> None:
    report, state = _receipt()
    assert continue_chain(report, state, 6)
    next_state = dict(state, epoch=6)
    next_report = dict(report, previous_epoch=5, new_epoch=6)
    assert not continue_chain(next_report, next_state, 1)
    for bad in (0, 7, True, -1):
        with pytest.raises(ValueError):
            continue_chain(report, state, bad)
    with pytest.raises(ValueError):
        continue_chain(dict(report, contract_sha256="c" * 64), state, 6)
    with pytest.raises(ValueError):
        continue_chain(dict(report, scope={"may_release": True}), state, 6)


def test_exact_identity_controls_resuming_across_main_sha_and_dataset(tmp_path) -> None:
    contract = identity()
    initial = state_from_artifact(None, contract)
    assert initial["epoch"] == 0
    assert initial["champion"] is None
    restored = tmp_path / "state.json"
    restored.write_text(json.dumps(initial), encoding="utf-8")
    assert state_from_artifact(restored, contract) == initial
    variants = [
        {**initial, "contract_sha256": "0" * 64},
        {**initial, "epoch": MAX_BATCHES},
        {**initial, "total_trials": -1},
        {**initial, "seen": ["unsafe"]},
        {**initial, "champion": {"code": "exec"}},
        {**initial, "best_internal_score": math.nan},
    ]
    for bad in variants:
        restored.write_text(json.dumps(bad), encoding="utf-8")
        with pytest.raises(ValueError):
            state_from_artifact(restored, contract)


def test_registered_numeric_genomes_and_mutation_without_code() -> None:
    _, original, _ = frozen_genomes()
    for w in WIDTHS:
        assert valid_genome({"width": w, "weights": original["weights"]})["width"] == w
    for bad in (7, 128, "56", True):
        with pytest.raises(ValueError):
            valid_genome({"width": bad, "weights": original["weights"]})
    candidate = valid_genome({"width": 56, "weights": original["weights"]})
    rng = random.Random(1412)
    choices = [propose(rng, candidate, original) for _ in range(100)]
    assert all(choice["width"] in WIDTHS for choice in choices)
    assert len({json.dumps(x, sort_keys=True) for x in choices}) > 48


def test_real_planner_v3_search_executes_without_external_agent() -> None:
    previous = state_from_artifact(None, identity())
    report, state = run(previous=previous, trials=2, cases_per_group=2)
    assert report["status"] == "V3_FINITE_ACTIONS_RESEARCH_ONLY"
    assert report["candidate_pools"] == list(WIDTHS)
    assert report["fit_requests"] == 3 * 48
    assert report["internal_check_requests"] == 3 * 48
    assert report["actual_planner_calls"] == 3 * 96 * 6
    assert state["epoch"] == 1
    assert 0 <= report["new_trials"] <= 2
    assert report["scope"]["automatic_product_promotion"] is False
    assert report["scope"]["independent_confirmation"] is False
    assert report["scope"]["may_release"] is False
    assert continue_chain(report, state, 6) == (report["new_trials"] > 0)
    assert all(x["genome"]["width"] in WIDTHS for x in report["history"])
    for bad in (0, MAX_TRIALS_PER_BATCH + 1, True):
        with pytest.raises(ValueError):
            run(previous=previous, trials=bad, cases_per_group=2)


def test_workflow_has_no_cron_and_no_write_permission_for_cpu() -> None:
    path = (
        Path(__file__).resolve().parents[1]
        / ".github/workflows/research-actions-v3-continue.yml"
    )
    text = path.read_text(encoding="utf-8")
    assert "\n  schedule:" not in text
    assert "workflow_dispatch:" in text
    research, dispatcher = text.split("\n  dispatch-next:", 1)
    assert "actions: write" not in research
    assert "actions: write" in dispatcher
    assert "github.event_name == 'push'" in research
    assert "if: always() && steps.experiment.outcome == 'success'" in research
    assert "gh workflow run research-actions-v3-continue.yml" in dispatcher
