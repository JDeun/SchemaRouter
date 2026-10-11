"""Read-only infrastructure diagnosis for 0.14 recovery workflow failures.

Never looks at scientific model output, task labels, pass/fail scores or
request contents. A job that says "failed" while its evaluator step remains
"in_progress" suggests runner loss or status inconsistency; it is NOT proof
of OOM or a deterministic evaluator bug.
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from scripts.research_014_conveyor import GitHubAPI
from scripts.research_014_heldout_recovery import (
    FROZEN_SOURCE,
    RECOVERY_JOB_RE,
    RECOVERY_WORKFLOW,
    latest_jobs,
)

EXPECTED_PARENT = 38012340016
TITLE = re.compile(
    rf"^Held-out recovery parent={EXPECTED_PARENT} wave=(\d+) "
    rf"source={FROZEN_SOURCE}$"
)


def _duration(start: object, end: object) -> int | None:
    if not isinstance(start, str) or not isinstance(end, str):
        return None
    try:
        a = datetime.fromisoformat(start.replace("Z", "+00:00"))
        b = datetime.fromisoformat(end.replace("Z", "+00:00"))
    except ValueError:
        return None
    return max(0, round((b - a).total_seconds()))


def inspect(api: Any, *, run_id: int) -> dict[str, Any]:
    if type(run_id) is not int or run_id < 1:
        raise ValueError("invalid recovery run id")
    run = api.run(run_id)
    path = str(run.get("path") or "")
    title = str(run.get("display_title") or "")
    if not path.endswith("/" + RECOVERY_WORKFLOW) or not TITLE.fullmatch(title):
        raise ValueError("not the exact 0.14 pinned recovery wave")
    wave = int(TITLE.fullmatch(title).group(1))
    if wave not in (0, 1, 2):
        raise ValueError("unexpected recovery wave")
    jobs = latest_jobs(api, run_id)
    if not jobs:
        raise ValueError("no materialized jobs to audit")

    failed: list[dict[str, Any]] = []
    counts: dict[str, int] = {}
    for job in jobs:
        name = str(job.get("name") or "")
        m = RECOVERY_JOB_RE.match(name)
        if m is None:
            continue
        ident = m.group(1)
        conclusion = str(job.get("conclusion") or "none")
        status = str(job.get("status") or "unknown")
        key = f"{status}/{conclusion}"
        counts[key] = counts.get(key, 0) + 1
        if conclusion not in ("failure", "timed_out", "cancelled"):
            continue

        # An individual job GET can carry more recent step metadata than
        # paginated workflow job snapshots. Unknown is never "OOM proven".
        try:
            details = api.get(f"/actions/jobs/{int(job['id'])}")
        except (RuntimeError, KeyError, TypeError, ValueError):
            details = {}
        steps = details.get("steps", job.get("steps", []))
        if not isinstance(steps, list):
            steps = []
        stage = next(
            (s for s in steps if s.get("name") ==
             "Evaluate only two frozen task identities per microshard"),
            None,
        )
        observed_stage = (
            {
                "status": str(stage.get("status") or "unknown"),
                "conclusion": str(stage.get("conclusion") or "none"),
            } if isinstance(stage, dict) else None
        )
        if (
            conclusion == "failure"
            and observed_stage is not None
            and observed_stage["status"] == "in_progress"
        ):
            classification = "runner_interruption_possible_not_confirmed"
        elif observed_stage is not None and observed_stage["conclusion"] == "failure":
            classification = "evaluator_step_failed_cause_requires_logs"
        else:
            classification = "unclassified_requires_logs"

        failed.append({
            "job_id": int(job["id"]),
            "microshard_id": ident,
            "conclusion": conclusion,
            "stage": observed_stage,
            "classification": classification,
            "duration_seconds": _duration(
                job.get("started_at"), job.get("completed_at")
            ),
            "replay_allowed_now": run.get("status") == "completed",
        })

    return {
        "schema_version": 1,
        "evidence_role": "infrastructure_forensics_only_no_scientific_scoring",
        "run_id": run_id,
        "original_parent_run": EXPECTED_PARENT,
        "wave": wave,
        "scientific_source_sha": FROZEN_SOURCE,
        "run_status": str(run.get("status")),
        "run_conclusion": run.get("conclusion"),
        "run_attempt": int(run.get("run_attempt") or 1),
        "microshard_job_count": sum(counts.values()),
        "status_counts": counts,
        "failed_jobs": failed,
        "deduced_root_cause": None,
        "limits": [
            "No model/episode outcomes, evaluator output or gold labels read.",
            "A completed failed job with in_progress evaluator step is not OOM proof.",
            "A failed or partial artifact must not be canonical evidence.",
            "GitHub rerun-failed-jobs only after the whole wave completes.",
            "Conveyor retains bounded at-most-three attempts and frozen SHA.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", type=int, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    import os

    api = GitHubAPI(os.environ["GITHUB_REPOSITORY"], os.environ["GH_TOKEN"])
    result = inspect(api, run_id=args.run_id)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({
        "run": result["run_id"],
        "status": result["run_status"],
        "attempt": result["run_attempt"],
        "failed_jobs": result["failed_jobs"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
