from __future__ import annotations

import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

from scripts.generate_agent_utility_v5_adaptive_authoring_plan import (
    EXPECTED_SLOT_COUNT,
    LANGUAGES,
    STRATA,
    TASKS_PER_CELL,
    build_authoring_plan,
    validate_authoring_plan,
)

ROOT = Path(__file__).resolve().parents[1]


def test_adaptive_authoring_plan_has_exact_preregistered_balance() -> None:
    plan = build_authoring_plan()
    validate_authoring_plan(plan)

    assert EXPECTED_SLOT_COUNT == 240
    assert len(plan["slots"]) == 240
    counts = Counter(
        (row["stratum"], row["language"])
        for row in plan["slots"]
    )
    assert counts == Counter(
        {
            (stratum, language): TASKS_PER_CELL
            for stratum in STRATA
            for language in LANGUAGES
        }
    )


def test_adaptive_authoring_plan_contains_no_task_content_or_scores() -> None:
    plan = build_authoring_plan()
    forbidden = set(plan["forbidden_slot_fields"])

    assert plan["corpus_generated"] is False
    assert plan["scoring_authorized"] is False
    assert plan["confirmation_surface_opened"] is False
    assert all(row["content_state"] == "unwritten" for row in plan["slots"])
    assert all(not forbidden.intersection(row) for row in plan["slots"])


def test_adaptive_authoring_plan_preserves_independence_guards() -> None:
    plan = build_authoring_plan()
    constraints = plan["provenance_constraints"]

    assert constraints
    assert all(value is False for value in constraints.values())


def test_adaptive_authoring_plan_cli_is_deterministic(tmp_path: Path) -> None:
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    command = [
        sys.executable,
        str(ROOT / "scripts" / "generate_agent_utility_v5_adaptive_authoring_plan.py"),
    ]

    for output in (first, second):
        process = subprocess.run(
            [*command, "--out", str(output)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        assert process.returncode == 0, process.stderr

    first_data = json.loads(first.read_text(encoding="utf-8"))
    second_data = json.loads(second.read_text(encoding="utf-8"))
    assert first_data == second_data
    assert first_data["expected_semantic_task_count"] == 240
