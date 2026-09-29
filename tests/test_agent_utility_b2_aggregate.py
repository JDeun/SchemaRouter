from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.aggregate_agent_utility_phase_b2 import (  # noqa: E402
    _cluster_bootstrap_delta,
    _retrieval_coverage,
    aggregate,
)

RUNTIME = {
    "platform": "Linux-test",
    "python": "3.12.14",
    "torch": "2.14.0+cpu",
    "transformers": "4.57.6",
    "tokenizers": "0.22.2",
    "safetensors": "0.8.0",
}

MODEL = {
    "name": "HuggingFaceTB/SmolLM3-3B",
    "revision": "a07cc9a04f16550a088caea529712d1d335b0ac1",
    "dtype": "bfloat16",
    "device": "cpu",
    "context_limit": 65536,
}

POLICY = {
    "smollm3_is_downstream_agent_only": True,
    "native_tool_template": "xml_tools",
    "observation_message_role": "tool",
    "schemarouter_rank_scores_visible_to_agent": False,
    "candidate_routes_lexically_sorted": True,
    "task_ground_truth_visible_to_agent": False,
    "silent_truncation": False,
    "full_context_overflow_is_failure": True,
    "unauthorized_destructive_execution_allowed": False,
}


def _write_result(
    tmp_path: Path,
    rows: list[dict[str, object]],
    *,
    name: str = "phase-b2-test.json",
) -> Path:
    path = tmp_path / name
    path.write_text(
        json.dumps(
            {
                "experiment": "0.14-agent-utility-phase-b2-smollm3-3b",
                "issue": 423,
                "runtime": RUNTIME,
                "model": MODEL,
                "policy": POLICY,
                "rows": rows,
            }
        ),
        encoding="utf-8",
    )
    return path


def _row(
    *,
    task_id: str,
    catalog_size: int = 20,
    condition: str = "FULL",
) -> dict[str, object]:
    return {
        "catalog_size": catalog_size,
        "task_id": task_id,
        "condition": condition,
        "required_routes": ["papers.search"],
        "candidate_history": [["papers.search"]],
        "passed": True,
    }


def test_b2_aggregate_rejects_duplicate_episode_keys(tmp_path: Path) -> None:
    row = _row(task_id="single-paper-search")
    path = _write_result(tmp_path, [row, dict(row)])

    with pytest.raises(ValueError, match="duplicate B2 episode key"):
        aggregate([path])


def test_b2_aggregate_rejects_unknown_frozen_task_id(tmp_path: Path) -> None:
    path = _write_result(
        tmp_path,
        [_row(task_id="unknown-b2-task")],
    )

    with pytest.raises(ValueError, match="unknown B2 task id"):
        aggregate([path])


def test_b2_aggregate_rejects_sr3_condition_drift(tmp_path: Path) -> None:
    path = _write_result(
        tmp_path,
        [_row(task_id="single-paper-search", condition="SR-3")],
    )

    with pytest.raises(ValueError, match="condition set drift"):
        aggregate([path])


def test_b2_cluster_bootstrap_resamples_tasks_not_catalog_rows() -> None:
    full_rows = [
        {"task_id": "task-a", "catalog_size": size, "passed": False}
        for size in (20, 50, 100, 250)
    ] + [
        {"task_id": "task-b", "catalog_size": size, "passed": True}
        for size in (20, 50, 100, 250)
    ]
    condition_rows = [
        {"task_id": "task-a", "catalog_size": size, "passed": True}
        for size in (20, 50, 100, 250)
    ] + [
        {"task_id": "task-b", "catalog_size": size, "passed": True}
        for size in (20, 50, 100, 250)
    ]

    result = _cluster_bootstrap_delta(
        full_rows,
        condition_rows,
        iterations=200,
        seed=1,
    )

    assert result["delta"] == 0.5
    assert result["cluster_unit"] == "task_id"
    assert result["unique_task_count"] == 2
    assert result["catalog_repeats_per_task"] == 4


def test_b2_aggregate_rejects_model_runtime_and_policy_drift(
    tmp_path: Path,
) -> None:
    first = _write_result(
        tmp_path,
        [_row(task_id="single-paper-search")],
        name="a.json",
    )

    payload = json.loads(first.read_text(encoding="utf-8"))
    payload["model"] = {**MODEL, "max_turns": 99}
    second = tmp_path / "model.json"
    second.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="model configuration drift"):
        aggregate([first, second])

    payload = json.loads(first.read_text(encoding="utf-8"))
    payload["runtime"] = {**RUNTIME, "transformers": "different"}
    second.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="runtime identity drift"):
        aggregate([first, second])

    payload = json.loads(first.read_text(encoding="utf-8"))
    payload["policy"] = {
        **POLICY,
        "candidate_routes_lexically_sorted": False,
    }
    second.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="policy drift"):
        aggregate([first, second])


def test_b2_retrieval_coverage_uses_final_exposed_set() -> None:
    rows = [
        {
            "catalog_size": 20,
            "required_routes": ["a", "b"],
            "candidate_history": [["a"], ["a", "b"]],
        },
        {
            "catalog_size": 50,
            "required_routes": ["a", "b"],
            "candidate_history": [["a"]],
        },
    ]

    result = _retrieval_coverage(rows)

    assert result["required_route_recall"] == 0.75
    assert result["all_required_task_coverage"] == 0.5
    assert result["minimum_required_route_recall_by_catalog"] == 0.5


def test_b2_sharding_plan_covers_exact_460_episode_surface() -> None:
    from benchmarks.agent_utility_b2_catalog import TASKS

    plan = json.loads(
        (
            Path(__file__).resolve().parents[1]
            / "benchmarks"
            / "agent-utility-v1-b2-sharding.json"
        ).read_text(encoding="utf-8")
    )

    assert plan["expected_job_count"] == 41
    assert plan["expected_episode_count"] == 460
    assert plan["conditions"] == [
        "FULL",
        "SR-5",
        "SR-10",
        "SR-PROGRESSIVE",
        "ORACLE",
    ]

    expected_task_ids = {task.task_id for task in TASKS}
    represented = set()
    episode_keys: set[tuple[int, str, str]] = set()

    for job in plan["jobs"]:
        task_id = job["task_id"]
        represented.add(task_id)
        sizes = job["catalog_sizes"]
        assert job["expected_episodes"] == len(sizes) * len(plan["conditions"])
        for size in sizes:
            for condition in plan["conditions"]:
                key = (int(size), task_id, condition)
                assert key not in episode_keys
                episode_keys.add(key)

    assert represented == expected_task_ids
    assert len(episode_keys) == 460
    assert {
        size for size, _, _ in episode_keys
    } == {20, 50, 100, 250}
