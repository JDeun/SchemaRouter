from __future__ import annotations

import importlib.util
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "generate_agent_utility_v3_heldout_authoring_plan.py"


def _module():
    spec = importlib.util.spec_from_file_location("heldout_authoring_plan", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_v3_authoring_plan_freezes_exact_balanced_slots_only() -> None:
    module = _module()
    plan = module.build_authoring_plan()

    assert plan["issue"] == 432
    assert plan["semantic_task_count"] == 780
    assert plan["cell_count"] == 78
    assert plan["tasks_per_cell"] == 10
    assert plan["content_generation_authorized"] is False
    assert plan["b2_terminal_required_before_content_generation"] is True
    assert plan["b2_outcomes_used"] is False

    slots = plan["slots"]
    assert len(slots) == 780

    ids = [slot["semantic_task_id"] for slot in slots]
    assert len(ids) == len(set(ids))

    cell_counts = Counter(
        (slot["task_stratum"], slot["language"])
        for slot in slots
    )
    assert len(cell_counts) == 78
    assert set(cell_counts.values()) == {10}

    assert Counter(slot["task_stratum"] for slot in slots) == {
        stratum: 60 for stratum in plan["task_strata"]
    }
    assert Counter(slot["language"] for slot in slots) == {
        language: 130 for language in plan["languages"]
    }


def test_v3_authoring_plan_contains_no_heldout_task_content() -> None:
    module = _module()
    plan = module.build_authoring_plan()
    forbidden = set(plan["forbidden_content_keys"])

    assert forbidden
    for slot in plan["slots"]:
        assert set(slot) == {
            "semantic_task_id",
            "task_stratum",
            "language",
            "ordinal_in_cell",
        }
        assert forbidden.isdisjoint(slot)


def test_v3_authoring_plan_is_deterministic() -> None:
    module = _module()

    first = module.build_authoring_plan()
    second = module.build_authoring_plan()

    assert first == second
    assert len(first["slots_sha256"]) == 64
    assert first["slots_sha256"] == second["slots_sha256"]


def test_v3_authoring_plan_preserves_independence_guards() -> None:
    module = _module()
    plan = module.build_authoring_plan()

    assert plan["b1_rows_used"] is False
    assert plan["representation_dev_434_queries_used"] is False
    assert plan["prior_benchmark_paraphrases_allowed"] is False
