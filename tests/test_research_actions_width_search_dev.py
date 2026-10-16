"""Guard the new Actions CPU pool-width and ranking-weights research family."""
from __future__ import annotations

import math
import random

import pytest

from benchmarks.agent_utility_v5_catalog import LANGUAGES
from research.autoresearch.actions_ranker import BASE
from scripts.research_actions_width_search_dev import (
    CLAIM_BOUNDARY,
    POOL_WIDTHS,
    full_result,
    new_genome,
    split_fixture,
    validated_genome,
)


def test_only_reviewed_width_and_safe_weights_accepted() -> None:
    for width in POOL_WIDTHS:
        assert validated_genome({"width": width, "weights": BASE})["width"] == width
    for bad in (0, 5, 23, 256, True, 24.0, "24"):
        with pytest.raises(ValueError):
            validated_genome({"width": bad, "weights": BASE})
    for bad in ({}, {"width": 24}, {"width": 24, "weights": BASE, "shell": "true"}):
        with pytest.raises(ValueError):
            validated_genome(bad)
    with pytest.raises(ValueError):
        validated_genome({"width": 64, "weights": {**BASE, "token": math.nan}})


def test_adaptive_width_changes_beyond_candidate_reorder_only() -> None:
    rng = random.Random(100)
    seen = {new_genome(rng, None)["width"] for _ in range(90)}
    assert seen == set(POOL_WIDTHS)
    champion = validated_genome({"width": 128, "weights": BASE})
    assert new_genome(rng, champion)["width"] in POOL_WIDTHS


def test_fit_and_check_are_disjoint_only_inside_exposed_synthetic_dev() -> None:
    for per_group, train_size, test_size in ((2, 48, 48), (5, 144, 96)):
        train, check = split_fixture(per_group)
        assert len(train) == train_size
        assert len(check) == test_size
        assert {x["task_id"] for x in train}.isdisjoint(
            {x["task_id"] for x in check}
        )
        assert set(x["language"] for x in train) == set(LANGUAGES)
    for bad in (0, 1, 3, 6, True):
        with pytest.raises(ValueError):
            split_fixture(bad)


def test_search_budget_and_promotion_guards() -> None:
    for n in (0, 2, 37, True):
        with pytest.raises(ValueError):
            full_result(trials=n)
    for seed in (-1, True):
        with pytest.raises(ValueError):
            full_result(trials=3, seed=seed)
    assert CLAIM_BOUNDARY["may_promote"] is False
    assert CLAIM_BOUNDARY["may_release"] is False
    assert CLAIM_BOUNDARY["agent_task_success_tested"] is False


def test_actual_current_api_multilingual_breadth_scoring() -> None:
    # Mandatory K24/64/128 base rank controls — real planner retrievals
    # on 100/250/500 synthetic typed endpoints. No gold enters rank().
    report = full_result(trials=3, cases_per_group=2, seed=1412)
    assert report["id"] == "actions-only-adaptive-pool-width-reranking-v2-dev"
    assert report["actual_current_planner_retrieval_calls"] == 864
    assert report["fit_cases_per_catalog"] == 48
    assert report["internal_check_cases_per_catalog"] == 48
    assert [x["genome"]["width"] for x in report["attempts"]] == [24, 64, 128]
    assert len(report["attempts"]) == 3
    assert all(x["actual_retrieval_plus_rank_p95_ms"] > 0 for x in report["attempts"])
    assert all(x["internal_dev_keep"] in (True, False) for x in report["attempts"])
    assert report["scope"]["principal_authorization_tested"] is False
    assert report["scope"]["may_promote"] is False
    assert report["champion_is_only_internal_exposed_DEV"] is True
