"""Generate the frozen #424 final-answer corpus after #432 is terminal."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from scripts.agent_utility_generated_common import (
    BASE_CONDITIONS,
    FINAL_ANSWER_CATALOG_SIZES,
    catalog_manifest,
)
from scripts.agent_utility_generated_corpus import (
    build_final_task,
    source_identity_sha,
    with_task_hashes,
)
from scripts.agent_utility_prior_query_guard import (
    assert_no_prior_query_overlap,
    known_prior_query_manifest,
    normalize_query,
    queries_from_corpus,
    query_set_sha256,
)
from scripts.generate_agent_utility_v4_final_answer_authoring_plan import (
    build_authoring_plan,
)

HEX40 = re.compile(r"^[0-9a-f]{40}$")


def build_corpus(
    source_revision: str,
    *,
    forbidden_corpus: Path,
) -> dict[str, object]:
    if HEX40.fullmatch(source_revision) is None:
        raise ValueError("source_revision must be a 40-character lowercase git SHA")

    plan = build_authoring_plan()
    tasks = [
        build_final_task(slot, index)
        for index, slot in enumerate(plan["slots"], start=20001)
    ]
    normalized = {normalize_query(str(task["query"])) for task in tasks}
    if len(normalized) != len(tasks):
        raise RuntimeError("final-answer corpus produced duplicate normalized queries")

    extra_forbidden = queries_from_corpus(forbidden_corpus)
    assert_no_prior_query_overlap(
        normalized,
        extra_forbidden_queries=extra_forbidden,
    )

    condition_manifest = {
        "conditions": list(BASE_CONDITIONS),
        "relation_to_432": (
            "#432 is a forbidden-query surface only; final-answer conditions remain "
            "the preregistered FULL/SR controls."
        ),
        "structured_final_envelope_required": True,
    }
    prior = known_prior_query_manifest()
    root: dict[str, object] = {
        "schema_version": 1,
        "issue": 424,
        "experiment": plan["experiment"],
        "generator_source_revision": source_revision,
        "authoring_slots_sha256": plan["slots_sha256"],
        "catalogs": catalog_manifest(FINAL_ANSWER_CATALOG_SIZES),
        "prior_query_manifest_sha256": prior["union_sha256"],
        "extra_forbidden_query_manifest_sha256": query_set_sha256(extra_forbidden),
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
    parser.add_argument("--forbidden-corpus", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    corpus = build_corpus(
        args.source_revision,
        forbidden_corpus=args.forbidden_corpus,
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
                "tasks_sha256": corpus["tasks_sha256"],
                "freeze_identity_sha256": corpus["freeze_identity_sha256"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
