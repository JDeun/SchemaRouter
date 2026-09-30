"""Generate the frozen #432 held-out corpus after upstream gates are terminal."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from scripts.agent_utility_generated_common import (
    BASE_CONDITIONS,
    EXTENDED_CATALOG_SIZES,
    catalog_manifest,
)
from scripts.agent_utility_generated_corpus import (
    build_heldout_task,
    source_identity_sha,
    with_task_hashes,
)
from scripts.agent_utility_prior_query_guard import (
    assert_no_prior_query_overlap,
    known_prior_query_manifest,
    normalize_query,
)
from scripts.generate_agent_utility_v3_heldout_authoring_plan import (
    build_authoring_plan,
)

HEX40 = re.compile(r"^[0-9a-f]{40}$")


def build_corpus(
    source_revision: str,
    *,
    include_struct_fixed3: bool,
    include_state_aware: bool,
) -> dict[str, object]:
    if HEX40.fullmatch(source_revision) is None:
        raise ValueError("source_revision must be a 40-character lowercase git SHA")

    plan = build_authoring_plan()
    tasks = [
        build_heldout_task(slot, index)
        for index, slot in enumerate(plan["slots"], start=10001)
    ]
    normalized = {normalize_query(str(task["query"])) for task in tasks}
    if len(normalized) != len(tasks):
        raise RuntimeError("held-out corpus produced duplicate normalized queries")
    assert_no_prior_query_overlap(normalized)

    optional: list[str] = []
    if include_struct_fixed3:
        optional.append("STRUCT-FIXED-3")
    if include_state_aware:
        optional.append("SR-5-STATE-AWARE")
    conditions = [*BASE_CONDITIONS, *optional]
    condition_manifest = {
        "required_conditions": list(BASE_CONDITIONS),
        "optional_promoted_conditions": optional,
        "conditions": conditions,
        "struct_fixed3_included": include_struct_fixed3,
        "state_aware_included": include_state_aware,
        "selection_rule": (
            "Optional conditions are frozen solely from preregistered upstream terminal gates."
        ),
    }

    prior = known_prior_query_manifest()
    root: dict[str, object] = {
        "schema_version": 1,
        "issue": 432,
        "benchmark": plan["benchmark"],
        "generator_source_revision": source_revision,
        "authoring_slots_sha256": plan["slots_sha256"],
        "catalogs": catalog_manifest(EXTENDED_CATALOG_SIZES),
        "prior_query_manifest_sha256": prior["union_sha256"],
        "freeze_identity_sha256": source_identity_sha(
            source_revision,
            str(plan["slots_sha256"]),
            condition_manifest,
        ),
    }
    with_task_hashes(
        root=root,
        tasks=tasks,
        condition_manifest=condition_manifest,
    )
    return root


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--include-struct-fixed3", action="store_true")
    parser.add_argument("--include-state-aware", action="store_true")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    corpus = build_corpus(
        args.source_revision,
        include_struct_fixed3=args.include_struct_fixed3,
        include_state_aware=args.include_state_aware,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(corpus, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "task_count": len(corpus["tasks"]),
                "conditions": corpus["condition_manifest"]["conditions"],
                "tasks_sha256": corpus["tasks_sha256"],
                "freeze_identity_sha256": corpus["freeze_identity_sha256"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
