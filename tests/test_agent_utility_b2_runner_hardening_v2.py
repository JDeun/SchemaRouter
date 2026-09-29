from __future__ import annotations

import importlib.util
import inspect
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "benchmarks" / "agent-utility-v1-b2-sharding-runner-hardened.json"
WORKFLOW = ROOT / ".github" / "workflows" / "research-0.14-b2-smollm3-full.yml"
EVALUATOR = ROOT / "scripts" / "evaluate_agent_utility_phase_b_smollm3.py"


def _evaluator_module():
    spec = importlib.util.spec_from_file_location("b2_eval_hardened", EVALUATOR)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_runner_hardened_plan_preserves_exact_460_episode_surface() -> None:
    plan = json.loads(PLAN.read_text(encoding="utf-8"))

    assert plan["issue"] == 423
    assert plan["expected_job_count"] == 184
    assert plan["expected_episode_count"] == 460
    assert plan["semantic_task_count"] == 23
    assert plan["catalog_sizes"] == [20, 50, 100, 250]
    assert plan["conditions"] == [
        "FULL",
        "SR-5",
        "SR-10",
        "SR-PROGRESSIVE",
        "ORACLE",
    ]

    jobs = plan["jobs"]
    assert len(jobs) == 184
    assert sum(row["expected_episodes"] for row in jobs) == 460

    episode_keys: set[tuple[int, str, str]] = set()
    task_catalog_pairs: set[tuple[str, int]] = set()
    for row in jobs:
        assert len(row["catalog_sizes"]) == 1
        size = int(row["catalog_sizes"][0])
        task_id = str(row["task_id"])
        task_catalog_pairs.add((task_id, size))

        assert row["conditions_csv"] == ",".join(row["conditions"])
        assert row["expected_episodes"] == len(row["conditions"])
        for condition in row["conditions"]:
            key = (size, task_id, condition)
            assert key not in episode_keys
            episode_keys.add(key)

    assert len(task_catalog_pairs) == 23 * 4
    assert len(episode_keys) == 23 * 4 * 5


def test_runner_hardened_condition_groups_are_complete_and_disjoint() -> None:
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    groups = plan["condition_groups"]

    assert groups == [
        {"group_id": "full-oracle", "conditions": ["FULL", "ORACLE"]},
        {
            "group_id": "sr-bounded",
            "conditions": ["SR-5", "SR-10", "SR-PROGRESSIVE"],
        },
    ]

    flattened = [
        condition
        for group in groups
        for condition in group["conditions"]
    ]
    assert len(flattened) == len(set(flattened)) == 5
    assert set(flattened) == set(plan["conditions"])


def test_condition_subset_validation_fails_before_model_load() -> None:
    module = _evaluator_module()

    assert module.ALL_CONDITIONS == (
        "FULL",
        "SR-5",
        "SR-10",
        "SR-PROGRESSIVE",
        "ORACLE",
    )

    with pytest.raises(ValueError, match="at least one"):
        module.evaluate(catalog_sizes=(20,), conditions=())

    with pytest.raises(ValueError, match="unknown B2 condition"):
        module.evaluate(catalog_sizes=(20,), conditions=("NOT-A-CONDITION",))

    with pytest.raises(ValueError, match="must be unique"):
        module.evaluate(catalog_sizes=(20,), conditions=("FULL", "FULL"))


def test_evaluator_exposes_condition_subset_without_changing_default() -> None:
    module = _evaluator_module()
    signature = inspect.signature(module.evaluate)

    assert signature.parameters["conditions"].default == module.ALL_CONDITIONS

    source = EVALUATOR.read_text(encoding="utf-8")
    assert '"--conditions"' in source
    assert 'default=",".join(ALL_CONDITIONS)' in source


def test_workflow_uses_runner_hardened_matrix_and_bounded_runner_lifetime() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "Export runner-hardened 184-job matrix" in text
    assert "agent-utility-v1-b2-sharding-runner-hardened.json" in text
    assert 'assert plan["expected_job_count"] == 184' in text
    assert "max-parallel: 4" in text
    assert "timeout-minutes: 45" in text
    assert '--conditions "${{ matrix.conditions }}"' in text
    assert 'EXPECTED_CONDITIONS: "${{ matrix.conditions }}"' in text
    assert "python -u scripts/evaluate_agent_utility_phase_b_smollm3.py" in text


def test_runner_hardening_is_outcome_independent() -> None:
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    governance = plan["governance"]

    assert plan["strategy"]["result_based_tuning"] is False
    assert plan["strategy"]["benchmark_semantics_changed"] is False
    assert governance["partial_task_outcomes_used_to_choose_hardening"] is False

    for key in (
        "model_changed",
        "prompt_changed",
        "tasks_changed",
        "catalogs_changed",
        "candidate_sets_changed",
        "conditions_changed",
        "condition_episode_definition_changed",
        "stopping_changed",
        "executor_changed",
        "scoring_changed",
        "statistics_changed",
    ):
        assert governance[key] is False
