from __future__ import annotations

import importlib.util
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADAPTIVE_SCRIPT = ROOT / "scripts" / "generate_agent_utility_v5_adaptive_authoring_plan.py"
CORRECTIVE_SCRIPT = ROOT / "scripts" / "generate_agent_utility_v6_corrective_authoring_plan.py"


def _module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_adaptive_authoring_scaffold_balances_dev_and_confirmation() -> None:
    module = _module(ADAPTIVE_SCRIPT, "adaptive_authoring")
    plan = module.build_authoring_plan()

    assert plan["issue"] == 430
    assert plan["dev_semantic_task_count"] == 240
    assert plan["confirmation_semantic_task_count"] == 240
    assert plan["total_semantic_task_count"] == 480
    assert plan["tasks_per_cell"] == 5
    assert plan["content_generation_authorized"] is False
    assert plan["dev_tuning_eligible"] is True
    assert plan["confirmation_tuning_eligible"] is False
    assert plan["confirmation_content_sealed_until_policy_selected"] is True

    for key in ("dev_slots", "confirmation_slots"):
        rows = plan[key]
        assert len(rows) == 240
        ids = [row["semantic_task_id"] for row in rows]
        assert len(ids) == len(set(ids))
        counts = Counter((row["task_stratum"], row["language"]) for row in rows)
        assert len(counts) == 48
        assert set(counts.values()) == {5}

    all_ids = [
        row["semantic_task_id"]
        for key in ("dev_slots", "confirmation_slots")
        for row in plan[key]
    ]
    assert len(all_ids) == len(set(all_ids))


def test_adaptive_authoring_scaffold_contains_no_task_content() -> None:
    module = _module(ADAPTIVE_SCRIPT, "adaptive_authoring_no_content")
    plan = module.build_authoring_plan()
    forbidden = set(plan["forbidden_content_keys"])

    for key in ("dev_slots", "confirmation_slots"):
        for row in plan[key]:
            assert set(row) == {
                "semantic_task_id",
                "surface",
                "task_stratum",
                "language",
                "ordinal_in_cell",
            }
            assert forbidden.isdisjoint(row)


def test_adaptive_authoring_scaffold_is_deterministic() -> None:
    module = _module(ADAPTIVE_SCRIPT, "adaptive_authoring_deterministic")
    first = module.build_authoring_plan()
    second = module.build_authoring_plan()

    assert first == second
    assert len(first["dev_slots_sha256"]) == 64
    assert len(first["confirmation_slots_sha256"]) == 64


def test_corrective_authoring_scaffold_is_balanced_and_sealed() -> None:
    module = _module(CORRECTIVE_SCRIPT, "corrective_authoring")
    plan = module.build_authoring_plan()

    assert plan["issue"] == 431
    assert plan["semantic_task_count"] == 180
    assert plan["tasks_per_cell"] == 6
    assert plan["content_generation_authorized"] is False
    assert plan["execution_authorized"] is False
    assert plan["b2_terminal_required_before_content_generation"] is True

    rows = plan["slots"]
    assert len(rows) == 180
    ids = [row["semantic_task_id"] for row in rows]
    assert len(ids) == len(set(ids))

    counts = Counter((row["task_stratum"], row["language"]) for row in rows)
    assert len(counts) == 30
    assert set(counts.values()) == {6}

    forbidden = set(plan["forbidden_content_keys"])
    for row in rows:
        assert set(row) == {
            "semantic_task_id",
            "task_stratum",
            "language",
            "ordinal_in_cell",
        }
        assert forbidden.isdisjoint(row)


def test_corrective_authoring_scaffold_is_deterministic() -> None:
    module = _module(CORRECTIVE_SCRIPT, "corrective_authoring_deterministic")
    first = module.build_authoring_plan()
    second = module.build_authoring_plan()

    assert first == second
    assert len(first["slots_sha256"]) == 64
