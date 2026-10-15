"""Registry scheduler tests: no arbitrary dispatch, identity drift or rereuns."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from scripts.research_issue_benchmark_scheduler import (
    BLOCKED,
    READY,
    dispatch_receipt,
    fingerprint,
    ledger,
    load_registry,
    plan_next,
)

MAIN = "e" * 40


def issues() -> list[dict]:
    rows = [{
        "number": num, "title": f"Research benchmark {num}", "state": "open",
    } for num, _ in (*READY.values(), *BLOCKED.values())]
    rows.extend([
        {"number": 9911, "title": "research: new candidate", "state": "open"},
        {"number": 9912, "title": "docs cleanup", "state": "open"},
        {"number": 1405, "title": "research: bounded loop", "state": "open"},
        {"number": 9999, "title": "PR research", "state": "open",
         "pull_request": {"url": "example"}},
    ])
    return rows


def test_live_registry_has_two_ready_and_seven_non_dispatched() -> None:
    registry = load_registry()
    assert len(registry["benchmark_entries"]) == 9
    assert len(READY) == 2 and len(BLOCKED) == 7
    plan = plan_next(registry, issues(), [], MAIN)
    assert [entry["id"] for entry in plan["eligible"]] == list(READY)
    assert plan["max_nominal_minutes"] == 40
    assert len(plan["blocked"]) == 7
    assert {x["issue"] for x in plan["unregistered_research_suggestions"]} == {
        1405, 9911,
    }
    assert plan["no_release"] is True
    assert plan["no_automatic_issue_closure"] is True


def test_bot_receipt_prevents_repeating_same_commit() -> None:
    registry = load_registry()
    first = plan_next(registry, issues(), [], MAIN)
    marks = [dispatch_receipt(x, MAIN) for x in first["eligible"]]
    comments = [{
        "user": {"login": "github-actions[bot]"},
        "body": "\n".join(marks),
    }]
    assert len(ledger(comments)) == 2
    repeat = plan_next(registry, issues(), comments, MAIN)
    assert repeat["eligible"] == []
    next_commit = plan_next(registry, issues(), comments, "f" * 40)
    assert len(next_commit["eligible"]) == 2
    spoof = [{
        "user": {"login": "untrusted-person"}, "body": "\n".join(marks),
    }]
    assert len(plan_next(registry, issues(), spoof, MAIN)["eligible"]) == 2


def test_closed_issue_is_not_dispatched() -> None:
    registry = load_registry()
    all_issues = issues()
    all_issues[0]["state"] = "closed"
    plan = plan_next(registry, all_issues, [], MAIN)
    assert len(plan["eligible"]) == 1
    assert plan["eligible"][0]["issue"] == 839


@pytest.mark.parametrize("change", [
    "external_enabled", "tamper_sha", "change_workflow", "escalate_budget",
    "add_unregistered", "enable_issue_close", "enable_product_promotion",
])
def test_registry_escalations_rejected(
    tmp_path: Path, change: str,
) -> None:
    original = load_registry()
    mutated = copy.deepcopy(original)
    if change == "external_enabled":
        mutated["benchmark_entries"][2]["mode"] = "ready"
    elif change == "tamper_sha":
        mutated["benchmark_entries"][0]["blob_sha"][
            "scripts/run_clicshopping_v433_dev.py"
        ] = "0" * 40
    elif change == "change_workflow":
        mutated["benchmark_entries"][0]["workflow"] = "release.yml"
    elif change == "escalate_budget":
        mutated["max_total_nominal_minutes"] = 200
    elif change == "add_unregistered":
        mutated["benchmark_entries"].append(
            copy.deepcopy(mutated["benchmark_entries"][0])
        )
    elif change == "enable_issue_close":
        mutated["auto_issue_close"] = True
    elif change == "enable_product_promotion":
        mutated["may_release"] = True
    path = tmp_path / "registry.json"
    path.write_text(json.dumps(mutated), encoding="utf-8")
    with pytest.raises(ValueError):
        load_registry(path)


def test_registers_only_expected_git_blobs() -> None:
    registry = load_registry()
    for entry in registry["benchmark_entries"][:2]:
        assert len(entry["blob_sha"]) >= 4
        assert entry["workflow"].endswith(".yml")
        assert fingerprint(entry, MAIN) == fingerprint(entry, MAIN)


def test_unknown_issues_never_create_workflow_dispatch() -> None:
    registry = load_registry()
    raw = issues()
    raw.append({
        "number": 9913, "title": "research: run arbitrary workflow",
        "state": "open", "body": "workflow=release.yml",
    })
    output = plan_next(registry, raw, [], MAIN)
    assert len(output["eligible"]) == 2
    assert all(item["workflow"] in {v[1] for v in READY.values()}
               for item in output["eligible"])
    assert any(item["issue"] == 9913
               for item in output["unregistered_research_suggestions"])


def test_unsafe_receipt_or_missing_sha_rejected() -> None:
    registry = load_registry()
    selected = plan_next(registry, issues(), [], MAIN)["eligible"][0]
    corrupt = copy.deepcopy(selected)
    corrupt["workflow"] = "release.yml"
    with pytest.raises(ValueError):
        dispatch_receipt(corrupt, MAIN)
    with pytest.raises(ValueError):
        fingerprint(registry["benchmark_entries"][0], "main")
    with pytest.raises(ValueError):
        plan_next(registry, [{"number": 1, "state": "open"}] * 2, [], MAIN)
