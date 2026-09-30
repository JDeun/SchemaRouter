"""Generate the frozen #506 output-field projection corpus."""
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
    source_identity_sha,
    with_task_hashes,
)
from scripts.agent_utility_v7_projection import (  # noqa: E402
    CATALOG_SIZES,
    PROJECTION_CONDITIONS,
    build_projection_task,
    projection_authoring_slots,
)

FIXED_CANDIDATE_CONDITION = "SR-5"


def build_corpus(source_revision: str) -> dict[str, Any]:
    slots = projection_authoring_slots()
    tasks = [build_projection_task(slot, index) for index, slot in enumerate(slots)]

    # Every condition sees the same routes. Only the observation differs, so the
    # candidate manifest is one entry rather than one per condition.
    condition_manifest = {
        "candidate_condition": FIXED_CANDIDATE_CONDITION,
        "conditions": list(PROJECTION_CONDITIONS),
        "varies": "observation_presentation_only",
    }

    root: dict[str, Any] = {
        "schema_version": 1,
        "experiment": "0.14-output-field-projection",
        "issue": 506,
        "surface": "development",
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
