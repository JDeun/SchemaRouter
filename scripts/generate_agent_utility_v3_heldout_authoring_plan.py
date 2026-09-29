"""Build the deterministic #432 held-out authoring-slot manifest.

This script intentionally DOES NOT generate task text, gold routes, executor states,
tool outputs, catalogs, candidate sets, or scoring data. Those remain sealed until
B2 (#423) is terminal.

The output freezes only independent semantic-task slot identities and their
preregistered task-stratum × language assignment.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PREREG = ROOT / "benchmarks" / "agent-utility-v3-heldout-preregistration.json"

FORBIDDEN_CONTENT_KEYS = {
    "query",
    "queries",
    "task_text",
    "prompt",
    "required_route",
    "required_routes",
    "gold_route",
    "gold_routes",
    "expected_answer",
    "executor_state",
    "executor_states",
    "tool_output",
    "tool_outputs",
    "catalog",
    "catalogs",
    "candidate_set",
    "candidate_sets",
    "score",
    "scores",
    "label",
    "labels",
}


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _sha(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_prereg() -> dict[str, Any]:
    return json.loads(PREREG.read_text(encoding="utf-8"))


def build_authoring_plan() -> dict[str, Any]:
    prereg = _load_prereg()
    surface = prereg["heldout_surface"]
    task_strata = list(surface["task_strata"])
    languages = list(surface["languages"])
    per_cell = int(surface["cross_balance"]["semantic_tasks_per_stratum_language_cell"])

    slots: list[dict[str, Any]] = []
    for task_stratum in task_strata:
        for language in languages:
            for ordinal in range(1, per_cell + 1):
                slots.append(
                    {
                        "semantic_task_id": (
                            f"v3-{task_stratum}-{language}-{ordinal:02d}"
                        ),
                        "task_stratum": task_stratum,
                        "language": language,
                        "ordinal_in_cell": ordinal,
                    }
                )

    expected = int(surface["unique_semantic_tasks"])
    if len(slots) != expected:
        raise RuntimeError(
            f"held-out authoring-slot count drifted: {len(slots)} != {expected}"
        )

    ids = [slot["semantic_task_id"] for slot in slots]
    if len(ids) != len(set(ids)):
        raise RuntimeError("held-out semantic_task_id values must be unique")

    cell_counts = Counter(
        (slot["task_stratum"], slot["language"])
        for slot in slots
    )
    if len(cell_counts) != int(surface["cross_balance"]["cells"]):
        raise RuntimeError(
            f"held-out cell count drifted: {len(cell_counts)}"
        )
    if set(cell_counts.values()) != {per_cell}:
        raise RuntimeError(
            "held-out task-stratum × language cells are not equally balanced"
        )

    plan = {
        "schema_version": 1,
        "issue": 432,
        "benchmark": prereg["benchmark"],
        "status": "authoring_slots_only_content_sealed_until_b2_terminal",
        "preregistration_path": str(PREREG.relative_to(ROOT)),
        "preregistration_file_sha256": _file_sha(PREREG),
        "content_generation_authorized": False,
        "b2_terminal_required_before_content_generation": True,
        "b2_outcomes_used": False,
        "b1_rows_used": False,
        "representation_dev_434_queries_used": False,
        "prior_benchmark_paraphrases_allowed": False,
        "semantic_task_count": len(slots),
        "task_strata": task_strata,
        "languages": languages,
        "tasks_per_cell": per_cell,
        "cell_count": len(cell_counts),
        "slots_sha256": _sha(slots),
        "forbidden_content_keys": sorted(FORBIDDEN_CONTENT_KEYS),
        "slots": slots,
    }

    leaked = FORBIDDEN_CONTENT_KEYS.intersection(
        key
        for slot in slots
        for key in slot
    )
    if leaked:
        raise RuntimeError(
            "authoring-slot scaffold leaked sealed corpus content keys: "
            + ", ".join(sorted(leaked))
        )

    return plan


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    plan = build_authoring_plan()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(plan, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "semantic_task_count": plan["semantic_task_count"],
                "cell_count": plan["cell_count"],
                "slots_sha256": plan["slots_sha256"],
                "content_generation_authorized": plan[
                    "content_generation_authorized"
                ],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
