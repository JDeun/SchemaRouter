from __future__ import annotations

import json
from pathlib import Path

import pytest
from scripts.aggregate_agent_utility_phase_b import aggregate


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
