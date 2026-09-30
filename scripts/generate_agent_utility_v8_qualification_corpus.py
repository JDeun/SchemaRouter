"""Generate the frozen #510 runtime-qualification corpus.

This surface exists only to decide whether a candidate runtime can both call a
tool and emit a grounded structured answer. It is not projection evidence.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.agent_utility_generated_common import catalog_manifest, sha256_json  # noqa: E402
from scripts.agent_utility_generated_corpus import (  # noqa: E402
    LANGUAGES,
    source_identity_sha,
    with_task_hashes,
)
from scripts.agent_utility_prior_query_guard import (  # noqa: E402
    known_prior_queries,
    normalize_query,
)
from scripts.agent_utility_v7_projection import (  # noqa: E402
    PROJECTION_STRATA,
    build_projection_task,
    projection_authoring_slots,
)

QUALIFICATION_PREFIX = "Q"
QUALIFICATION_SURFACE = "output-field-projection-runtime-qualification-v1"
QUALIFICATION_EVIDENCE_CLASS = "instrument_qualification"
QUALIFICATION_CATALOG_SIZE = 100
QUALIFICATION_CANDIDATE_CONDITION = "SR-5"
QUALIFICATION_OBSERVATION_CONDITION = "RAW-FULL"


def qualification_authoring_slots() -> list[dict[str, Any]]:
    """One frozen task per stratum/language cell: 6 x 6 = 36 episodes."""
    slots: list[dict[str, Any]] = []
    for stratum in PROJECTION_STRATA:
        for language in LANGUAGES:
            index = len(slots)
            slots.append(
                {
                    "semantic_task_id": f"{QUALIFICATION_PREFIX}{index:04d}",
                    "projection_stratum": stratum,
                    "language": language,
                    "repeat": 0,
                }
            )
    return slots


def _projection_queries(prefix: str) -> set[str]:
    return {
        normalize_query(
            str(build_projection_task(slot, index, prefix=prefix)["query"])
        )
        for index, slot in enumerate(projection_authoring_slots())
    }


def build_qualification_corpus(source_revision: str) -> dict[str, Any]:
    slots = qualification_authoring_slots()
    tasks = [
        build_projection_task(slot, index, prefix=QUALIFICATION_PREFIX)
        for index, slot in enumerate(slots)
    ]

    queries = {normalize_query(str(task["query"])) for task in tasks}
    forbidden_surfaces = dict(known_prior_queries())
    forbidden_surfaces["projection_506"] = _projection_queries("P")
    forbidden_surfaces["successor_510"] = _projection_queries("S")

    collisions: dict[str, set[str]] = {}
    for name, prior in forbidden_surfaces.items():
        overlap = queries & prior
        if overlap:
            collisions[name] = overlap
    if collisions:
        details = "; ".join(
            f"{name!r} ({len(overlap)} shared queries)"
            for name, overlap in sorted(collisions.items())
        )
        raise SystemExit(
            f"qualification surface overlaps prior/successor surface(s): {details}"
        )

    condition_manifest = {
        "candidate_condition": QUALIFICATION_CANDIDATE_CONDITION,
        "conditions": [QUALIFICATION_OBSERVATION_CONDITION],
        "purpose": QUALIFICATION_EVIDENCE_CLASS,
        "selection_effect": "runtime_eligibility_only",
    }
    root: dict[str, Any] = {
        "schema_version": 1,
        "experiment": "0.14-output-field-projection-runtime-qualification",
        "issue": 510,
        "surface": QUALIFICATION_SURFACE,
        "evidence_class": QUALIFICATION_EVIDENCE_CLASS,
        "source_revision": source_revision,
        "authoring_slots_sha256": sha256_json(slots),
        "catalog_manifest": catalog_manifest([QUALIFICATION_CATALOG_SIZE]),
        "catalog_sizes": [QUALIFICATION_CATALOG_SIZE],
        "expected_episode_count": len(tasks),
        "source_identity_sha256": source_identity_sha(
            source_revision,
            sha256_json(slots),
            condition_manifest,
        ),
    }
    return with_task_hashes(
        root=root,
        tasks=tasks,
        condition_manifest=condition_manifest,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()

    corpus = build_qualification_corpus(args.source_revision)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(corpus, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        f"tasks={len(corpus['tasks'])} "
        f"tasks_sha256={corpus['tasks_sha256']} "
        f"source_identity={corpus['source_identity_sha256']}"
    )


if __name__ == "__main__":
    main()
