from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmarks.agent_utility_v5_catalog import (  # noqa: E402
    _core_tools,
    build_registry as build_dev_registry,
    build_tasks as build_dev_tasks,
)
from benchmarks.agent_utility_v5_structural_confirmation import (  # noqa: E402
    build_confirmation_registry as build_v2_registry,
    build_confirmation_tasks as build_v2_tasks,
)
from benchmarks.agent_utility_v5_structural_fixed_k3_confirmation import (  # noqa: E402
    CONFIRMATION_CATALOG_SIZES,
    CONFIRMATION_LANGUAGES,
    CONFIRMATION_STRATA,
    CONFIRMATION_TASKS_PER_CELL,
    build_fixed_k3_confirmation_registry,
    build_fixed_k3_confirmation_tasks,
)

PREREG = (
    ROOT
    / "benchmarks"
    / "agent-utility-v5-structural-fixed-k3-preregistration.json"
)


def _normalize(value: str) -> str:
    return " ".join(value.casefold().split())


def _routes(registry: object) -> set[str]:
    return {
        f"{tool.key}.{endpoint.name}"
        for tool in registry.tools()
        for endpoint in tool.endpoints
    }


def test_fixed_k3_candidate_is_frozen_before_confirmation() -> None:
    prereg = json.loads(PREREG.read_text(encoding="utf-8"))
    candidate = prereg["fixed_candidate"]

    assert prereg["status"] == (
        "preregistered_before_fresh_confirmation_generation"
    )
    assert candidate["id"] == "STRUCT-4.5-1.5-K3"
    assert candidate["shortlist_k"] == 3
    assert candidate["weights_retunable"] is False
    assert candidate["k_retunable"] is False
    assert prereg["confirmation_surface"]["tuning_eligible"] is False


def test_fixed_k3_confirmation_surface_is_balanced_and_unique() -> None:
    tasks = build_fixed_k3_confirmation_tasks()

    assert len(tasks) == 240
    assert len({task["task_id"] for task in tasks}) == 240
    assert len({task["query"] for task in tasks}) == 240

    counts = Counter(
        (task["task_stratum"], task["language"])
        for task in tasks
    )
    assert len(counts) == (
        len(CONFIRMATION_STRATA)
        * len(CONFIRMATION_LANGUAGES)
    )
    assert set(counts.values()) == {
        CONFIRMATION_TASKS_PER_CELL
    }


def test_fixed_k3_queries_do_not_reuse_prior_surfaces() -> None:
    fresh = {
        _normalize(str(task["query"]))
        for task in build_fixed_k3_confirmation_tasks()
    }
    prior = {
        _normalize(str(task["query"]))
        for task in build_dev_tasks()
    }
    prior.update(
        _normalize(str(task["query"]))
        for task in build_v2_tasks()
    )

    assert fresh.isdisjoint(prior)


def test_fixed_k3_catalogs_are_nested_and_auxiliary_routes_are_fresh() -> None:
    canonical = {
        f"{tool.key}.{endpoint.name}"
        for tool in _core_tools()
        for endpoint in tool.endpoints
    }
    prior = (
        _routes(build_dev_registry(500))
        | _routes(build_v2_registry(500))
    )

    previous: set[str] | None = None
    for size in CONFIRMATION_CATALOG_SIZES:
        current = _routes(
            build_fixed_k3_confirmation_registry(size)
        )

        assert len(current) == size
        assert current & prior == canonical
        if previous is not None:
            assert previous < current
        previous = current
