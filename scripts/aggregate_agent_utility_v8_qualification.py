"""Aggregate one #510 runtime candidate into validated qualification evidence."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.qualify_agent_utility_runtime import (  # noqa: E402
    ROSTER,
    ROSTER_REVISIONS,
    qualifies,
    validate_qualification_evidence,
)
from scripts.validate_agent_utility_v8_qualification_corpus import (  # noqa: E402
    validate_qualification_corpus,
)


def aggregate(
    corpus: dict[str, Any],
    *,
    candidate: str,
    shard_dir: Path,
) -> dict[str, Any]:
    validate_qualification_corpus(corpus)
    if candidate not in ROSTER:
        raise ValueError(f"candidate is not on frozen roster: {candidate!r}")

    shard_paths = sorted(shard_dir.rglob("*.json"))
    if not shard_paths:
        raise ValueError("no qualification shard JSON files found")

    rows: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    runtime_identities: list[dict[str, Any]] = []
    for path in shard_paths:
        shard = json.loads(path.read_text(encoding="utf-8"))
        for field, expected in {
            "evidence_class": corpus["evidence_class"],
            "surface": corpus["surface"],
            "source_revision": corpus["source_revision"],
            "harness_revision": corpus["source_revision"],
            "corpus_tasks_sha256": corpus["tasks_sha256"],
            "candidate_model": candidate,
            "model_revision": ROSTER_REVISIONS[candidate],
        }.items():
            if shard.get(field) != expected:
                raise ValueError(
                    f"{path}: {field} mismatch: expected {expected!r}, "
                    f"got {shard.get(field)!r}"
                )
        runtime_identities.append(dict(shard["runtime"]))
        for row in shard["rows"]:
            task_id = str(row["semantic_task_id"])
            if task_id in seen_ids:
                raise ValueError(f"duplicate qualification row across shards: {task_id}")
            seen_ids.add(task_id)
            rows.append(row)

    expected_ids = {
        str(task["semantic_task_id"])
        for task in corpus["tasks"]
    }
    if seen_ids != expected_ids:
        missing = sorted(expected_ids - seen_ids)
        extra = sorted(seen_ids - expected_ids)
        raise ValueError(
            f"qualification shards do not cover frozen surface: "
            f"missing={missing[:3]} extra={extra[:3]}"
        )

    platform_shapes = {
        json.dumps(identity.get("platform", {}), sort_keys=True)
        for identity in runtime_identities
    }
    if len(platform_shapes) != 1:
        raise ValueError("qualification shards used inconsistent runtime platforms")

    evidence: dict[str, Any] = {
        "schema_version": 1,
        "issue": 510,
        "candidate_model": candidate,
        "model_revision": ROSTER_REVISIONS[candidate],
        "source_revision": corpus["source_revision"],
        "harness_revision": corpus["source_revision"],
        "corpus_tasks_sha256": corpus["tasks_sha256"],
        "evidence_class": corpus["evidence_class"],
        "surface": corpus["surface"],
        "runtime": runtime_identities[0],
        "rows": sorted(rows, key=lambda row: str(row["semantic_task_id"])),
    }
    rates = validate_qualification_evidence(candidate, evidence, corpus)
    evidence["rates"] = rates
    evidence["qualified"] = qualifies(rates)
    evidence["episode_count"] = len(rows)
    return evidence


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", required=True, type=Path)
    parser.add_argument("--candidate", required=True, choices=ROSTER)
    parser.add_argument("--input-dir", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()

    corpus = json.loads(args.corpus.read_text(encoding="utf-8"))
    result = aggregate(corpus, candidate=args.candidate, shard_dir=args.input_dir)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "candidate": args.candidate,
                "rates": result["rates"],
                "qualified": result["qualified"],
                "episode_count": result["episode_count"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
