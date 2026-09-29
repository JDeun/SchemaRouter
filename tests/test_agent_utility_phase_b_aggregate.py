from __future__ import annotations

import json
from pathlib import Path

import pytest
from scripts.aggregate_agent_utility_phase_b import (
    _cluster_bootstrap_delta,
    aggregate,
)


MODEL = {
    "name": "Qwen/Qwen3-0.6B",
    "revision": "test-revision",
    "dtype": "float32",
    "device": "cpu",
    "context_limit": 40960,
}

POLICY = {
    "qwen_is_downstream_agent_only": True,
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
    name: str = "phase-b1-test.json",
) -> Path:
    path = tmp_path / name
    path.write_text(
        json.dumps(
            {
                "experiment": "0.14-agent-utility-phase-b1-qwen3-0.6b",
                "issue": 420,
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


def test_aggregate_rejects_duplicate_episode_keys(tmp_path: Path) -> None:
    row = _row(task_id="single-paper-search")
    path = _write_result(tmp_path, [row, dict(row)])

    with pytest.raises(ValueError, match="duplicate B1 episode key"):
        aggregate([path])


def test_aggregate_rejects_unknown_frozen_task_id(tmp_path: Path) -> None:
    path = _write_result(
        tmp_path,
        [_row(task_id="multi-inventory-create-send")],
    )

    with pytest.raises(ValueError, match="unknown B1 task id"):
        aggregate([path])


def test_cluster_bootstrap_resamples_semantic_tasks_not_catalog_rows() -> None:
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


def test_aggregate_rejects_model_configuration_drift(
    tmp_path: Path,
) -> None:
    first = _write_result(
        tmp_path,
        [_row(task_id="single-paper-search")],
        name="phase-b1-a.json",
    )
    payload = json.loads(first.read_text(encoding="utf-8"))
    payload["model"] = {**MODEL, "max_turns": 99}
    second = tmp_path / "phase-b1-b.json"
    second.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="model configuration drift"):
        aggregate([first, second])


def test_aggregate_rejects_policy_drift(tmp_path: Path) -> None:
    first = _write_result(
        tmp_path,
        [_row(task_id="single-paper-search")],
        name="phase-b1-a.json",
    )
    payload = json.loads(first.read_text(encoding="utf-8"))
    payload["policy"] = {
        **POLICY,
        "candidate_routes_lexically_sorted": False,
    }
    second = tmp_path / "phase-b1-b.json"
    second.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="policy drift"):
        aggregate([first, second])
