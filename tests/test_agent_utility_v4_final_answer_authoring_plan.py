from __future__ import annotations

import importlib.util
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "generate_agent_utility_v4_final_answer_authoring_plan.py"


def _module():
    spec = importlib.util.spec_from_file_location("final_answer_authoring_plan", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_v4_authoring_plan_freezes_exact_balanced_slots_only() -> None:
    module = _module()
    plan = module.build_authoring_plan()

    assert plan["issue"] == 424
    assert plan["semantic_task_count"] == 144
    assert plan["cell_count"] == 36
    assert plan["tasks_per_cell"] == 4
    assert plan["content_generation_authorized"] is False
    assert plan["answer_inference_authorized"] is False
    assert plan["b2_terminal_required_before_content_generation"] is True
    assert plan["b2_terminal_required_before_answer_inference"] is True
    assert plan["b2_outcomes_used"] is False

    slots = plan["slots"]
    assert len(slots) == 144

    ids = [slot["semantic_task_id"] for slot in slots]
    assert len(ids) == len(set(ids))

    cell_counts = Counter(
        (slot["answer_task_stratum"], slot["language"])
        for slot in slots
    )
    assert len(cell_counts) == 36
    assert set(cell_counts.values()) == {4}

    assert Counter(slot["answer_task_stratum"] for slot in slots) == {
        stratum: 24 for stratum in plan["answer_task_strata"]
    }
    assert Counter(slot["language"] for slot in slots) == {
        language: 24 for language in plan["languages"]
    }


def test_v4_authoring_plan_contains_no_answer_benchmark_content() -> None:
    module = _module()
    plan = module.build_authoring_plan()
    forbidden = set(plan["forbidden_content_keys"])

    assert forbidden
    for slot in plan["slots"]:
        assert set(slot) == {
            "semantic_task_id",
            "answer_task_stratum",
            "language",
            "ordinal_in_cell",
        }
        assert forbidden.isdisjoint(slot)


def test_v4_authoring_plan_is_deterministic() -> None:
    module = _module()

    first = module.build_authoring_plan()
    second = module.build_authoring_plan()

    assert first == second
    assert len(first["slots_sha256"]) == 64
    assert first["slots_sha256"] == second["slots_sha256"]


def test_v4_authoring_plan_preserves_independence_guards() -> None:
    module = _module()
    plan = module.build_authoring_plan()

    assert plan["b1_b2_wording_used"] is False
    assert plan["issue_432_rows_used"] is False
