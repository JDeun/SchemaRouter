"""Actual current-library joint-pool/reranker CPU research contract checks."""
from __future__ import annotations

import copy
import math
import random

import pytest

from research.autoresearch.actions_ranker import BASE
from scripts import research_actions_joint_pool as joint


def test_genome_does_not_accept_arbitrary_source_or_width() -> None:
    original = {"pool_width": 24, "weights": BASE.copy()}
    assert joint.validate_genome(original) == original
    for invalid in (
        {"pool_width": 25, "weights": BASE},
        {"pool_width": True, "weights": BASE},
        {"pool_width": 128, "weights": {**BASE, "shell": 1}},
        {"pool_width": 64, "weights": {**BASE, "token": math.nan}},
        {"pool_width": 24, "weights": BASE, "source_code": "open('/etc/passwd')"},
    ):
        with pytest.raises(ValueError):
            joint.validate_genome(invalid)


def test_generator_creates_joint_width_and_weight_hypotheses() -> None:
    rng = random.Random(1412)
    generated = [joint.mutate(rng, None, None) for _ in range(60)]
    assert {x["pool_width"] for x in generated} == {24, 64, 128}
    assert len({joint.genome_id(x) for x in generated}) > 55
    assert all(joint.validate_genome(x) == x for x in generated)


def test_stale_or_modified_research_state_fails_closed(tmp_path) -> None:
    prior = joint.blank_state()
    assert joint.load_state(None) == prior
    target = tmp_path / "state.json"
    target.write_text(__import__("json").dumps(prior), encoding="utf-8")
    assert joint.load_state(target) == prior
    corrupted = copy.deepcopy(prior)
    corrupted["contract_sha256"] = "0" * 64
    target.write_text(__import__("json").dumps(corrupted), encoding="utf-8")
    with pytest.raises(ValueError):
        joint.load_state(target)
    target.unlink()
    with pytest.raises(ValueError):
        joint.load_state(target)


def test_receipt_enforces_finite_chain_and_nonpromotion() -> None:
    source = joint.blank_state()
    state = copy.deepcopy(source)
    state["epoch"] = 1
    report = {
        "status": "JOINT_POOL_SYNTHETIC_DEV_ONLY",
        "contract_sha256": joint.contract(),
        "next_epoch": 1,
        "new_trial_count": 1,
        "history": [{}],
        "champion": None,
        "may_promote_product": False,
        "independent_confirmation": False,
    }
    assert joint.continue_chain(report, state, 8) == (True, 7)
    # A different remaining budget for the same epoch is a forged chain.
    with pytest.raises(ValueError):
        joint.continue_chain(report, state, 1)
    with pytest.raises(ValueError):
        joint.continue_chain(report, state, 9)
    with pytest.raises(ValueError):
        joint.continue_chain({**report, "may_promote_product": True}, state, 8)
    with pytest.raises(ValueError):
        joint.continue_chain({**report, "new_trial_count": 2}, state, 8)


def test_wider_pool_backend_over_budget_is_never_kept() -> None:
    def row(found: int) -> dict:
        return {
            "catalog_size": 100,
            "task_id": "case-001",
            "language": "en",
            "k": 5,
            "required_route_count": 1,
            "found_required_count": found,
            "full_coverage": found,
            "candidate_json_bytes": 100,
        }
    before_timing = {"retrieval_p95_ms": 2.0}
    slow = {"retrieval_p95_ms": 9.0, "rerank_p95_ms": 0.1}
    result = joint.gate([row(0)], [row(1)], before_timing, slow)
    assert result["decision"] == "DISCARD_OR_REVISE"
    assert not result["guard_results"]["width_backend_cpu_budget"]


@pytest.mark.parametrize("trial,seconds", [(0, 120), (33, 120), (1, 0), (1, 1201)])
def test_unbounded_search_rejected_before_loading_data(trial: int, seconds: int) -> None:
    with pytest.raises(ValueError):
        joint.search(trials=trial, seconds=seconds, seed=1412,
                     previous=joint.blank_state())


def test_real_current_planner_and_joint_ranking_trial() -> None:
    report, state = joint.search(
        trials=1, seconds=120, seed=1412,
        previous=joint.blank_state(),
    )
    assert report["status"] == "JOINT_POOL_SYNTHETIC_DEV_ONLY"
    assert report["actual_current_planner_retrieval_calls"] == 2160
    assert report["fit_requests"] == 432
    assert report["internal_check_requests"] == 288
    assert state["epoch"] == 1
    assert report["new_trial_count"] == 1
    assert report["history"][0]["pool_width"] in (24, 64, 128)
    assert report["may_promote_product"] is False
    assert report["independent_confirmation"] is False
    assert state["total_trials"] == 1


def test_workflow_is_event_driven_and_scoped_to_readonly_cpu() -> None:
    path = joint.ROOT / ".github/workflows/research-actions-joint-pool-search.yml"
    contents = path.read_text(encoding="utf-8")
    assert "\n  schedule:" not in contents
    assert "workflow_dispatch:" in contents
    assert "previous_run_id" in contents
    research, dispatcher = contents.split("\n  dispatch-next:", 1)
    assert "actions: write" not in research
    assert "actions: write" in dispatcher
    assert "persist-credentials: false" in research
