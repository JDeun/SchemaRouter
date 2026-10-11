"""One-shot outcome-blind 0.14 #432 cutover, gated on real frozen evidence.

May cancel ONLY the pinned original run AFTER verifying complete successful
ZIPs and all four measured, unscored two-task pilot reports. The existing
conveyor then dispatches the terminal-parent microshard recovery workflow.
Never reads scientific pass/fail, overwrites artifacts or starts a new study.
"""
from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Any

from scripts.research_014_conveyor import GitHubAPI
from scripts.research_014_heldout_recovery import FROZEN_SOURCE, _artifact_payload, latest_jobs
from scripts.research_014_preservation_preflight import inspect_parent

ORIGINAL_RUN = 38012340016
PILOT_RUN = 38097578889
PILOT_SHA = "a8c4c4f0bd3757e8e0a065753ff8cbc8832d378c"
EVIDENCE_DIGEST = (
    "sha256:a6dcd33ac9768f939d18e18a3edcf3de6a7e35a1804a7b5666433f2f6ebdcce7"
)
PILOT_PARTS = {
    "pilot-c250-g01": 250,
    "pilot-c250-g12": 250,
    "pilot-c500-g01": 500,
    "pilot-c500-g12": 500,
}
REQUIRED_CONDITIONS = frozenset({
    "FULL", "ORACLE", "SR-10", "SR-5", "SR-PROGRESSIVE"
})
REPORT_RE = re.compile(
    r"^frozen-two-task-speed-pilot-(pilot-c(?:250|500)-g(?:01|12))-"
    + str(PILOT_RUN) + r"$"
)


def validate_pilot(api: GitHubAPI, *, frozen_tasks_sha: str) -> dict[str, int]:
    """Check actual completed matrix jobs AND genuine ZIP pilot reports."""
    run = api.run(PILOT_RUN)
    if (
        run.get("status") != "completed"
        or run.get("conclusion") != "success"
        or run.get("head_sha") != PILOT_SHA
    ):
        raise ValueError("frozen 4/4 pilot not terminal/success/pinned")
    jobs = latest_jobs(api, PILOT_RUN)
    observed: dict[str, str] = {}
    for job in jobs:
        name = str(job.get("name") or "")
        if not name.startswith("measure ("):
            continue
        ident = name.split("(", 1)[1].split(",", 1)[0]
        if ident in observed:
            raise ValueError("duplicate pilot evaluator")
        observed[ident] = str(job.get("conclusion"))
    if set(observed) != set(PILOT_PARTS) or set(observed.values()) != {"success"}:
        raise ValueError("all four pinned pilot evaluator jobs must succeed")
    artifacts = {}
    for artifact in api.artifacts(PILOT_RUN):
        match = REPORT_RE.fullmatch(str(artifact.get("name") or ""))
        if match:
            if match.group(1) in artifacts or artifact.get("expired"):
                raise ValueError("missing/nonunique surviving pilot artifact")
            artifacts[match.group(1)] = artifact
    if set(artifacts) != set(PILOT_PARTS):
        raise ValueError("four actual pilot ZIP artifacts required")
    timings: dict[str, int] = {}
    for ident, catalog in sorted(PILOT_PARTS.items()):
        # _artifact_payload checks real ZIP bytes against GitHub SHA-256
        # before parsing the identity-only report, never scored rows.
        report = _artifact_payload(api, artifacts[ident], "pilot-report.json")
        seconds = report.get("evaluation_wall_seconds")
        runtime = report.get("runtime", {})
        if (
            report.get("job_id") != ident
            or report.get("catalog_size") != catalog
            or report.get("source_revision") != FROZEN_SOURCE
            or report.get("parent_run_id") != ORIGINAL_RUN
            or report.get("tasks_sha256") != frozen_tasks_sha
            or report.get("identity_only_pilot") is not True
            or report.get("eligible_for_scientific_aggregation") is not False
            or report.get("verified_episode_count") != 10
            or len(report.get("tasks", [])) != 2
            or set(report.get("conditions", [])) != REQUIRED_CONDITIONS
            or not isinstance(seconds, int)
            or not 0 < seconds < 5 * 3600
            or not isinstance(runtime, dict)
            or runtime.get("python") != "3.12.14"
            or runtime.get("machine") not in {"aarch64", "arm64"}
            or runtime.get("torch") != "2.14.0+cpu"
            or runtime.get("transformers") != "4.57.6"
        ):
            raise ValueError(f"incomplete frozen live pilot identity: {ident}")
        timings[ident] = seconds
    return timings


def cutover(
    api: GitHubAPI,
    corpus: dict[str, Any],
    *,
    execute: bool,
) -> dict[str, Any]:
    """Return a proof before effects; cancel at most the exact original run."""
    run = api.run(ORIGINAL_RUN)
    if (
        "research-0.14-heldout-generalization.yml"
        not in str(run.get("path") or "")
        or EVIDENCE_DIGEST not in str(run.get("display_title") or "")
        or f"source={FROZEN_SOURCE}" not in str(run.get("display_title") or "")
    ):
        raise ValueError("canonical frozen original run identity mismatch")
    if run.get("status") not in {"queued", "in_progress", "completed"}:
        raise ValueError("unknown original run state")
    if not api.path_exists(
        ".github/workflows/research-0.14-heldout-recovery.yml", ref="main"
    ) or not api.path_exists(
        "scripts/research_014_heldout_recovery.py", ref="main"
    ):
        raise ValueError("recovery implementation not available on main")
    pilot = validate_pilot(api, frozen_tasks_sha=str(corpus["tasks_sha256"]))
    snapshot = inspect_parent(api, corpus, parent=ORIGINAL_RUN)
    statuses = snapshot["latest_evaluator_status_counts"]
    if (
        snapshot["expected_parent_shards"] != 234
        or sum(statuses.values()) != 234
        or snapshot["invalid_successful_shard_artifacts"]
        or snapshot["verified_reusable_parent_shards"] != statuses["success"]
        or snapshot["verified_reusable_parent_shards"] < 96
        or snapshot["source_sha"] != FROZEN_SOURCE
        or snapshot["tasks_sha256"] != corpus["tasks_sha256"]
    ):
        raise ValueError("incomplete or invalid real original successful shard proof")
    # Even a cancelled/incomplete ORIGINAL run retains all successful ZIPs.
    # Cancelled/in-progress original jobs do not become canonical evidence.
    result = {
        "kind": "research_014_outcome_blind_controlled_cutover",
        "parent_run_id": ORIGINAL_RUN,
        "pilot_run_id": PILOT_RUN,
        "scientific_aggregate": False,
        "source_sha": FROZEN_SOURCE,
        "evidence_digest": EVIDENCE_DIGEST,
        "tasks_sha256": corpus["tasks_sha256"],
        "verified_pilot_wall_seconds": pilot,
        "original_reusable_parent_shards": snapshot["verified_reusable_parent_shards"],
        "original_reusable_episodes": snapshot["verified_reusable_episodes"],
        "original_unfinished_parent_shards": snapshot[
            "missing_or_incomplete_parent_shards_at_snapshot"
        ],
        "planned_recovery_waves_at_snapshot": snapshot["prospective_recovery_waves"],
        "in_progress_jobs_at_snapshot": statuses["in_progress"],
        "unverified_partial_outputs_reused": False,
        "original_run_status_before_action": run["status"],
        "authorized_one_shot_cutover": bool(execute),
        "cancel_requested": False,
    }
    if run["status"] == "completed":
        result["action"] = "already_terminal_conveyor_will_select_recovery"
        return result
    if not execute:
        result["action"] = "audit_only_no_run_cancelled"
        return result

    # Double-check status AFTER the expensive ZIP audit. Race with a
    # naturally finished parent => avoid unnecessary cancellation.
    fresh = api.run(ORIGINAL_RUN)
    if fresh.get("status") == "completed":
        result["action"] = "became_terminal_during_audit"
        return result
    if fresh.get("status") not in {"queued", "in_progress"}:
        raise ValueError("unexpected status before one-shot cancellation")

    # GitHub responds 202; terminal cancellation can be asynchronous.
    # A separate existing conveyor, gated on parent=terminal and exact
    # surviving successful ZIPs, dispatches wave 0; NO recovery is
    # permitted here while original jobs remain active.
    status, _ = api._request(
        "POST", f"/actions/runs/{ORIGINAL_RUN}/cancel"
    )
    if status not in {200, 202, 204}:
        raise ValueError("GitHub did not accept one-shot original cancellation")
    result["cancel_requested"] = True
    result["action"] = "cancel_accepted_wait_for_terminal_conveyor"
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    corpus = json.loads(args.corpus.read_text(encoding="utf-8"))
    api = GitHubAPI(os.environ["GITHUB_REPOSITORY"], os.environ["GH_TOKEN"])
    report = cutover(api, corpus, execute=args.execute)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
