"""Narrow-scope GitHub experiment issue lifecycle, never product issue closure.

Only exact AutoLab-owned benchmark MEASUREMENT issues may be created and
closed after a complete 72-case research report. All broader product,
release, independent-qualification, and architectural issues stay open.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.research_operation_fit_auto_loop import (  # noqa: E402
    CORPUS_SHA,
    VARIANTS,
    validate_state,
)
from scripts.research_operation_fit_conveyor import (  # noqa: E402
    _metric_rows,
    load_inputs,
)

MARKER = "schemarouter-autolab-owned-v1"
REPO = "JDeun/SchemaRouter"
PARENT_ISSUE = 1405


def run_gh(args: list[str]) -> str:
    result = subprocess.run(
        ["gh", *args], capture_output=True, text=True,
        check=True, timeout=60,
    )
    return result.stdout.strip()


def sync_issues(
    report: dict[str, Any], *,
    run_url: str,
    github_repo: str,
    gh: Callable[[list[str]], str] = run_gh,
) -> list[int]:
    if github_repo != REPO:
        raise ValueError("refuse issue mutation outside the registered repository")
    if not re.fullmatch(
        r"https://github\.com/JDeun/SchemaRouter/actions/runs/[1-9][0-9]*",
        run_url,
    ):
        raise ValueError("untrusted workflow run URL")
    if (
        report.get("status") != "DEV_EVIDENCE_ONLY"
        or report.get("source_sha256") != CORPUS_SHA
        or report.get("independent_validation") is not False
        or report.get("may_promote_to_product") is not False
        or report.get("may_merge_release") is not False
        or report.get("may_execute_tools") is not False
        or report.get("may_auto_merge_pr") is not False
    ):
        raise ValueError("report attempts to authorize unsafe issue mutation")
    state = validate_state(report["state"])
    results = report.get("new_results")
    if not isinstance(results, list) or len(results) > 2 or not results:
        raise ValueError("no complete registered experiment to synchronize")
    allowed = {entry["variant"] for entry in state["results"]}
    source_state = {entry["variant"]: entry for entry in state["results"]}
    _, corpus, digest = load_inputs()
    if digest != CORPUS_SHA:
        raise ValueError("experiment source corpus has changed")
    run_id = int(run_url.rsplit("/", 1)[-1])
    seen: set[str] = set()
    for trial in results:
        if not isinstance(trial, dict) or trial.get("variant") not in VARIANTS:
            raise ValueError("unregistered experiment evidence")
        variant = trial["variant"]
        if variant in seen or variant not in allowed:
            raise ValueError("duplicate/uncommitted experiment evidence")
        seen.add(variant)
        metric = trial.get("metrics")
        rows = trial.get("rows")
        if not isinstance(metric, dict) or not isinstance(rows, list):
            raise ValueError("incomplete trial evidence")
        audited = _metric_rows({
            "corpus_sha256": digest,
            "independent_validation": False,
            "grants_execution_authority": False,
            "rows": rows,
        }, corpus, digest, arm=variant)
        if (
            trial.get("run_id") != run_id
            or source_state[variant]["run_id"] != run_id
            or any(
                type(metric.get(display)) is not int
                or metric[display] != audited[audit_key]
                or metric[display] != source_state[variant][display]
                for display, audit_key in (
                    ("supported_correct", "supported_correct"),
                    ("supported_wrong", "supported_wrong"),
                    ("supported_refused", "supported_refused"),
                    ("unsupported_false_accepted", "unsupported_false_accepted"),
                )
            )
        ):
            raise ValueError("per-case evidence does not match issue metrics")
    # Validate every trial first: no partial issue changes on invalid input.
    numbers = []
    for trial in results:
        variant = trial["variant"]
        identity = f"{MARKER}/{variant}"
        title = f"[AutoLab DEV] Measure {variant}"
        raw = gh([
            "issue", "list", "--repo", REPO, "--state", "all",
            "--search", f"in:body {identity}",
            "--json", "number,title,body,author", "--limit", "100",
        ])
        matches = [
            issue for issue in json.loads(raw)
            if issue.get("title") == title
            and identity in issue.get("body", "")
        ]
        if len(matches) > 1:
            raise ValueError("ambiguous scoped issue identity")
        if matches:
            issue = matches[0]
            author = issue.get("author")
            if not isinstance(author, dict) or author.get("login") != (
                "github-actions[bot]"
            ):
                raise ValueError("refuse to close human-authored issue")
            number = issue["number"]
            if type(number) is not int or number <= 0:
                raise ValueError("malformed experiment issue")
        else:
            body = (
                f"<!-- {identity} -->\n"
                "Scope: execute and preserve one **DEV-only measurement**.\n"
                f"Measured evidence: {run_url}\n"
                "Completion refers only to measurement, NOT independent quality, "
                "agent safety or model promotion.\n"
                "Parent research program: #1405; #1291/#1339/#1346 stay open.\n"
            )
            created = gh([
                "issue", "create", "--repo", REPO,
                "--title", title, "--body", body,
            ])
            if not re.fullmatch(
                r"https://github\.com/JDeun/SchemaRouter/issues/[1-9][0-9]*",
                created,
            ):
                raise ValueError("did not receive canonical issue creation URL")
            number = int(created.rsplit("/", 1)[-1])
        metric = trial["metrics"]
        comment = (
            f"Measured in {run_url}. Supported correct "
            f"{metric['supported_correct']}/54; wrong "
            f"{metric['supported_wrong']}/54; refused "
            f"{metric['supported_refused']}/54; unsupported false accepts "
            f"{metric['unsupported_false_accepted']}/18. "
            "Closed as **measurement completed only**, never qualified."
        )
        gh([
            "issue", "close", str(number), "--repo", REPO,
            "--reason", "completed", "--comment", comment,
        ])
        numbers.append(number)
    return numbers


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if os.environ.get("GITHUB_REPOSITORY") != REPO:
        raise ValueError("GitHub repository mismatch")
    if os.environ.get("GITHUB_EVENT_NAME") not in {
        "push", "workflow_dispatch", "schedule",
    }:
        raise ValueError("issue lifecycle is disabled for PR checks")
    if os.environ.get("GITHUB_REF") != "refs/heads/main":
        raise ValueError("issue lifecycle requires merged main")
    run_id = os.environ["GITHUB_RUN_ID"]
    if not run_id.isdigit() or int(run_id) <= 0:
        raise ValueError("missing Actions run identity")
    report = json.loads(args.report.read_text(encoding="utf-8"))
    run_url = f"https://github.com/{REPO}/actions/runs/{run_id}"
    numbers = sync_issues(
        report, run_url=run_url, github_repo=REPO,
    )
    print(json.dumps({
        "scoped_benchmark_issues_closed": numbers,
        "never_closed_product_or_release_issues": [
            1291, 1339, 1346, 1356, 1403, PARENT_ISSUE,
        ],
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
