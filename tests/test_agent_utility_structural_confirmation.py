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
    CONFIRMATION_CATALOG_SIZES,
    CONFIRMATION_LANGUAGES,
    CONFIRMATION_STRATA,
    CONFIRMATION_TASKS_PER_CELL,
    build_confirmation_registry,
    build_confirmation_tasks,
)
from schemarouter import SchemaPlanner  # noqa: E402
from schemarouter.planner import (  # noqa: E402
    _STRUCTURAL_OPERATION_FAMILY_BONUS,
    _STRUCTURAL_TOOL_IDENTIFIER_BONUS,
)

GENERATOR = (
    ROOT
    / "scripts"
    / "generate_agent_utility_v5_structural_confirmation.py"
)
PREREG = (
    ROOT
    / "benchmarks"
    / "agent-utility-v5-structural-retrieval-v2-preregistration.json"
)


def _load_generator():
    spec = importlib.util.spec_from_file_location(
        "structural_confirmation_generator",
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


def test_confirmation_surface_is_balanced_and_unique() -> None:
    tasks = build_confirmation_tasks()

    assert len(tasks) == 240
    assert len({task["task_id"] for task in tasks}) == 240
    assert len({task["query"] for task in tasks}) == 240

    counts = Counter(
        (
            task["task_stratum"],
            task["language"],
        )
        for task in tasks
    )
    assert len(counts) == 48
    assert set(counts.values()) == {
        CONFIRMATION_TASKS_PER_CELL
    }
    assert {
        task["task_stratum"]
        for task in tasks
    } == set(CONFIRMATION_STRATA)
    assert {
        task["language"]
        for task in tasks
    } == set(CONFIRMATION_LANGUAGES)


def test_confirmation_queries_have_no_exact_dev_overlap() -> None:
    confirmation = {
        " ".join(task["query"].casefold().split())
        for task in build_confirmation_tasks()
    }
    dev = {
        " ".join(task["query"].casefold().split())
        for task in dev_catalog.build_tasks()
    }

    assert confirmation.isdisjoint(dev)


def test_confirmation_catalogs_are_nested_and_auxiliary_ids_are_fresh() -> None:
    dev_routes = _routes(dev_catalog.build_registry(500))
    canonical = _routes(dev_catalog.build_registry(100))
    prior: set[str] | None = None

    for size in CONFIRMATION_CATALOG_SIZES:
        registry = build_confirmation_registry(size)
        routes = _routes(registry)

        assert len(routes) == size
        assert routes & dev_routes == canonical
        if prior is not None:
            assert prior < routes
        prior = routes


def test_confirmation_freeze_records_independence(
    tmp_path: Path,
) -> None:
    generator = _load_generator()
    manifest = generator.freeze_confirmation(tmp_path)

    assert manifest["status"] == "frozen_before_scoring"
    assert manifest["semantic_task_count"] == 240
    assert manifest["cell_count"] == 48
    assert manifest[
        "exact_normalized_dev_query_overlap_count"
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
    assert all(
        item["shared_dev_route_count"] == 30
        and item[
            "shared_dev_routes_are_canonical_only"
        ]
        is True
        for item in manifest["catalogs"].values()
    )


def test_v2_prereg_matches_core_and_default_remains_off() -> None:
    prereg = json.loads(PREREG.read_text(encoding="utf-8"))
    fixed = prereg["fixed_candidate"]

    assert float(
        fixed["tool_identifier_bonus"]
    ) == _STRUCTURAL_TOOL_IDENTIFIER_BONUS
    assert float(
        fixed["operation_family_bonus"]
    ) == _STRUCTURAL_OPERATION_FAMILY_BONUS
    assert fixed["schema_specificity_tiebreak"] is True

    registry = build_confirmation_registry(100)
    assert SchemaPlanner(registry).structural_retrieval is False
    assert (
        SchemaPlanner(
            registry,
            structural_retrieval=True,
        ).structural_retrieval
        is True
    )
