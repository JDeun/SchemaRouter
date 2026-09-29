from __future__ import annotations

import importlib.util
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmarks.agent_utility_v5_catalog import (  # noqa: E402
    _READ_WRITE_PAIRS,
    CATALOG_SIZES,
    LANGUAGES,
    STRATA,
    TASKS_PER_CELL,
    build_registry,
    build_tasks,
)

GENERATOR = ROOT / "scripts" / "generate_agent_utility_v5_adaptive_dev.py"


def _load_generator():
    spec = importlib.util.spec_from_file_location("adaptive_dev_generator", GENERATOR)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_adaptive_dev_surface_is_240_unique_one_language_tasks() -> None:
    tasks = build_tasks()

    assert len(tasks) == 240
    assert len({task["task_id"] for task in tasks}) == 240
    assert len({task["query"] for task in tasks}) == 240
    assert {task["language"] for task in tasks} == set(LANGUAGES)
    assert {task["task_stratum"] for task in tasks} == set(STRATA)

    counts = Counter(
        (task["task_stratum"], task["language"])
        for task in tasks
    )
    assert len(counts) == len(STRATA) * len(LANGUAGES) == 48
    assert set(counts.values()) == {TASKS_PER_CELL}


def test_adaptive_dev_supported_and_unsupported_gold_contracts() -> None:
    tasks = build_tasks()
    supported = set(STRATA[:-2])
    unsupported = set(STRATA[-2:])

    assert all(
        task["required_route_ids"]
        for task in tasks
        if task["task_stratum"] in supported
    )
    assert all(
        not task["required_route_ids"]
        for task in tasks
        if task["task_stratum"] in unsupported
    )


def test_adaptive_catalogs_are_exact_and_nested() -> None:
    prior_routes: set[str] | None = None

    for size in CATALOG_SIZES:
        registry = build_registry(size)
        routes = {
            f"{tool.key}.{endpoint.name}"
            for tool in registry.tools()
            for endpoint in tool.endpoints
        }

        assert len(routes) == size
        if prior_routes is not None:
            assert prior_routes < routes
        prior_routes = routes


def test_adaptive_dev_freeze_precedes_scoring_and_has_no_exact_prior_overlap(
    tmp_path: Path,
) -> None:
    generator = _load_generator()
    manifest = generator.freeze_dev(tmp_path)

    assert manifest["status"] == "frozen_before_scoring"
    assert manifest["semantic_task_count"] == 240
    assert manifest["task_rows"] == 240
    assert manifest["cell_count"] == 48
    assert manifest["tasks_per_cell"] == 5
    assert manifest["exact_prior_query_overlap_count"] == 0
    assert set(manifest["catalogs"]) == {"100", "250", "500"}
    assert (tmp_path / "freeze-manifest.json").is_file()
    assert (tmp_path / "dev-tasks.json").is_file()
    for size in CATALOG_SIZES:
        assert (tmp_path / f"catalog-{size}.json").is_file()


def test_read_write_pairs_match_endpoint_authority() -> None:
    registry = build_registry(100)
    lookup = {
        f"{tool.key}.{endpoint.name}": endpoint
        for tool in registry.tools()
        for endpoint in tool.endpoints
    }

    for read_route, write_route in _READ_WRITE_PAIRS:
        assert lookup[read_route].read_only is True
        assert lookup[write_route].read_only is False
