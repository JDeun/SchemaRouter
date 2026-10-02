from __future__ import annotations

import pytest

from scripts.select_corrective_recovery_shards import select


def _corpus() -> dict[str, object]:
    return {
        "tasks": [
            {"semantic_task_id": f"task-{index:03d}"}
            for index in range(180)
        ]
    }


def test_selects_exact_requested_frozen_shards() -> None:
    selected = select(_corpus(), "c250-g10,c250-g17")
    assert [item["job_id"] for item in selected] == ["c250-g10", "c250-g17"]
    assert selected[0]["catalog_size"] == 250
    assert selected[0]["task_ids"] == "task-030,task-031,task-032"


def test_rejects_duplicate_shards() -> None:
    with pytest.raises(ValueError, match="duplicate"):
        select(_corpus(), "c250-g10,c250-g10")


def test_rejects_unknown_shards() -> None:
    with pytest.raises(ValueError, match="unknown"):
        select(_corpus(), "c250-g60")
