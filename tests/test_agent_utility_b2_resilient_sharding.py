from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ORIGINAL = ROOT / "benchmarks" / "agent-utility-v1-b2-sharding.json"
RESILIENT = (
    ROOT / "benchmarks" / "agent-utility-v1-b2-sharding-resilient.json"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_resilient_b2_sharding_preserves_exact_episode_surface() -> None:
    original = _load(ORIGINAL)
    resilient = _load(RESILIENT)

    assert original["expected_episode_count"] == 460
    assert resilient["expected_episode_count"] == 460
    assert resilient["expected_job_count"] == 92
    assert resilient["semantic_task_count"] == 23
    assert resilient["conditions"] == original["conditions"]
    assert resilient["catalog_sizes"] == original["catalog_sizes"]

    original_task_ids = {row["task_id"] for row in original["jobs"]}
    resilient_task_ids = {row["task_id"] for row in resilient["jobs"]}
    assert resilient_task_ids == original_task_ids
    assert len(resilient_task_ids) == 23

    expected_pairs = {
        (task_id, catalog_size)
        for task_id in original_task_ids
        for catalog_size in original["catalog_sizes"]
    }
    actual_pairs = {
        (row["task_id"], row["catalog_sizes"][0])
        for row in resilient["jobs"]
    }
    assert actual_pairs == expected_pairs
    assert len(actual_pairs) == 92

    assert all(len(row["catalog_sizes"]) == 1 for row in resilient["jobs"])
    assert all(row["expected_episodes"] == 5 for row in resilient["jobs"])
    assert sum(row["expected_episodes"] for row in resilient["jobs"]) == 460


def test_resilient_b2_sharding_is_infrastructure_only() -> None:
    data = _load(RESILIENT)
    strategy = data["strategy"]
    governance = data["governance"]

    assert strategy["result_based_tuning"] is False
    assert strategy["benchmark_semantics_changed"] is False
    assert governance["failure_class"] == "github_hosted_runner_shutdown"
    assert governance["partial_attempt4_results_are_noncanonical"] is True
    assert governance["partial_task_outcomes_used_to_choose_sharding"] is False

    for key in (
        "model_changed",
        "prompt_changed",
        "conditions_changed",
        "catalogs_changed",
        "tasks_changed",
        "candidate_sets_changed",
        "stopping_changed",
        "executor_changed",
        "statistics_changed",
    ):
        assert governance[key] is False
