from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from benchmarks.agent_utility_v1_catalog import (
    CATALOG_SIZES,
    TASKS,
    build_registry,
)
from schemarouter import SchemaPlanner

ROOT = Path(__file__).resolve().parents[1]
EVALUATOR = (
    ROOT
    / "scripts"
    / "evaluate_structural_fixed3_agent_utility.py"
)
AGGREGATOR = (
    ROOT
    / "scripts"
    / "aggregate_structural_fixed3_agent_utility.py"
)


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


evaluator = _load(EVALUATOR, "structural_k3_agent_eval")
aggregator = _load(AGGREGATOR, "structural_k3_agent_aggregate")


def test_structural_candidate_weights_are_frozen() -> None:
    evaluator._assert_frozen_structural_candidate()


def test_structural_k3_is_exact_ranking_prefix_of_k5() -> None:
    for catalog_size in CATALOG_SIZES:
        registry = build_registry(catalog_size)
        planner = SchemaPlanner(
            registry,
            structural_retrieval=True,
        )
        for task in TASKS:
            top5 = planner.retrieve(task.query, k=5)
            top3 = planner.retrieve(task.query, k=3)
            assert [
                candidate.route_id
                for candidate in top3.candidates
            ] == [
                candidate.route_id
                for candidate in top5.candidates[:3]
            ]
            assert evaluator._structural_routes(
                registry,
                task.query,
                k=3,
            ) == sorted(
                candidate.route_id
                for candidate in top5.candidates[:3]
            )


def test_unknown_task_fails_before_model_load() -> None:
    with pytest.raises(ValueError, match="unknown frozen task"):
        evaluator.evaluate(
            catalog_sizes=(20,),
            task_ids={"not-a-frozen-task"},
        )


def test_candidate_coverage_reports_required_route_recall() -> None:
    rows = [
        {
            "required_routes": ["a", "b"],
            "candidate_history": [["a", "b", "c"]],
        },
        {
            "required_routes": ["a", "d"],
            "candidate_history": [["a", "c", "e"]],
        },
    ]

    result = aggregator._candidate_coverage(rows)

    assert result["required_route_recall"] == 0.75
    assert result["all_required_full_coverage"] == 0.5


def test_expected_episode_contract_is_184() -> None:
    assert aggregator.EXPECTED_EPISODES == 184
    assert len(TASKS) == 23
    assert len(CATALOG_SIZES) == 4
    assert len(aggregator.CONDITIONS) == 2
