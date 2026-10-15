"""Fixed-cost issue-bound benchmark scheduling, never arbitrary issue execution.

Inputs: paginated GitHub open issues, bot-owned ledger comments and verified
source blobs. Selection cannot accept workflow names/commands from an issue.
Only pinned no-secret DEV studies are dispatchable; all other open research
issues are *suggestions*, never dynamic actions or independent evidence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "benchmarks/research-issue-benchmark-scheduler-v1.json"
MARKER = "<!-- schemarouter-benchmark-dispatch-v1:"
END = " -->"
READY = {
    "clicshopping_public_dev": (1208, "external-validation-clicshopping-v433-dev.yml"),
    "clear_your_tools_public_dev": (839, "clear-your-tools-development-smoke.yml"),
}
BLOCKED = {
    "clicshopping_maintainer_20_holdout": (1311, "blocked"),
    "pi_jev_local_laya": (1312, "blocked"),
    "laya_latency_research": (1313, "reference_only"),
    "nli_collapse_research": (1403, "reference_only"),
    "multilingual_initial_recall": (1339, "blocked"),
    "safeact_v1_independent": (1224, "blocked"),
    "external_release_gate": (1346, "blocked"),
}
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
TOPIC = re.compile(r"research|benchmark|external validation|experiment|safeact|multilingual", re.I)


def git_blob(path: str) -> str:
    result = subprocess.run(
        ["git", "hash-object", "--", path],
        cwd=ROOT, capture_output=True, text=True, check=True,
    )
    return result.stdout.strip()


def load_registry(
    path: Path = REGISTRY_PATH,
    *,
    blobs: Callable[[str], str] = git_blob,
) -> dict[str, Any]:
    doc = json.loads(path.read_text(encoding="utf-8"))
    expected = {
        "schema_version", "id", "scope", "parent_issue", "schedule_owner",
        "max_dispatches_per_schedule", "max_total_nominal_minutes",
        "repeat_policy", "unregistered_issue_policy", "auto_issue_close",
        "auto_pr_merge", "may_release", "may_treat_as_independent",
        "benchmark_entries",
    }
    if not isinstance(doc, dict) or set(doc) != expected:
        raise ValueError("unregistered benchmark scheduler schema")
    if (
        type(doc["schema_version"]) is not int or doc["schema_version"] != 1
        or doc["id"] != "issue-bound-benchmark-scheduler-v1"
        or doc["scope"] != "registered_gitHub_actions_DEV_benchmarks_only"
        or doc["parent_issue"] != 1405
        or doc["schedule_owner"] != "research-operation-fit-auto-loop-dev.yml"
        or doc["max_dispatches_per_schedule"] != 2
        or doc["max_total_nominal_minutes"] != 40
        or doc["repeat_policy"] != "once_per_exact_main_commit_and_registry_fingerprint"
        or doc["unregistered_issue_policy"] != "suggest_only_no_dispatch"
        or any(doc[k] is not False for k in (
            "auto_issue_close", "auto_pr_merge",
            "may_release", "may_treat_as_independent",
        ))
    ):
        raise ValueError("unsafe benchmark schedule or authority escalation")
    entries = doc["benchmark_entries"]
    if not isinstance(entries, list) or [
        x.get("id") for x in entries
    ] != [*READY, *BLOCKED]:
        raise ValueError("unregistered experiment in scheduler")
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {
            "id", "issue", "mode", "workflow", "max_minutes", "blob_sha",
            "source_class", "reason",
        }:
            raise ValueError("malformed benchmark entry")
        if type(entry["issue"]) is not int or not isinstance(entry["reason"], str):
            raise ValueError("invalid benchmark issue provenance")
        if entry["id"] in READY:
            if (
                (entry["issue"], entry["workflow"]) != READY[entry["id"]]
                or entry["mode"] != "ready"
                or type(entry["max_minutes"]) is not int
                or entry["max_minutes"] != 20
                or entry["source_class"] not in {
                    "visible_public_development_only",
                    "synthetic_visible_development_only",
                }
                or not isinstance(entry["blob_sha"], dict)
                or len(entry["blob_sha"]) < 4
                or ".github/workflows/" + entry["workflow"] not in entry["blob_sha"]
            ):
                raise ValueError("unapproved benchmark implementation")
            for path_name, digest in entry["blob_sha"].items():
                if (
                    not isinstance(path_name, str)
                    or not path_name.startswith((
                        ".github/workflows/", "benchmarks/", "scripts/",
                    ))
                    or ".." in Path(path_name).parts
                    or not (ROOT / path_name).is_file()
                    or not isinstance(digest, str) or HEX40.fullmatch(digest) is None
                    or blobs(path_name) != digest
                ):
                    raise ValueError(f"benchmark file integrity failed: {path_name}")
            content = (
                ROOT / ".github/workflows" / entry["workflow"]
            ).read_text(encoding="utf-8")
            if "workflow_dispatch:" not in content:
                raise ValueError("approved workflow lacks explicit dispatch")
        elif (
            (entry["issue"], entry["mode"]) != BLOCKED[entry["id"]]
            or entry["workflow"] is not None
            or entry["max_minutes"] != 0
            or entry["blob_sha"] != {}
        ):
            raise ValueError("blocked historical or external issue enabled")
    return doc


def flatten(pages: Any) -> list[dict[str, Any]]:
    if not isinstance(pages, list):
        raise ValueError("GitHub input must be paginated JSON array")
    result: list[dict[str, Any]] = []
    for part in pages:
        for item in part if isinstance(part, list) else [part]:
            if not isinstance(item, dict):
                raise ValueError("malformed GitHub page")
            result.append(item)
    return result


def ledger(comments: Any) -> set[tuple[str, str]]:
    done = set()
    for item in flatten(comments):
        if item.get("user", {}).get("login") != "github-actions[bot]":
            continue
        content = item.get("body", "")
        if not isinstance(content, str):
            continue
        for line in content.splitlines():
            if not (line.startswith(MARKER) and line.endswith(END)):
                continue
            try:
                receipt = json.loads(line[len(MARKER):-len(END)])
            except (TypeError, ValueError):
                continue
            if (
                isinstance(receipt, dict)
                and receipt.get("experiment") in READY
                and type(receipt.get("issue")) is int
                and receipt["issue"] == READY[receipt["experiment"]][0]
                and isinstance(receipt.get("fingerprint"), str)
                and HEX64.fullmatch(receipt["fingerprint"]) is not None
            ):
                done.add((receipt["experiment"], receipt["fingerprint"]))
    return done


def fingerprint(entry: dict[str, Any], commit: str) -> str:
    if not isinstance(commit, str) or HEX40.fullmatch(commit) is None:
        raise ValueError("must use exact main commit SHA")
    payload = {
        "id": entry["id"], "issue": entry["issue"],
        "workflow": entry["workflow"], "source_commit": commit,
        "blobs": entry["blob_sha"],
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def plan_next(
    registry: dict[str, Any],
    issues: Any,
    comments: Any,
    commit: str,
) -> dict[str, Any]:
    raw = flatten(issues)
    by_number: dict[int, dict[str, Any]] = {}
    for item in raw:
        number = item.get("number")
        if type(number) is not int or number < 1:
            raise ValueError("invalid GitHub issue number")
        if "pull_request" in item:
            continue
        if number in by_number:
            raise ValueError("duplicate GitHub issue")
        by_number[number] = item
    seen = ledger(comments)
    selected = []
    blocked = []
    budget = 0
    for entry in registry["benchmark_entries"]:
        issue = by_number.get(entry["issue"])
        if not issue or issue.get("state") != "open":
            blocked.append({"id": entry["id"], "issue": entry["issue"],
                            "reason": "issue_not_open_or_missing"})
            continue
        if entry["mode"] != "ready":
            blocked.append({"id": entry["id"], "issue": entry["issue"],
                            "reason": entry["reason"]})
            continue
        digest = fingerprint(entry, commit)
        if (entry["id"], digest) in seen:
            blocked.append({"id": entry["id"], "issue": entry["issue"],
                            "reason": "identical_commit_already_dispatched"})
            continue
        if (
            len(selected) >= registry["max_dispatches_per_schedule"]
            or budget + entry["max_minutes"]
            > registry["max_total_nominal_minutes"]
        ):
            blocked.append({"id": entry["id"], "issue": entry["issue"],
                            "reason": "research_budget_exhausted"})
            continue
        budget += entry["max_minutes"]
        selected.append({
            "id": entry["id"], "issue": entry["issue"],
            "workflow": entry["workflow"], "fingerprint": digest,
            "max_minutes": entry["max_minutes"],
        })
    registered_issues = {x["issue"] for x in registry["benchmark_entries"]}
    suggestions = sorted([
        {"issue": num, "title": item.get("title", "")}
        for num, item in by_number.items()
        if num not in registered_issues
        and TOPIC.search(str(item.get("title", "")))
        and item.get("state") == "open"
    ], key=lambda item: item["issue"])
    return {
        "status": "DEV_ONLY_READY_BENCHMARKS_NOT_QUALIFICATION",
        "source_commit": commit,
        "eligible": selected,
        "blocked": blocked,
        "unregistered_research_suggestions": suggestions,
        "max_nominal_minutes": budget,
        "no_automatic_issue_closure": True,
        "no_automatic_model_promotion": True,
        "no_release": True,
    }


def dispatch_receipt(entry: dict[str, Any], commit: str) -> str:
    if entry["id"] not in READY or entry["workflow"] != READY[entry["id"]][1]:
        raise ValueError("unregistered workflow dispatch")
    if type(entry["issue"]) is not int or entry["issue"] != READY[entry["id"]][0]:
        raise ValueError("unregistered research issue")
    if (
        not isinstance(entry.get("fingerprint"), str)
        or HEX64.fullmatch(entry["fingerprint"]) is None
    ):
        raise ValueError("invalid dispatch fingerprint")
    return (
        f"{MARKER}"
        + json.dumps({
            "experiment": entry["id"], "issue": entry["issue"],
            "fingerprint": entry["fingerprint"], "main_sha": commit,
            "status": "DISPATCH_REQUESTED_NOT_BENCHMARK_SUCCESS",
        }, sort_keys=True, separators=(",", ":"))
        + END
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--issues", type=Path, required=True)
    parser.add_argument("--comments", type=Path, required=True)
    parser.add_argument("--sha", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    registry = load_registry()
    result = plan_next(
        registry,
        json.loads(args.issues.read_text(encoding="utf-8")),
        json.loads(args.comments.read_text(encoding="utf-8")),
        args.sha,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, sort_keys=True, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "ready": len(result["eligible"]),
        "blocked": len(result["blocked"]),
        "unregistered_suggestions": len(result["unregistered_research_suggestions"]),
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
