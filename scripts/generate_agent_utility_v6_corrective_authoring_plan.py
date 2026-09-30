"""Build the deterministic #431 corrective-retrieval authoring slots.

No task text, gold route, execution trace, or score is generated here.
Scoring remains blocked until #423 B2 is terminal.
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
    / "agent-utility-v6-corrective-reretrieval-preregistration.json"
)

FORBIDDEN_CONTENT_KEYS = {
    "query",
    "queries",
    "task_text",
    "prompt",
    "required_route",
    "required_routes",
    "required_route_ids",
    "future_required_route_ids",
    "gold_route",
    "gold_routes",
    "future_required_route_id",
    "gold_next_route_id",
    "oracle_task_graph",
    "hidden_expected_answer",
    "hidden_reference_fact",
    "observation",
    "observations",
    "execution_trace",
    "condition",
    "condition_name",
    "candidate",
    "candidates",
    "candidate_ids",
    "candidate_set",
    "score",
    "scores",
    "ranking",
    "rankings",
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
    surface = prereg["surface"]
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
                            f"v6-{stratum}-{language}-{ordinal:02d}"
                        ),
                        "task_stratum": stratum,
                        "language": language,
                        "ordinal_in_cell": ordinal,
                    }
                )

    expected = int(surface["unique_semantic_tasks"])
    if len(slots) != expected:
        raise RuntimeError(
            f"corrective authoring-slot count drifted: {len(slots)} != {expected}"
        )
    ids = [slot["semantic_task_id"] for slot in slots]
    if len(ids) != len(set(ids)):
        raise RuntimeError("corrective semantic_task_id values must be unique")

    counts = Counter(
        (slot["task_stratum"], slot["language"])
        for slot in slots
    )
    if len(counts) != int(surface["cells"]):
        raise RuntimeError(
            f"corrective stratum/language cell count drifted: {len(counts)}"
        )
    if set(counts.values()) != {per_cell}:
        raise RuntimeError(
            "corrective stratum/language authoring slots are not balanced"
        )

    leaked = FORBIDDEN_CONTENT_KEYS.intersection(
        key
        for slot in slots
        for key in slot
    )
    if leaked:
        raise RuntimeError(
            "corrective authoring slots leaked sealed content keys: "
            + ", ".join(sorted(leaked))
        )

    return {
        "schema_version": 1,
        "issue": 431,
        "experiment": prereg["experiment"],
        "status": "authoring_slots_only_execution_blocked_until_b2_terminal",
        "preregistration_path": str(PREREG.relative_to(ROOT)),
        "preregistration_file_sha256": _file_sha(PREREG),
        "content_generation_authorized": False,
        "execution_authorized": False,
        "b2_terminal_required": True,
        "b1_rows_used": False,
        "b2_rows_used": False,
        "heldout_432_rows_used": False,
        "final_answer_424_rows_used": False,
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
                "execution_authorized": plan["execution_authorized"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
