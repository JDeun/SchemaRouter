"""Outcome-blind GitHub Actions job-state triage for research 0.14 recovery.

Does NOT decide scientific success, re-run a job, inspect model outputs, touch
frozen tasks, or make claims about absent runner logs. The existing conveyor
owns bounded retries once a complete workflow run reaches terminal failure.
"""
from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Any

from scripts.research_014_conveyor import GitHubAPI
from scripts.research_014_heldout_recovery import (
    FROZEN_SOURCE,
    RECOVERY_JOB_RE,
    RECOVERY_WORKFLOW,
    latest_jobs,
)

TITLE_RE = re.compile(
    rf"^Held-out recovery parent=(\d+) wave=(\d+) source={FROZEN_SOURCE}$"
)
EVALUATION_STEP = "Evaluate only two frozen task identities per microshard"
SUCCESS_ARTIFACT_RE = re.compile(
    r"^heldout-recovery-part-(c(?:100|250|500)-g\d{2}-p\d{2})-(\d+)$"
)


def classify_failed_steps(steps: list[dict[str, Any]]) -> str:
    """Expose stage evidence, not an invented OOM/runner diagnosis."""
    if not steps:
        return "missing_step_telemetry"
    for step in steps:
        if step.get("name") == EVALUATION_STEP:
            if step.get("conclusion") == "failure":
                return "evaluator_step_failed_cause_unverified"
            if step.get("status") != "completed":
                return "evaluator_step_incomplete_runner_or_telemetry_unknown"
            if step.get("conclusion") == "success":
                return "evaluation_passed_but_later_job_failed"
            return "evaluation_conclusion_unknown"
    if any(step.get("conclusion") == "failure" for step in steps):
        return "setup_or_pre_evaluation_step_failed"
    return "evaluation_step_not_observed"


def triage(api: GitHubAPI, run_id: int) -> dict[str, Any]:
    if type(run_id) is not int or run_id <= 0:
        raise ValueError("positive integer GitHub run ID required")
    run = api.run(run_id)
    if not str(run.get("path") or "").endswith("/" + RECOVERY_WORKFLOW):
        raise ValueError("not the exact held-out recovery workflow")
    title = str(run.get("display_title") or "")
    marker = TITLE_RE.fullmatch(title)
    if marker is None:
        raise ValueError("unfrozen or unknown recovery-run provenance")
    state = str(run.get("status") or "")
    if state not in {"queued", "in_progress", "pending", "completed", "requested", "waiting"}:
        raise ValueError("unrecognized GitHub Actions status")
    jobs = latest_jobs(api, run_id)
    if not jobs:
        raise ValueError("no materialized jobs to triage")
    artifacts = api.artifacts(run_id)
    artifact_names = {
        name for item in artifacts
        if isinstance((name := item.get("name")), str)
        and not item.get("expired")
    }
    missing: list[dict[str, Any]] = []
    good = 0
    active = 0
    pending = 0
    seen: set[str] = set()
    for job in jobs:
        matched = RECOVERY_JOB_RE.match(str(job.get("name") or ""))
        if matched is None:
            continue  # Prepare/next-wave/aggregate are NOT 2-task evaluator jobs.
        ident = matched.group(1)
        if ident in seen:
            raise ValueError("duplicate latest microshard identity")
        seen.add(ident)
        conclusion = job.get("conclusion")
        job_status = str(job.get("status") or "")
        expected_artifact = f"heldout-recovery-part-{ident}-{run_id}"
        uploaded = expected_artifact in artifact_names
        if job_status == "completed" and conclusion == "success":
            good += 1
            continue
        if job_status == "completed":
            if conclusion not in {"failure", "cancelled", "timed_out"}:
                raise ValueError("unexpected completed microshard conclusion")
            job_id = job.get("id")
            if type(job_id) is not int or job_id <= 0:
                raise ValueError("failed job lacks an integer ID")
            steps = job.get("steps")
            if not isinstance(steps, list) or not steps:
                # Full job details may contain step summaries even when the
                # list-jobs API omits them. Failure to read details must NOT
                # be mistaken for evidence about the scorer or model.
                try:
                    details = api.get(f"/actions/jobs/{job_id}")
                    steps = details.get("steps")
                except (RuntimeError, ValueError, KeyError):
                    steps = None
            diagnosis = classify_failed_steps(steps if isinstance(steps, list) else [])
            missing.append({
                "microshard": ident,
                "job_id": job_id,
                "job_conclusion": conclusion,
                "stage_evidence": diagnosis,
                "artifact_uploaded_not_proof_of_success": uploaded,
                "eligible_for_bounded_retry_after_run_ends": state == "completed",
            })
        elif job_status == "in_progress":
            active += 1
        elif job_status in {"queued", "pending", "waiting", "requested"}:
            pending += 1
        else:
            raise ValueError(f"unrecognized microshard state: {job_status}")
    if len(seen) not in {250, 185}:
        raise ValueError("unexpected recovery matrix size or incomplete job listing")
    if good + active + pending + len(missing) != len(seen):
        raise ValueError("inconsistent recovery job totals")
    return {
        "schema_version": 1,
        "evidence_kind": "github_job_metadata_only_no_scientific_outcomes",
        "run_id": run_id,
        "frozen_source": FROZEN_SOURCE,
        "original_parent_run_id": int(marker.group(1)),
        "wave": int(marker.group(2)),
        "status": state,
        "conclusion": run.get("conclusion"),
        "expected_microshards": len(seen),
        "successful_jobs": good,
        "failed_jobs": len(missing),
        "active_jobs": active,
        "queued_jobs": pending,
        "failures": missing,
        "retry_policy": (
            "On terminal failure only, use GitHub rerun-failed-jobs; never "
            "replay successful jobs or treat incomplete uploads as evidence. "
            "The existing conveyor caps workflow attempts. Unknown failure "
            "cause is not proof of OOM or a model fault."
        ),
        "model_calls_by_this_triage": 0,
        "scoring_values_inspected": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", default=os.environ.get("GITHUB_REPOSITORY", ""))
    parser.add_argument("--run-id", type=int, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    token = os.environ.get("GH_TOKEN", "")
    if not args.repository or not token:
        raise SystemExit("repository and GH_TOKEN required")
    result = triage(GitHubAPI(args.repository, token), args.run_id)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(result, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "run_id": result["run_id"],
        "status": result["status"],
        "failures": [
            {k: v for k, v in row.items() if k != "job_id"}
            for row in result["failures"]
        ],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
