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


def _write_result(
    tmp_path: Path,
    rows: list[dict[str, object]],
    *,
    name: str = "phase-b1-test.json",
) -> Path:
    path = tmp_path / name
    path.write_text(
        json.dumps({"model": MODEL, "rows": rows}),
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
