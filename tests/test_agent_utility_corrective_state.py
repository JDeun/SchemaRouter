from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from benchmarks.agent_utility_b2_catalog import build_registry

ROOT = Path(__file__).resolve().parents[1]
STATE_MODULE = ROOT / "scripts" / "agent_utility_v6_state.py"
PLAN_MODULE = (
    ROOT
    / "scripts"
    / "generate_agent_utility_v6_corrective_authoring_plan.py"
)


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


state_api = _load(STATE_MODULE, "corrective_state")


def test_corrective_state_retains_typed_metadata_not_free_text() -> None:
    registry = build_registry(20)
    state = state_api.empty_state(
        "Search for a material and then read its current modulus."
    )

    state = state_api.update_state(
        state,
        registry=registry,
        route_id="materials.search",
        observation={
            "status": "ok",
            "material_id": "MAT-SEARCH-1",
            "formula": "LiNi0.8Mn0.1Co0.1O2",
        },
        error=None,
        task_incomplete=True,
    )

    assert state["executed_registered_route_ids"] == ["materials.search"]
    assert "material.id" in state["observation_semantic_ids"]
    assert "MAT-SEARCH-1" in state["stable_observed_identifiers"]
    assert state["last_execution_status"] == "ok"
    assert state["last_error_class"] is None

    rendered = state_api.render_retrieval_query(state)
    assert rendered.count(state["original_query"]) == 1
    assert "[EXECUTION_STATE]" in rendered
    assert "MAT-SEARCH-1" in rendered
    assert "LiNi0.8Mn0.1Co0.1O2" not in rendered


def test_corrective_state_projects_unit_dimension_without_numeric_value() -> None:
    registry = build_registry(20)
    state = state_api.empty_state("Read the material modulus.")

    state = state_api.update_state(
        state,
        registry=registry,
        route_id="materials.current",
        observation={
            "status": "ok",
            "youngs_modulus": 125.0,
            "unit": "GPa",
        },
        error=None,
        task_incomplete=False,
    )

    assert "material.youngs_modulus" in state["observation_semantic_ids"]
    assert "GPa" in state["observation_units"]
    assert "elastic_modulus" in state["observation_dimensions"]
    assert "number" in state["observation_value_types"]
    assert state["task_incomplete_boolean"] is False

    rendered = state_api.render_retrieval_query(state)
    assert "material.youngs_modulus" in rendered
    assert "elastic_modulus" in rendered
    assert "125.0" not in rendered


def test_corrective_state_normalizes_error_class_and_registered_attempt() -> None:
    registry = build_registry(20)
    state = state_api.empty_state("Update the inventory item.")

    state = state_api.update_state(
        state,
        registry=registry,
        route_id="inventory.update",
        observation={
            "status": "error",
            "error": "missing_required_argument:item_id",
        },
        error="missing_required_argument:item_id",
        task_incomplete=True,
    )

    assert state["executed_registered_route_ids"] == ["inventory.update"]
    assert state["last_execution_status"] == "error"
    assert state["last_error_class"] == "missing_required_argument"
    rendered = state_api.render_retrieval_query(state)
    assert "missing_required_argument:item_id" not in rendered
    assert '"last_error_class":"missing_required_argument"' in rendered


def test_corrective_state_rejects_hidden_ground_truth_fields() -> None:
    state = state_api.empty_state("Continue the task.")
    state["gold_next_route_id"] = "materials.current"

    with pytest.raises(ValueError):
        state_api.validate_state(state)


def test_corrective_state_unknown_route_is_not_registered_execution() -> None:
    registry = build_registry(20)
    state = state_api.empty_state("Try an unavailable route.")

    state = state_api.update_state(
        state,
        registry=registry,
        route_id="hidden.future_tool",
        observation={
            "status": "error",
            "error": "unknown_tool",
        },
        error="unknown_tool",
        task_incomplete=True,
    )

    assert state["executed_registered_route_ids"] == []
    assert state["stable_observed_identifiers"] == []
    assert state["last_error_class"] == "unknown_tool"


def test_corrective_authoring_plan_is_balanced_and_content_sealed() -> None:
    plan_api = _load(PLAN_MODULE, "corrective_plan")
    plan = plan_api.build_authoring_plan()

    assert plan["semantic_task_count"] == 180
    assert plan["cell_count"] == 30
    assert plan["tasks_per_cell"] == 6
    assert plan["slots_sha256"] == (
        "9ef60a639b971731e257e921087d4741"
        "f7c7fa9ec521e1d30d777fa230550946"
    )
    assert plan["content_generation_authorized"] is False
    assert plan["execution_authorized"] is False
    assert plan["b2_terminal_required"] is True
    assert all(
        not set(slot).intersection(plan_api.FORBIDDEN_CONTENT_KEYS)
        for slot in plan["slots"]
    )
