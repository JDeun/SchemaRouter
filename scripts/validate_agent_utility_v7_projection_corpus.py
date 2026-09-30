"""Pre-scoring integrity checks for the #506 projection corpus.

Deliberately narrower than the scorer: it enforces only what must hold before
any outcome is produced, so it can never be tuned by a result.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.agent_utility_generated_common import sha256_json  # noqa: E402
from scripts.agent_utility_v7_projection import (  # noqa: E402
    CONTROL_KEYS,
    PROJECTION_STRATA,
    TASKS_PER_CELL,
    project_observation,
    projection_authoring_slots,
)


def _fail(message: str) -> None:
    raise SystemExit(f"corpus validation failed: {message}")


def validate(
    corpus: dict[str, Any],
    *,
    expected_slots: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    tasks = corpus.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        _fail("no tasks")

    expected_slots = (
        projection_authoring_slots() if expected_slots is None else expected_slots
    )
    if len(tasks) != len(expected_slots):
        _fail(f"task count drifted: expected={len(expected_slots)} actual={len(tasks)}")
    if sha256_json(expected_slots) != corpus.get("authoring_slots_sha256"):
        _fail("authoring slot plan drifted from the frozen plan")
    if sha256_json(tasks) != corpus.get("tasks_sha256"):
        _fail("tasks_sha256 does not match the task rows")

    seen_ids: set[str] = set()
    seen_queries: set[str] = set()
    cells: dict[tuple[str, str], int] = {}

    for task, slot in zip(tasks, expected_slots, strict=True):
        task_id = str(task["semantic_task_id"])
        if task_id != str(slot["semantic_task_id"]):
            _fail(f"semantic task id drifted at {task_id}")
        if task_id in seen_ids:
            _fail(f"duplicate semantic task id: {task_id}")
        seen_ids.add(task_id)

        query = str(task["query"]).strip()
        if not query:
            _fail(f"empty query: {task_id}")
        normalized = " ".join(query.split()).casefold()
        if normalized in seen_queries:
            _fail(f"duplicate query text: {task_id}")
        seen_queries.add(normalized)

        if task["projection_stratum"] != slot["projection_stratum"]:
            _fail(f"stratum drifted: {task_id}")
        if task["language"] != slot["language"]:
            _fail(f"language drifted: {task_id}")
        key = (str(task["projection_stratum"]), str(task["language"]))
        cells[key] = cells.get(key, 0) + 1

        steps = task["executor_fixture"]["steps"]
        if not steps:
            _fail(f"no executor steps: {task_id}")

        available: dict[str, Any] = {}
        for step in steps:
            observation = step["observation"]
            planned = set(step["planned_fields"])
            gold = set(step["gold_fields"])
            raw = set(observation)

            if not planned <= raw:
                _fail(f"planned fields absent from the raw record: {task_id} {step['route_id']}")
            if not gold <= planned:
                _fail(f"gold fields exceed the plan: {task_id} {step['route_id']}")
            if not raw - planned - CONTROL_KEYS:
                # Without competing content the RAW-FULL and PROJECTED arms are
                # the same observation and the comparison measures nothing.
                _fail(f"raw record carries no distractor content: {task_id} {step['route_id']}")

            available.update(
                project_observation(
                    observation,
                    condition="PROJECTED",
                    planned_fields=step["planned_fields"],
                    gold_fields=step["gold_fields"],
                    field_contracts=step.get("field_contracts", {}),
                )
            )

        for fact in task["required_facts"]:
            key_name = str(fact["key"])
            if key_name not in available:
                _fail(f"required fact is unreachable after projection: {task_id} {key_name}")
            if available[key_name] != fact["value"]:
                _fail(f"required fact value disagrees with the record: {task_id} {key_name}")

        for forbidden in task["forbidden_facts"]:
            if forbidden["value"] == available.get(str(forbidden["key"])):
                _fail(f"forbidden value equals the correct value: {task_id} {forbidden['key']}")

    expected_cells = len(PROJECTION_STRATA) * len({slot["language"] for slot in expected_slots})
    if len(cells) != expected_cells:
        _fail(f"stratum x language cells drifted: expected={expected_cells} actual={len(cells)}")
    if set(cells.values()) != {TASKS_PER_CELL}:
        _fail(f"unbalanced cells: {sorted(set(cells.values()))}")

    return {
        "tasks": len(tasks),
        "cells": len(cells),
        "tasks_per_cell": TASKS_PER_CELL,
        "tasks_sha256": corpus["tasks_sha256"],
        "source_identity_sha256": corpus["source_identity_sha256"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", required=True, type=Path)
    args = parser.parse_args()

    corpus = json.loads(args.corpus.read_text(encoding="utf-8"))
    summary = validate(corpus)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
