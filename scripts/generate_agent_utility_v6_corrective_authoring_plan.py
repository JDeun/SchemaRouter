"""Build the sealed #431 state-aware corrective retrieval authoring slots.

Only semantic-task identities and preregistered stratum/language assignments are
generated. Query wording, routes, executor state, observations and outcomes stay sealed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PREREG = ROOT / "benchmarks" / "agent-utility-v6-corrective-reretrieval-preregistration.json"

FORBIDDEN_CONTENT_KEYS = {
    "query", "queries", "task_text", "prompt",
    "required_route", "required_routes", "gold_route", "gold_routes",
    "future_required_route_id", "gold_next_route_id", "oracle_task_graph",
    "expected_answer", "executor_state", "executor_states",
    "observation", "observations", "tool_output", "tool_outputs",
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


def build_authoring_plan() -> dict[str, Any]:
    prereg = _load_prereg()
    surface = prereg["surface"]
    strata = list(surface["task_strata"])
    languages = list(surface["languages"])
    per_cell = int(surface["tasks_per_stratum_language_cell"])

    slots: list[dict[str, Any]] = []
    for task_stratum in strata:
        for language in languages:
            for ordinal in range(1, per_cell + 1):
                slots.append(
                    {
                        "semantic_task_id": (
                            f"v6-{task_stratum}-{language}-{ordinal:02d}"
                        ),
                        "task_stratum": task_stratum,
                        "language": language,
                        "ordinal_in_cell": ordinal,
                    }
                )

    if len(slots) != int(surface["unique_semantic_tasks"]):
        raise RuntimeError("corrective authoring-slot count drifted")

    ids = [row["semantic_task_id"] for row in slots]
    if len(ids) != len(set(ids)):
        raise RuntimeError("corrective semantic_task_id values must be unique")

    cell_counts = Counter(
        (row["task_stratum"], row["language"]) for row in slots
    )
    if len(cell_counts) != int(surface["cells"]):
        raise RuntimeError("corrective cell count drifted")
    if set(cell_counts.values()) != {per_cell}:
        raise RuntimeError("corrective cells are not balanced")

    leaked = FORBIDDEN_CONTENT_KEYS.intersection(
        key for row in slots for key in row
    )
    if leaked:
        raise RuntimeError(
            "corrective authoring scaffold leaked sealed content keys: "
            + ", ".join(sorted(leaked))
        )

    return {
        "schema_version": 1,
        "issue": 431,
        "experiment": prereg["experiment"],
        "status": "authoring_slots_only_content_and_execution_sealed_until_b2_terminal",
        "preregistration_path": str(PREREG.relative_to(ROOT)),
        "preregistration_file_sha256": _file_sha(PREREG),
        "content_generation_authorized": False,
        "execution_authorized": False,
        "b2_terminal_required_before_content_generation": True,
        "task_strata": strata,
        "languages": languages,
        "tasks_per_cell": per_cell,
        "semantic_task_count": len(slots),
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
                "slots_sha256": plan["slots_sha256"],
                "content_generation_authorized": False,
                "execution_authorized": False,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
