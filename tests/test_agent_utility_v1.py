# ruff: noqa: E402
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmarks.agent_utility_v1_catalog import (
    CATALOG_SIZES,
    K_VALUES,
    TASKS,
    build_registry,
    route_ids,
)
from scripts.evaluate_agent_utility_phase_a import _rank, evaluate


def test_agent_utility_catalog_sizes_are_exact() -> None:
    previous: set[str] = set()
    for size in CATALOG_SIZES:
        registry = build_registry(size)
        routes = set(route_ids(registry))
        assert len(routes) == size
        assert previous.issubset(routes)
        previous = routes


def test_agent_utility_tasks_are_frozen_and_grounded_in_base_catalog() -> None:
    assert len(TASKS) == 23
    assert sum(task.kind == "single" for task in TASKS) == 17
    assert sum(task.kind == "multi" for task in TASKS) == 6
    assert K_VALUES == (1, 3, 5, 10)

    routes = set(route_ids(build_registry(20)))
    task_ids = {task.task_id for task in TASKS}
    assert len(task_ids) == len(TASKS)
    for task in TASKS:
        assert task.query.strip()
        assert task.expected_answer.strip()
        assert task.kind in {"single", "multi"}
        assert set(task.required_routes).issubset(routes)
        if task.kind == "single":
            assert len(task.required_routes) == 1
        else:
            assert 2 <= len(task.required_routes) <= 3


def test_phase_a_ranking_is_deterministic() -> None:
    registry = build_registry(50)
    query = "Search scientific papers about solid-state battery electrolytes."
    first = _rank(registry, query)
    second = _rank(registry, query)
    assert [
        (row["route_id"], row["score"])
        for row in first
    ] == [
        (row["route_id"], row["score"])
        for row in second
    ]
    assert len(first) == 50


def test_phase_a_evaluator_reports_all_strata_and_k_values() -> None:
    result = evaluate()
    assert result["phase"] == "A"
    assert result["policy"]["llm_called"] is False
    assert set(result["catalog_sizes"]) == {
        str(size) for size in CATALOG_SIZES
    }
    for size in CATALOG_SIZES:
        metrics = result["catalog_sizes"][str(size)]
        assert metrics["endpoint_count"] == size
        assert metrics["task_count"] == 23
        assert set(metrics["k"]) == {str(k) for k in K_VALUES}
        full_bytes = metrics["full_schema_context"]["utf8_bytes"]
        for k in K_VALUES:
            bucket = metrics["k"][str(k)]
            assert 0.0 <= bucket["required_route_recall"] <= 1.0
            assert 0.0 <= bucket["all_required_task_coverage"] <= 1.0
            assert bucket["schema_context_bytes"]["max"] < full_bytes
