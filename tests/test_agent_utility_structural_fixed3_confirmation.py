from __future__ import annotations

import importlib.util
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmarks import agent_utility_v5_catalog as dev_catalog  # noqa: E402
from benchmarks.agent_utility_v5_structural_confirmation import (  # noqa: E402
    build_confirmation_registry,
    build_confirmation_tasks,
)
from benchmarks.agent_utility_v5_structural_fixed3_confirmation import (  # noqa: E402
    FIXED3_CONFIRM_CATALOG_SIZES,
    FIXED3_CONFIRM_LANGUAGES,
    FIXED3_CONFIRM_STRATA,
    FIXED3_CONFIRM_TASKS_PER_CELL,
    build_fixed3_confirmation_registry,
    build_fixed3_confirmation_tasks,
)
from schemarouter import SchemaPlanner  # noqa: E402

GENERATOR = (
    ROOT
    / "scripts"
    / "generate_agent_utility_v5_structural_fixed3_confirmation.py"
)
PREREG = (
    ROOT
    / "benchmarks"
    / "agent-utility-v5-structural-fixed3-v4-preregistration.json"
)


def _load_generator():
    spec = importlib.util.spec_from_file_location(
        "fixed3_confirmation_generator",
        GENERATOR,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _routes(registry) -> set[str]:
    return {
        f"{tool.key}.{endpoint.name}"
        for tool in registry.tools()
        for endpoint in tool.endpoints
    }


def _normalized_queries(tasks) -> set[str]:
    return {
        " ".join(str(task["query"]).casefold().split())
        for task in tasks
    }


def test_fixed3_confirmation_surface_is_balanced_and_unique() -> None:
    tasks = build_fixed3_confirmation_tasks()

    assert len(tasks) == 240
    assert len({task["task_id"] for task in tasks}) == 240
    assert len({task["query"] for task in tasks}) == 240

    counts = Counter(
        (task["task_stratum"], task["language"])
        for task in tasks
    )
    assert len(counts) == 48
    assert set(counts.values()) == {
        FIXED3_CONFIRM_TASKS_PER_CELL
    }
    assert {
        task["task_stratum"]
        for task in tasks
    } == set(FIXED3_CONFIRM_STRATA)
    assert {
        task["language"]
        for task in tasks
    } == set(FIXED3_CONFIRM_LANGUAGES)


def test_fixed3_confirmation_queries_are_fresh() -> None:
    current = _normalized_queries(
        build_fixed3_confirmation_tasks()
    )
    dev = _normalized_queries(dev_catalog.build_tasks())
    prior = _normalized_queries(build_confirmation_tasks())

    assert current.isdisjoint(dev)
    assert current.isdisjoint(prior)


def test_fixed3_confirmation_auxiliary_routes_are_fresh() -> None:
    canonical = {
        f"{tool.key}.{endpoint.name}"
        for tool in dev_catalog._core_tools()  # noqa: SLF001
        for endpoint in tool.endpoints
    }
    dev_routes = _routes(dev_catalog.build_registry(500))
    prior_routes = _routes(build_confirmation_registry(500))

    previous: set[str] | None = None
    for size in FIXED3_CONFIRM_CATALOG_SIZES:
        routes = _routes(
            build_fixed3_confirmation_registry(size)
        )
        assert len(routes) == size
        assert routes & dev_routes == canonical
        assert routes & prior_routes == canonical
        if previous is not None:
            assert previous < routes
        previous = routes


def test_fixed3_prereg_is_frozen_before_surface_generation() -> None:
    prereg = json.loads(PREREG.read_text(encoding="utf-8"))

    assert prereg["status"] == (
        "preregistered_before_fresh_confirmation_surface_generation"
    )
    assert prereg["fixed_depth_candidate"]["k"] == 3
    assert prereg["fixed_depth_candidate"]["adaptive"] is False
    assert prereg["confirmation_surface"]["must_be_fresh"] is True
    assert prereg["confirmation_surface"][
        "structural_v2_confirmation_reuse_allowed"
    ] is False
    assert prereg["confirmation_surface"][
        "adaptive_dev_reuse_allowed"
    ] is False


def test_fixed3_confirmation_freeze_records_independence(
    tmp_path: Path,
) -> None:
    generator = _load_generator()
    manifest = generator.freeze_fixed3_confirmation(tmp_path)

    assert manifest["status"] == "frozen_before_scoring"
    assert manifest["semantic_task_count"] == 240
    assert manifest["cell_count"] == 48
    assert manifest[
        "exact_normalized_adaptive_dev_query_overlap_count"
    ] == 0
    assert manifest[
        "exact_normalized_structural_v2_confirmation_query_overlap_count"
    ] == 0
    assert manifest[
        "confirmation_rows_inspected_before_freeze"
    ] is False
    assert manifest[
        "confirmation_metrics_used_for_tuning"
    ] is False
    assert set(manifest["catalogs"]) == {
        "100",
        "250",
        "500",
    }


def test_structural_retrieval_default_remains_disabled() -> None:
    registry = build_fixed3_confirmation_registry(100)
    assert SchemaPlanner(registry).structural_retrieval is False
    assert (
        SchemaPlanner(
            registry,
            structural_retrieval=True,
        ).structural_retrieval
        is True
    )
