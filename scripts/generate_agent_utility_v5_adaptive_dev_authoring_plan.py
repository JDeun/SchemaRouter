"""Build the deterministic #430 adaptive-shortlist DEV authoring slots.

This script intentionally does not generate query text, gold routes, catalogs,
rankings, scores, or evaluation results. It freezes only semantic-task slot
identities and their preregistered task-stratum x language assignments.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PREREG = (
    ROOT
    / "benchmarks"
    / "agent-utility-v5-adaptive-shortlist-preregistration.json"
)

FORBIDDEN_CONTENT_KEYS = {
    "query",
    "queries",
    "task_text",
    "prompt",
    "required_route",
    "required_routes",
    "required_route_ids",
    "gold_route",
    "gold_routes",
    "catalog",
    "catalogs",
    "ranking",
    "rankings",
    "score",
    "scores",
    "schema_tokens",
    "label",
    "labels",
    "result",
    "results",
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


def build_authoring_plan() -> dict[str, Any]:
    prereg = json.loads(PREREG.read_text(encoding="utf-8"))
    surface = prereg["development_surface"]
    strata = list(surface["task_strata"])
    languages = list(surface["languages"])
    per_cell = int(surface["tasks_per_stratum_language_cell"])

    slots: list[dict[str, Any]] = []
    for stratum in strata:
        for language in languages:
            for ordinal in range(1, per_cell + 1):
                slots.append(
                    {
                        "semantic_task_id": (
                            f"v5-{stratum}-{language}-{ordinal:02d}"
                        ),
                        "task_stratum": stratum,
                        "language": language,
                        "ordinal_in_cell": ordinal,
                    }
                )

    expected = int(surface["unique_semantic_tasks"])
    if len(slots) != expected:
        raise RuntimeError(
            f"adaptive DEV slot count drifted: {len(slots)} != {expected}"
        )

    ids = [slot["semantic_task_id"] for slot in slots]
    if len(ids) != len(set(ids)):
        raise RuntimeError("adaptive DEV semantic_task_id values must be unique")

    counts = Counter(
        (slot["task_stratum"], slot["language"])
        for slot in slots
    )
    if len(counts) != int(surface["cells"]):
        raise RuntimeError(
            f"adaptive DEV cell count drifted: {len(counts)}"
        )
    if set(counts.values()) != {per_cell}:
        raise RuntimeError(
            "adaptive DEV stratum x language cells are not balanced"
        )

    leaked = FORBIDDEN_CONTENT_KEYS.intersection(
        key
        for slot in slots
        for key in slot
    )
    if leaked:
        raise RuntimeError(
            "adaptive DEV authoring slots leaked content keys: "
            + ", ".join(sorted(leaked))
        )

    return {
        "schema_version": 1,
        "issue": 430,
        "experiment": prereg["experiment"],
        "status": "authoring_slots_only_no_query_or_gold_content",
        "preregistration_path": str(PREREG.relative_to(ROOT)),
        "preregistration_file_sha256": _file_sha(PREREG),
        "b1_rows_used": False,
        "b2_rows_used": False,
        "heldout_432_rows_used": False,
        "final_answer_424_rows_used": False,
        "representation_dev_434_queries_used": False,
        "semantic_task_count": len(slots),
        "task_strata": strata,
        "languages": languages,
        "tasks_per_cell": per_cell,
        "cell_count": len(counts),
        "slots_sha256": _sha(slots),
        "forbidden_content_keys": sorted(FORBIDDEN_CONTENT_KEYS),
        "slots": slots,
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
                "semantic_task_count": plan["semantic_task_count"],
                "cell_count": plan["cell_count"],
                "slots_sha256": plan["slots_sha256"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
