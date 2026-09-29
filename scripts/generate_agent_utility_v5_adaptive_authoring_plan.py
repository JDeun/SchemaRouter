"""Build sealed authoring-slot manifests for #430 adaptive shortlist research.

This script freezes only task identities and preregistered stratum/language balance.
It does not generate query text, gold routes, scores, catalogs, or benchmark outcomes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PREREG = ROOT / "benchmarks" / "agent-utility-v5-adaptive-shortlist-preregistration.json"

FORBIDDEN_CONTENT_KEYS = {
    "query", "queries", "task_text", "prompt",
    "required_route", "required_routes", "gold_route", "gold_routes",
    "expected_answer", "executor_state", "tool_output", "tool_outputs",
    "catalog", "catalogs", "candidate_set", "candidate_sets",
    "score", "scores", "label", "labels",
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


def _surface_slots(
    *,
    surface_name: str,
    task_strata: list[str],
    languages: list[str],
    tasks_per_cell: int,
) -> list[dict[str, Any]]:
    slots: list[dict[str, Any]] = []
    for task_stratum in task_strata:
        for language in languages:
            for ordinal in range(1, tasks_per_cell + 1):
                slots.append(
                    {
                        "semantic_task_id": (
                            f"v5-{surface_name}-{task_stratum}-{language}-{ordinal:02d}"
                        ),
                        "surface": surface_name,
                        "task_stratum": task_stratum,
                        "language": language,
                        "ordinal_in_cell": ordinal,
                    }
                )
    return slots


def build_authoring_plan() -> dict[str, Any]:
    prereg = _load_prereg()
    dev = prereg["development_surface"]
    confirmation = prereg["confirmation_surface"]

    task_strata = list(dev["task_strata"])
    languages = list(dev["languages"])
    per_cell = int(dev["tasks_per_stratum_language_cell"])

    dev_slots = _surface_slots(
        surface_name="dev",
        task_strata=task_strata,
        languages=languages,
        tasks_per_cell=per_cell,
    )
    confirmation_slots = _surface_slots(
        surface_name="confirmation",
        task_strata=task_strata,
        languages=languages,
        tasks_per_cell=per_cell,
    )

    if len(dev_slots) != int(dev["unique_semantic_tasks"]):
        raise RuntimeError("adaptive DEV authoring-slot count drifted")
    if len(confirmation_slots) != int(confirmation["unique_semantic_tasks"]):
        raise RuntimeError("adaptive confirmation authoring-slot count drifted")

    all_slots = dev_slots + confirmation_slots
    ids = [row["semantic_task_id"] for row in all_slots]
    if len(ids) != len(set(ids)):
        raise RuntimeError("adaptive authoring semantic_task_id values must be unique")

    for name, rows in (("dev", dev_slots), ("confirmation", confirmation_slots)):
        cell_counts = Counter(
            (row["task_stratum"], row["language"]) for row in rows
        )
        if len(cell_counts) != int(dev["cells"]):
            raise RuntimeError(f"adaptive {name} cell count drifted")
        if set(cell_counts.values()) != {per_cell}:
            raise RuntimeError(f"adaptive {name} cells are not balanced")

    leaked = FORBIDDEN_CONTENT_KEYS.intersection(
        key for row in all_slots for key in row
    )
    if leaked:
        raise RuntimeError(
            "adaptive authoring scaffold leaked sealed content keys: "
            + ", ".join(sorted(leaked))
        )

    return {
        "schema_version": 1,
        "issue": 430,
        "experiment": prereg["experiment"],
        "status": "authoring_slots_only_no_task_content_generated",
        "preregistration_path": str(PREREG.relative_to(ROOT)),
        "preregistration_file_sha256": _file_sha(PREREG),
        "content_generation_authorized": False,
        "dev_tuning_eligible": True,
        "confirmation_tuning_eligible": False,
        "confirmation_content_sealed_until_policy_selected": True,
        "task_strata": task_strata,
        "languages": languages,
        "tasks_per_cell": per_cell,
        "dev_semantic_task_count": len(dev_slots),
        "confirmation_semantic_task_count": len(confirmation_slots),
        "total_semantic_task_count": len(all_slots),
        "dev_slots_sha256": _sha(dev_slots),
        "confirmation_slots_sha256": _sha(confirmation_slots),
        "forbidden_content_keys": sorted(FORBIDDEN_CONTENT_KEYS),
        "dev_slots": dev_slots,
        "confirmation_slots": confirmation_slots,
    }


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
                "dev_semantic_task_count": plan["dev_semantic_task_count"],
                "confirmation_semantic_task_count": plan[
                    "confirmation_semantic_task_count"
                ],
                "dev_slots_sha256": plan["dev_slots_sha256"],
                "confirmation_slots_sha256": plan[
                    "confirmation_slots_sha256"
                ],
                "content_generation_authorized": False,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
