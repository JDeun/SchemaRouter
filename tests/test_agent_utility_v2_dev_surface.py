from __future__ import annotations

import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

from benchmarks.agent_utility_v2_catalog import (
    CATALOG_SIZES,
    DEVELOPMENT_TASKS,
    LANGUAGES,
    STRATA,
    build_registry,
    development_rows,
)
from scripts.generate_agent_utility_v2_dev import freeze_dev

ROOT = Path(__file__).resolve().parents[1]


def test_v2_dev_surface_matches_preregistration_counts() -> None:
    assert len(DEVELOPMENT_TASKS) == 60
    assert len(development_rows()) == 360
    assert {task.semantic_task_id for task in DEVELOPMENT_TASKS}
    assert len({task.semantic_task_id for task in DEVELOPMENT_TASKS}) == 60
    assert Counter(task.stratum for task in DEVELOPMENT_TASKS) == Counter(
        {stratum: 5 for stratum in STRATA}
    )
    for task in DEVELOPMENT_TASKS:
        assert tuple(task.queries) == LANGUAGES
        assert bool(task.required_routes) is task.supported


def test_v2_dev_required_routes_exist_in_all_catalogs() -> None:
    required = {
        route
        for task in DEVELOPMENT_TASKS
        if task.supported
        for route in task.required_routes
    }

    for size in CATALOG_SIZES:
        registry = build_registry(size)
        routes = {
            f"{tool.key}.{endpoint.name}"
            for tool in registry.tools()
            for endpoint in tool.endpoints
        }
        assert len(routes) == size
        assert required <= routes


def test_v2_dev_catalog_sizes_are_exact_and_nested() -> None:
    prior: set[str] = set()
    for size in CATALOG_SIZES:
        registry = build_registry(size)
        routes = {
            f"{tool.key}.{endpoint.name}"
            for tool in registry.tools()
            for endpoint in tool.endpoints
        }
        assert len(routes) == size
        assert prior <= routes
        prior = routes


def test_v2_freeze_is_deterministic_and_confirmation_stays_sealed(tmp_path: Path) -> None:
    first = freeze_dev(tmp_path / "first")
    second = freeze_dev(tmp_path / "second")

    assert first == second
    assert first["surface"] == "development"
    assert first["confirmation_surface_opened"] is False
    assert first["semantic_task_count"] == 60
    assert first["rows"] == 360
    assert tuple(first["languages"]) == LANGUAGES
    assert tuple(first["strata"]) == STRATA

    first_rows = json.loads(
        (tmp_path / "first" / "dev-tasks.json").read_text(encoding="utf-8")
    )
    second_rows = json.loads(
        (tmp_path / "second" / "dev-tasks.json").read_text(encoding="utf-8")
    )
    assert first_rows == second_rows

    process = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "generate_agent_utility_v2_dev.py"),
            "--surface",
            "confirmation",
            "--out-dir",
            str(tmp_path / "forbidden"),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert process.returncode != 0
    assert "confirmation generation is sealed" in (
        process.stdout + process.stderr
    )


def test_v2_surface_does_not_reuse_b1_task_ids() -> None:
    from benchmarks.agent_utility_v1_catalog import TASKS as B1_TASKS

    b1_ids = {task.task_id for task in B1_TASKS}
    v2_ids = {task.semantic_task_id for task in DEVELOPMENT_TASKS}
    assert b1_ids.isdisjoint(v2_ids)
