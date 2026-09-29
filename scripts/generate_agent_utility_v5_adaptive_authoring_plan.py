"""Build the #430 DEV authoring scaffold without generating task content."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

STRATA = (
    "clear_single_tool",
    "sibling_operation_ambiguity",
    "semantically_adjacent_distractors",
    "multi_step_first_hop",
    "typed_numeric_units",
    "read_write_siblings",
    "near_domain_unsupported",
    "out_of_domain",
)
LANGUAGES = ("en", "ko", "es", "ja", "de", "mixed")
TASKS_PER_CELL = 5
EXPECTED_SLOT_COUNT = len(STRATA) * len(LANGUAGES) * TASKS_PER_CELL


def build_authoring_plan() -> dict[str, Any]:
    slots = [
        {
            "slot_id": f"adaptive-dev-{stratum}-{language}-{index:02d}",
            "stratum": stratum,
            "language": language,
            "cell_index": index,
            "content_state": "unwritten",
        }
        for stratum in STRATA
        for language in LANGUAGES
        for index in range(1, TASKS_PER_CELL + 1)
    ]
    return {
        "schema_version": 1,
        "cycle": "0.14-end-to-end-agent-utility",
        "experiment": "adaptive-capability-shortlist-depth-v1",
        "issue": 430,
        "surface": "development-authoring-scaffold",
        "status": "scaffold_only_no_task_content",
        "corpus_generated": False,
        "scoring_authorized": False,
        "confirmation_surface_opened": False,
        "expected_semantic_task_count": EXPECTED_SLOT_COUNT,
        "strata": list(STRATA),
        "languages": list(LANGUAGES),
        "tasks_per_stratum_language_cell": TASKS_PER_CELL,
        "forbidden_slot_fields": [
            "query",
            "required_routes",
            "ranking",
            "score",
            "condition",
            "result",
        ],
        "provenance_constraints": {
            "b1_row_content_allowed": False,
            "b2_row_content_allowed": False,
            "representation_dev_434_queries_allowed": False,
            "heldout_432_rows_allowed": False,
            "final_answer_424_rows_allowed": False,
            "prior_benchmark_paraphrases_allowed": False,
        },
        "slots": slots,
    }


def validate_authoring_plan(plan: dict[str, Any]) -> None:
    slots = plan["slots"]
    if len(slots) != EXPECTED_SLOT_COUNT:
        raise RuntimeError(
            f"adaptive DEV slot count drifted: {len(slots)} != {EXPECTED_SLOT_COUNT}"
        )

    ids = [str(row["slot_id"]) for row in slots]
    if len(ids) != len(set(ids)):
        raise RuntimeError("adaptive DEV slot IDs must be unique")

    counts = Counter((row["stratum"], row["language"]) for row in slots)
    expected = Counter(
        {
            (stratum, language): TASKS_PER_CELL
            for stratum in STRATA
            for language in LANGUAGES
        }
    )
    if counts != expected:
        raise RuntimeError("adaptive DEV stratum/language balance drifted")

    forbidden = set(plan["forbidden_slot_fields"])
    for row in slots:
        leaked = forbidden.intersection(row)
        if leaked:
            raise RuntimeError(
                f"authoring scaffold leaked task content in {row['slot_id']}: "
                f"{sorted(leaked)}"
            )
        if row["content_state"] != "unwritten":
            raise RuntimeError(
                f"authoring slot must remain unwritten: {row['slot_id']}"
            )

    if plan["corpus_generated"] is not False:
        raise RuntimeError("authoring scaffold must not generate a DEV corpus")
    if plan["scoring_authorized"] is not False:
        raise RuntimeError("authoring scaffold must not authorize scoring")
    if plan["confirmation_surface_opened"] is not False:
        raise RuntimeError("confirmation must remain sealed")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    plan = build_authoring_plan()
    validate_authoring_plan(plan)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(plan, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "issue": plan["issue"],
                "surface": plan["surface"],
                "slots": len(plan["slots"]),
                "corpus_generated": plan["corpus_generated"],
                "scoring_authorized": plan["scoring_authorized"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
