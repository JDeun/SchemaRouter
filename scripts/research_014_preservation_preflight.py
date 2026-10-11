"""Read-only outcome-blind preflight for a still-active held-out evaluation.

Inspect all latest original jobs, surviving artifact ZIP hashes, frozen model
metadata and complete task/condition identities before considering a cutover.
Never dispatch, cancel, rerun, aggregate scientific outcomes, or write issues.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import zipfile
from pathlib import Path
from typing import Any

from scripts.research_014_conveyor import GitHubAPI
from scripts.research_014_heldout_recovery import (
    ARTIFACT_RE,
    FROZEN_SOURCE,
    JOB_RE,
    PARENT_WORKFLOW,
    _artifact_payload,
    frozen_shards,
    latest_jobs,
    validate_shard,
    wave_parts,
)


def inspect_parent(
    api: GitHubAPI, corpus: dict[str, Any], *, parent: int,
) -> dict[str, Any]:
    """Return preservation evidence, not a safe-to-cancel authorization."""
    shards = frozen_shards(corpus)
    run = api.run(parent)
    if PARENT_WORKFLOW not in str(run.get("path") or ""):
        raise ValueError("not a frozen held-out workflow")
    if f"source={FROZEN_SOURCE}" not in str(run.get("display_title") or ""):
        raise ValueError("frozen scientific source provenance drift")
    if run.get("status") not in {"queued", "in_progress", "completed"}:
        raise ValueError("unrecognized original workflow status")

    jobs = latest_jobs(api, parent)
    observed: dict[str, str] = {}
    for job in jobs:
        name = str(job.get("name") or "")
        match = JOB_RE.match(name)
        if not match:
            continue
        shard = f"c{match.group(1)}-g{match.group(2)}"
        if shard not in shards or shard in observed:
            raise ValueError(f"unexpected or duplicate frozen evaluator job: {shard}")
        observed[shard] = str(job.get("conclusion") or job.get("status") or "")
    if set(observed) != set(shards):
        raise ValueError("original 234-shard matrix not fully materialized")

    artifacts: dict[str, dict[str, Any]] = {}
    for artifact in api.artifacts(parent):
        name = str(artifact.get("name") or "")
        match = ARTIFACT_RE.fullmatch(name)
        if not match or int(match.group(2)) != parent:
            continue
        ident = match.group(1)
        if ident not in shards or ident in artifacts:
            raise ValueError(f"unexpected or duplicate evaluator artifact: {ident}")
        artifacts[ident] = artifact

    verified: dict[str, dict[str, Any]] = {}
    invalid: dict[str, str] = {}
    for shard, conclusion in sorted(observed.items()):
        if conclusion != "success":
            continue
        artifact = artifacts.get(shard)
        if artifact is None or artifact.get("expired"):
            invalid[shard] = "missing_or_expired_artifact"
            continue
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", str(artifact.get("digest") or "")):
            invalid[shard] = "missing_or_invalid_sha256_metadata"
            continue
        catalog, tasks = shards[shard]
        # Verifies the downloaded ZIP bytes, payload model/runtime and exact
        # paired episode identities without looking at pass/fail or scores.
        try:
            payload = _artifact_payload(api, artifact, f"{shard}.json")
            validate_shard(payload, corpus=corpus, catalog=catalog, task_ids=tasks)
        except (ValueError, KeyError, TypeError, IndexError, OSError, zipfile.BadZipFile) as exc:
            invalid[shard] = type(exc).__name__
            continue
        verified[shard] = {
            "artifact_id": int(artifact["id"]),
            "artifact_digest": str(artifact["digest"]),
            "catalog_size": catalog,
            "task_count": len(tasks),
        }

    missing = sorted(set(shards) - set(verified))
    wave_sizes: list[dict[str, Any]] = []
    if missing:
        _, count = wave_parts(shards, missing, 0)
        for wave in range(count):
            parts, _ = wave_parts(shards, missing, wave)
            wave_sizes.append({
                "wave": wave,
                "microshards": len(parts),
                "catalog_500_microshards": sum(
                    int(item["catalog_size"] == 500) for item in parts
                ),
            })

    counts = {
        kind: sum(value == kind for value in observed.values())
        for kind in {"success", "cancelled", "failure", "timed_out",
                     "queued", "in_progress"}
    }
    return {
        "kind": "read_only_preservation_preflight",
        "scientific_aggregate": False,
        "safe_to_cancel": False,
        "run_is_still_mutating": run.get("status") != "completed",
        "original_run_id": parent,
        "original_run_status": run["status"],
        "source_sha": FROZEN_SOURCE,
        "tasks_sha256": corpus["tasks_sha256"],
        "expected_parent_shards": len(shards),
        "latest_evaluator_status_counts": counts,
        "verified_reusable_parent_shards": len(verified),
        "verified_reusable_episodes": len(verified)
        * 10 * len(corpus["condition_manifest"]["conditions"]),
        "invalid_successful_shard_artifacts": invalid,
        "missing_or_incomplete_parent_shards_at_snapshot": len(missing),
        "prospective_recovery_waves": wave_sizes,
        "verified_artifact_provenance": verified,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--parent-run", type=int, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    api = GitHubAPI(os.environ["GITHUB_REPOSITORY"], os.environ["GH_TOKEN"])
    corpus = json.loads(args.corpus.read_text(encoding="utf-8"))
    report = inspect_parent(api, corpus, parent=args.parent_run)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8")
    # Never emit scientific row outcomes or model responses to PR logs.
    print(json.dumps({key: value for key, value in report.items()
                      if key != "verified_artifact_provenance"}, sort_keys=True))


if __name__ == "__main__":
    main()
