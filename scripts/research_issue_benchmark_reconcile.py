"""Conservative GitHub workflow_run -> benchmark issue evidence reconciliation.

Only an allowlisted, completed, successful DEV workflow matching a bot-owned
dispatch receipt, exact main SHA and expected non-expired artifact is eligible
for a *status comment*. Never close external-validation or product issues.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from scripts.research_issue_benchmark_scheduler import (
    END,
    MARKER,
    READY,
    fingerprint,
    flatten,
    load_registry,
)

REPO = "JDeun/SchemaRouter"
PARENT = 1405
CONFIRMED = "<!-- schemarouter-benchmark-confirmation-v1:"
WORKFLOWS = {
    "ClicShopping 4.33 Offline Development Benchmark": (
        "clicshopping_public_dev", 1208, "clicshopping-v433-offline-dev-",
    ),
    "Clear Your Tools Development Smoke": (
        "clear_your_tools_public_dev", 839,
        "clear-your-tools-development-smoke",
    ),
}
SHA = re.compile(r"^[0-9a-f]{40}$")


def receipts(comments: Any) -> list[dict[str, Any]]:
    results = []
    for comment in flatten(comments):
        if comment.get("user", {}).get("login") != "github-actions[bot]":
            continue
        for line in str(comment.get("body", "")).splitlines():
            if not (line.startswith(MARKER) and line.endswith(END)):
                continue
            try:
                value = json.loads(line[len(MARKER):-len(END)])
            except (TypeError, ValueError):
                continue
            if isinstance(value, dict) and value.get("status") == (
                "DISPATCH_REQUESTED_NOT_BENCHMARK_SUCCESS"
            ):
                results.append(value)
    return results


def verified_result(
    run: dict[str, Any],
    artifact_payload: dict[str, Any],
    dispatch_comments: Any,
    existing_issue_comments: Any,
    *,
    registry: dict[str, Any] | None = None,
) -> dict[str, Any]:
    registry = load_registry() if registry is None else registry
    name = run.get("name")
    if name not in WORKFLOWS:
        raise ValueError("workflow outside fixed DEV allowlist")
    experiment, issue_number, artifact_prefix = WORKFLOWS[name]
    run_id = run.get("id")
    sha = run.get("head_sha")
    if (
        type(run_id) is not int or run_id <= 0
        or not isinstance(sha, str) or SHA.fullmatch(sha) is None
        or run.get("status") != "completed"
        or run.get("conclusion") != "success"
        or run.get("event") != "workflow_dispatch"
        or run.get("head_branch") != "main"
        or run.get("repository", {}).get("full_name") != REPO
    ):
        raise ValueError("run is not a successful, main-scoped DEV dispatch")
    entries = [
        entry for entry in registry["benchmark_entries"]
        if entry["id"] == experiment and entry["mode"] == "ready"
    ]
    if len(entries) != 1:
        raise ValueError("registered issue or workflow not active")
    entry = entries[0]
    if (entry["issue"], entry["workflow"]) != READY[experiment]:
        raise ValueError("workflow or issue registration differs")
    digest = fingerprint(entry, sha)
    matches = [
        value for value in receipts(dispatch_comments)
        if value.get("experiment") == experiment
        and value.get("issue") == issue_number
        and value.get("fingerprint") == digest
        and value.get("main_sha") == sha
    ]
    if not matches:
        raise ValueError("matching bot-owned dispatch receipt not found")
    if artifact_payload.get("total_count", 0) < 1:
        raise ValueError("no run artifact evidence")
    items = artifact_payload.get("artifacts")
    if not isinstance(items, list):
        raise ValueError("artifact manifest missing")
    matches_artifact = [
        item for item in items
        if isinstance(item, dict)
        and item.get("workflow_run", {}).get("id") == run_id
        and isinstance(item.get("name"), str)
        and (
            item["name"] == artifact_prefix
            if experiment == "clear_your_tools_public_dev"
            else item["name"] == f"{artifact_prefix}{run_id}"
        )
        and item.get("expired") is False
        and type(item.get("size_in_bytes")) is int
        and item["size_in_bytes"] > 0
        and type(item.get("id")) is int
        and item["id"] > 0
    ]
    if len(matches_artifact) != 1:
        raise ValueError("exact nonexpired output artifact not verified")
    artifact = matches_artifact[0]
    marker = (
        f'{CONFIRMED}{json.dumps({"experiment": experiment, "run_id": run_id, "sha": sha}, sort_keys=True, separators=(",", ":"))}{END}'
    )
    if any(
        item.get("user", {}).get("login") == "github-actions[bot]"
        and marker in str(item.get("body", ""))
        for item in flatten(existing_issue_comments)
    ):
        return {
            "status": "ALREADY_RECONCILED",
            "issue": issue_number,
            "run_id": run_id,
            "may_close_issue": False,
            "may_promote_model": False,
        }
    url = f"https://github.com/{REPO}/actions/runs/{run_id}"
    artifact_url = f"{url}/artifacts/{artifact['id']}"
    body = (
        f"Automatic DEV benchmark evidence reconciliation for registered "
        f"`{experiment}`.\n\n"
        f"Workflow completed successfully: {url}\n"
        f"Exact available output artifact: {artifact_url}\n"
        f"Source commit: `{sha}`\n"
        "This confirms workflow execution and artifact publication only; "
        "it does **not** establish independent quality, real-agent success, "
        "external qualification, production readiness, or issue resolution. "
        "Keep this broader external-validation issue OPEN.\n\n"
        f"{marker}\n"
    )
    return {
        "status": "COMMENT_ONLY",
        "issue": issue_number,
        "run_id": run_id,
        "body": body,
        "may_close_issue": False,
        "may_promote_model": False,
        "may_release": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--artifacts", type=Path, required=True)
    parser.add_argument("--dispatch-comments", type=Path, required=True)
    parser.add_argument("--issue-comments", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = verified_result(
        json.loads(args.run.read_text(encoding="utf-8")),
        json.loads(args.artifacts.read_text(encoding="utf-8")),
        json.loads(args.dispatch_comments.read_text(encoding="utf-8")),
        json.loads(args.issue_comments.read_text(encoding="utf-8")),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        key: value for key, value in result.items() if key != "body"
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
