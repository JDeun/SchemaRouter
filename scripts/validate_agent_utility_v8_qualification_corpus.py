"""Fail-closed validator for the #510 runtime-qualification corpus."""
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
from scripts.agent_utility_prior_query_guard import normalize_query  # noqa: E402
from scripts.generate_agent_utility_v8_qualification_corpus import (  # noqa: E402
    QUALIFICATION_EVIDENCE_CLASS,
    QUALIFICATION_SURFACE,
    _projection_queries,
    qualification_authoring_slots,
)


def validate_qualification_corpus(corpus: dict[str, Any]) -> dict[str, Any]:
    expected_slots = qualification_authoring_slots()
    expected_ids = [str(slot["semantic_task_id"]) for slot in expected_slots]
    tasks = list(corpus.get("tasks", []))

    if corpus.get("surface") != QUALIFICATION_SURFACE:
        raise ValueError("wrong qualification surface")
    if corpus.get("evidence_class") != QUALIFICATION_EVIDENCE_CLASS:
        raise ValueError("wrong qualification evidence class")
    if len(tasks) != len(expected_slots):
        raise ValueError(
            f"qualification corpus has {len(tasks)} tasks; expected {len(expected_slots)}"
        )
    if corpus.get("expected_episode_count") != len(expected_slots):
        raise ValueError("qualification expected_episode_count drifted")
    if corpus.get("tasks_sha256") != sha256_json(tasks):
        raise ValueError("qualification tasks_sha256 mismatch")

    task_ids = [str(task.get("semantic_task_id")) for task in tasks]
    if task_ids != expected_ids:
        raise ValueError("qualification task identifier/order drifted")

    cell_pairs = {
        (str(task.get("projection_stratum")), str(task.get("language")))
        for task in tasks
    }
    if len(cell_pairs) != len(expected_slots):
        raise ValueError("qualification surface must contain one task per stratum/language cell")

    queries = {normalize_query(str(task.get("query", ""))) for task in tasks}
    for name, prior in {
        "projection_506": _projection_queries("P"),
        "successor_510": _projection_queries("S"),
    }.items():
        overlap = queries & prior
        if overlap:
            raise ValueError(
                f"qualification surface overlaps {name}: {len(overlap)} queries"
            )

    return {
        "tasks": len(tasks),
        "tasks_sha256": corpus["tasks_sha256"],
        "surface": QUALIFICATION_SURFACE,
        "evidence_class": QUALIFICATION_EVIDENCE_CLASS,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", required=True, type=Path)
    args = parser.parse_args()
    corpus = json.loads(args.corpus.read_text(encoding="utf-8"))
    print(json.dumps(validate_qualification_corpus(corpus), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
