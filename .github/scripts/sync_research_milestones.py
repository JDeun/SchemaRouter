#!/usr/bin/env python3
"""Opt-in GitHub milestone creation/assignment. Preview is offline and read-only."""

from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

PLAN = Path(__file__).resolve().parents[1] / "research-milestones.json"
REPO = "JDeun/SchemaRouter"


def load_plan() -> dict[str, Any]:
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    if plan.get("schema_version") != 1 or plan.get("repository") != REPO:
        raise ValueError("unexpected milestone mapping repository/version")
    stages = plan.get("milestones", [])
    if [stage.get("key") for stage in stages] != [f"M{i}" for i in range(6)]:
        raise ValueError("expected exactly six ordered milestone stages")
    ids: list[int] = []
    names: set[str] = set()
    for stage in stages:
        title = stage.get("title")
        issues = stage.get("issues")
        if not isinstance(title, str) or not title.startswith(stage["key"] + " — "):
            raise ValueError("invalid milestone title")
        if title in names or not isinstance(issues, list) or not issues:
            raise ValueError("duplicate title or missing issue list")
        if not isinstance(stage.get("gate"), str) or not stage["gate"].strip():
            raise ValueError("missing milestone evidence gate")
        if any(isinstance(n, bool) or not isinstance(n, int) or n <= 0 for n in issues):
            raise ValueError("invalid issue identifier")
        ids.extend(issues)
        names.add(title)
    if len(ids) != 30 or len(set(ids)) != 30 or plan.get("unassigned_cross_cutting") != [200]:
        raise ValueError("unexpected issue count, duplicates or cross-cutting tracker")
    if 1345 not in next(s["issues"] for s in stages if s["key"] == "M4"):
        raise ValueError("release gate parent #1345 is not assigned to M4")
    return plan


def api(token: str, method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
    if not path.startswith(f"/repos/{REPO}/"):
        raise ValueError("invalid API scope")
    raw = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        "https://api.github.com" + path,
        data=raw,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "SchemaRouter-Milestone-Plan",
            **({"Content-Type": "application/json"} if raw is not None else {}),
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            data = response.read()
            return json.loads(data) if data else None
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"GitHub {method} {path}: HTTP {exc.code}") from exc


def apply(plan: dict[str, Any], token: str) -> None:
    if os.environ.get("GITHUB_REPOSITORY") != REPO:
        raise ValueError("apply requires exact GitHub Actions repository identity")
    known: dict[str, dict[str, Any]] = {}
    for page in range(1, 21):
        items = api(token, "GET", f"/repos/{REPO}/milestones?state=all&per_page=100&page={page}")
        if not isinstance(items, list):
            raise ValueError("unexpected milestone API response")
        for milestone in items:
            title = milestone["title"]
            if title in known:
                raise ValueError(f"duplicate existing milestone name: {title}")
            known[title] = milestone
        if len(items) < 100:
            break
    else:
        raise ValueError("milestone listing exceeds safe pagination bound")

    # Reject all closed milestones before ANY write, even if the closed
    # milestone belongs to a later stage. Avoid partial application.
    for stage in plan["milestones"]:
        existing = known.get(stage["title"])
        if existing is not None and existing.get("state") != "open":
            raise ValueError(f"existing milestone is closed: {stage['title']}")

    # All issues are checked before ANY create/assign write.
    eligible: dict[int, dict[str, Any]] = {}
    for stage in plan["milestones"]:
        for n in stage["issues"]:
            issue = api(token, "GET", f"/repos/{REPO}/issues/{n}")
            if not isinstance(issue, dict) or "pull_request" in issue:
                raise ValueError(f"#{n}: invalid issue or PR")
            if issue["state"] != "open":
                print(f"SKIP closed #{n}")
                continue
            current = issue.get("milestone")
            if current and current.get("title") != stage["title"]:
                raise ValueError(f"#{n} already belongs to another milestone; abort")
            eligible[n] = issue

    for stage in plan["milestones"]:
        title = stage["title"]
        milestone = known.get(title)
        if milestone and milestone.get("state") != "open":
            raise ValueError(f"existing milestone is closed: {title}")
        if milestone is None:
            milestone = api(token, "POST", f"/repos/{REPO}/milestones", {
                "title": title, "state": "open", "description": stage["gate"]
            })
            known[title] = milestone
            print(f"CREATED {title} #{milestone['number']}")
        else:
            print(f"EXISTS {title} #{milestone['number']}")
        for n in stage["issues"]:
            current = eligible.get(n)
            if current is None or (
                current.get("milestone") and
                current["milestone"]["number"] == milestone["number"]
            ):
                continue
            # Avoid overwriting an assignment changed after the initial preflight.
            live = api(token, "GET", f"/repos/{REPO}/issues/{n}")
            if not isinstance(live, dict) or "pull_request" in live:
                raise ValueError(f"#{n}: changed into an invalid issue")
            if live.get("state") != "open":
                print(f"SKIP newly closed #{n}")
                continue
            live_milestone = live.get("milestone")
            if live_milestone:
                if live_milestone.get("number") == milestone["number"]:
                    print(f"ALREADY ASSIGNED #{n} -> {title}")
                    continue
                raise ValueError(
                    f"#{n}: milestone changed since preflight; refuse overwrite"
                )
            api(token, "PATCH", f"/repos/{REPO}/issues/{n}", {
                "milestone": milestone["number"]
            })
            print(f"ASSIGNED issue #{n} -> {title}")
    print("SYNC COMPLETE: no issue closures, PR merges, release tags or due dates")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    plan = load_plan()
    if not args.apply:
        for stage in plan["milestones"]:
            print(f"PREVIEW {stage['key']}: {stage['title']}: {stage['issues']}")
        print("Cross-cutting issue #200 stays unassigned. NO NETWORK OR WRITES.")
        return
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        raise SystemExit("apply requires Issues-write GITHUB_TOKEN or GH_TOKEN")
    apply(plan, token)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, RuntimeError) as exc:
        raise SystemExit(str(exc)) from exc
