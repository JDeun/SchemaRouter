"""Generate the frozen #431 corrective-retrieval corpus after B2 success."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from scripts.agent_utility_generated_common import (
    CORRECTIVE_CONDITIONS,
    catalog_manifest,
    sha256_json,
)
from scripts.agent_utility_generated_corpus import (
    build_corrective_task,
    source_identity_sha,
    with_task_hashes,
)
from scripts.agent_utility_prior_query_guard import (
    assert_no_prior_query_overlap,
    known_prior_query_manifest,
    normalize_query,
)
from scripts.generate_agent_utility_v6_corrective_authoring_plan import (
    build_authoring_plan,
)

HEX40 = re.compile(r"^[0-9a-f]{40}$")
CATALOGS = (100, 250, 500)


def build_corpus(source_revision: str) -> dict[str, object]:
    if HEX40.fullmatch(source_revision) is None:
        raise ValueError("source_revision must be a 40-character lowercase git SHA")

    plan = build_authoring_plan()
    tasks = [
        build_corrective_task(slot, index)
        for index, slot in enumerate(plan["slots"], start=1)
    ]
    normalized = {normalize_query(str(task["query"])) for task in tasks}
    if len(normalized) != len(tasks):
        raise RuntimeError("corrective corpus produced duplicate normalized queries")
    assert_no_prior_query_overlap(normalized)

    condition_manifest = {
        "conditions": list(CORRECTIVE_CONDITIONS),
        "state_aware_per_refresh_k": 5,
        "state_aware_max_refreshes": 5,
        "static_progressive_stages": [3, 10, "FULL"],
        "retriever": "canonical deterministic SchemaPlanner scorer",
    }
    prior = known_prior_query_manifest()
    root: dict[str, object] = {
        "schema_version": 1,
        "issue": 431,
        "experiment": "execution-state-aware-corrective-retrieval-v1",
        "generator_source_revision": source_revision,
        "authoring_slots_sha256": plan["slots_sha256"],
        "catalogs": catalog_manifest(CATALOGS),
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
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    corpus = build_corpus(args.source_revision)
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
