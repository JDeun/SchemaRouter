"""Generate the frozen #510 successor screen corpus.

The surface must share no query with #506, whose screen this one replaces.
Disjointness is enforced here at generation rather than left to a test, so a
corpus that overlaps can never reach a run.
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

from scripts.agent_utility_generated_common import (  # noqa: E402
    catalog_manifest,
    sha256_json,
)
from scripts.agent_utility_generated_corpus import (  # noqa: E402
    LANGUAGES,  # noqa: E402
    source_identity_sha,
    with_task_hashes,
)
from scripts.agent_utility_prior_query_guard import (  # noqa: E402
    known_prior_queries,
    normalize_query,
)
from scripts.agent_utility_v7_projection import (  # noqa: E402
    CATALOG_SIZES,
    PROJECTION_CONDITIONS,
    PROJECTION_STRATA,
    TASKS_PER_CELL,
    build_projection_task,
    projection_authoring_slots,
)

SUCCESSOR_PREFIX = "S"
FIXED_CANDIDATE_CONDITION = "SR-5"


def successor_authoring_slots() -> list[dict[str, Any]]:
    slots: list[dict[str, Any]] = []
    for stratum in PROJECTION_STRATA:
        for language in LANGUAGES:
            for repeat in range(TASKS_PER_CELL):
                index = len(slots)
                slots.append(
                    {
                        "semantic_task_id": f"{SUCCESSOR_PREFIX}{index:04d}",
                        "projection_stratum": stratum,
                        "language": language,
                        "repeat": repeat,
                    }
                )
    return slots


def _506_projection_queries() -> set[str]:
    """The #506 query set, built locally rather than read off the guard.

    Registering #506 in `agent_utility_prior_query_guard.known_prior_queries`
    would change `known_prior_query_manifest()["union_sha256"]`, which is
    stamped into generated v3/v4/v6 corpora and hard-checked by their
    validators. This surface needs the same disjointness guarantee without
    that blast radius, so it is built here instead.
    """
    return {
        normalize_query(str(build_projection_task(slot, index)["query"]))
        for index, slot in enumerate(projection_authoring_slots())
    }


def build_corpus(source_revision: str) -> dict[str, Any]:
    slots = successor_authoring_slots()
    tasks = [
        build_projection_task(slot, index, prefix=SUCCESSOR_PREFIX)
        for index, slot in enumerate(slots)
    ]

    queries = {normalize_query(str(task["query"])) for task in tasks}
    forbidden_surfaces = dict(known_prior_queries())
    forbidden_surfaces["projection"] = _506_projection_queries()

    # Hand-rolled rather than assert_no_prior_query_overlap (#510's named
    # mechanism): that helper raises ValueError and reports only the first
    # colliding surface. This is a generation script, not a library call, so
    # SystemExit is the appropriate failure mode, and every colliding
    # surface is aggregated below instead of just the first, so a run that
    # collides on more than one surface does not require a fix/rerun/refix
    # loop to find out.
    collisions: dict[str, set[str]] = {}
    for name, prior in forbidden_surfaces.items():
        overlap = queries & prior
        if overlap:
            collisions[name] = overlap
    if collisions:
        details = "; ".join(
            f"{name!r} ({len(overlap)} shared queries, e.g. {sorted(overlap)[0]!r})"
            for name, overlap in sorted(collisions.items())
        )
        raise SystemExit(
            f"successor surface overlaps prior surface(s): {details}"
        )

    condition_manifest = {
        "candidate_condition": FIXED_CANDIDATE_CONDITION,
        "conditions": list(PROJECTION_CONDITIONS),
        "varies": "observation_presentation_only",
    }
    root: dict[str, Any] = {
        "schema_version": 1,
        "experiment": "0.14-output-field-projection-successor-screen",
        "issue": 510,
        "surface": "shared_frozen_successor_screen",
        "source_revision": source_revision,
        "authoring_slots_sha256": sha256_json(slots),
        "catalog_manifest": catalog_manifest(CATALOG_SIZES),
        "catalog_sizes": list(CATALOG_SIZES),
        "source_identity_sha256": source_identity_sha(
            source_revision,
            sha256_json(slots),
            condition_manifest,
        ),
    }
    return with_task_hashes(root=root, tasks=tasks, condition_manifest=condition_manifest)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()

    corpus = build_corpus(args.source_revision)
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
