"""Actions-only adaptive retrieval search: bounded and honest synthetic DEV tests."""
from __future__ import annotations

import copy
import json
import math
import random

import pytest

from research.autoresearch.actions_ranker import (
    BASE,
    FEATURES,
    fingerprint,
    generate,
    rank,
    validate,
)
from scripts.research_actions_only_search import (
    contract_hash,
    load_previous,
    search,
    split_tasks,
    utility,
)
from benchmarks.agent_utility_v5_catalog import build_tasks


def test_control_exactly_preserves_current_candidate_order() -> None:
    rows = [
        {"route_id": "demo.read", "tool": "demo", "endpoint": "read",
         "tool_description": "records", "endpoint_description": "read records",
         "matched_fields": [], "output_fields": []},
        {"route_id": "demo.write", "tool": "demo", "endpoint": "write",
         "tool_description": "records", "endpoint_description": "write records",
         "matched_fields": [], "output_fields": []},
    ]
    assert rank("please write records", rows, BASE) == ["demo.read", "demo.write"]
    other = dict(BASE)
    other["identifier"] = 8.0
    assert rank("write", rows, other) == ["demo.write", "demo.read"]


@pytest.mark.parametrize("unsafe", [
    {"base": 1.0},
    {**BASE, "exec": 0.0},
    {**BASE, "token": -1.0},
    {**BASE, "token": math.nan},
    {**BASE, "token": math.inf},
    {**BASE, "base": True},
    {**BASE, "identifier": "1.0"},
])
def test_only_reviewed_finite_numeric_operators(unsafe: object) -> None:
    with pytest.raises(ValueError):
        validate(unsafe)


def test_evolution_generates_more_than_48_distinct_safe_hypotheses() -> None:
    rng = random.Random(2026)
    seen = set()
    for _ in range(160):
        config = generate(rng, BASE, None)
        assert set(config) == set(FEATURES)
        assert validate(config) == config
        seen.add(fingerprint(config))
    assert len(seen) > 120


def test_existing_known_dev_fit_check_slices_do_not_overlap() -> None:
    fit, check = split_tasks(build_tasks())
    assert len(fit) == 144
    assert len(check) == 96
    assert set(x["task_id"] for x in fit).isdisjoint(
        x["task_id"] for x in check
    )


def test_resume_fails_closed_for_tainted_previous_state(tmp_path) -> None:
    expected = contract_hash()
    initial = load_previous(None, expected)
    assert initial["anchor"] == BASE
    assert initial["champion"] is None
    filename = tmp_path / "state.json"
    filename.write_text(json.dumps(initial), encoding="utf-8")
    assert load_previous(filename, expected) == initial

    for key, value in (
        ("contract_sha256", "0" * 64),
        ("epoch", -1),
        ("seen", ["invalid"]),
        ("anchor", {"os_exec": 5.0}),
        ("champion", {"base": math.nan}),
    ):
        corrupted = copy.deepcopy(initial)
        corrupted[key] = value
        filename.write_text(json.dumps(corrupted), encoding="utf-8")
        with pytest.raises(ValueError):
            load_previous(filename, expected)


def test_trial_budget_and_utility_integrity_fail_closed() -> None:
    original = load_previous(None, contract_hash())
    for invalid in (0, 65, True):
        with pytest.raises(ValueError):
            search(trials=invalid, seed=1412, previous=original)
    before = [{"task_id": "caseA", "catalog_size": 100, "k": 5,
               "language": "en", "found_required_count": 1, "full_coverage": 1}]
    after = [{"task_id": "caseB", "catalog_size": 100, "k": 5,
              "language": "en", "found_required_count": 2, "full_coverage": 1}]
    with pytest.raises(ValueError):
        utility(before, after)


def test_one_true_cpu_trial_on_current_schema_planner() -> None:
    prior = load_previous(None, contract_hash())
    report, state = search(trials=1, seed=1412, previous=prior, seconds=60)
    assert report["status"] == "ACTIONS_CPU_RESEARCH_ONLY"
    assert report["fit_tasks_per_catalog"] == 144
    assert report["internal_check_tasks_per_catalog"] == 96
    assert report["catalogs"] == [100, 250, 500]
    assert state["epoch"] == 1
    assert report["total_new_trials"] in (0, 1)
    assert state["champion"] is None or validate(state["champion"]) == state["champion"]
    assert report["may_promote_to_product"] is False
    assert report["independent_validation"] is False
    assert "NO_LLM_OR_AUTONOMOUS_SOURCE_EDITS" in report["limitations"]
