"""GitHub issue lifecycle contract tests, no GitHub requests."""
from __future__ import annotations

import copy
import json
from typing import Any

import pytest

from scripts.research_operation_fit_auto_loop import (
    KINDS,
    empty_state,
    loop,
    protocol,
)
from scripts.research_operation_fit_issue_sync import (
    MARKER,
    REPO,
    sync_issues,
)

RUN_URL = "https://github.com/JDeun/SchemaRouter/actions/runs/777"


def fake_score(
    _query: str, _hypotheses: tuple[str, ...],
) -> tuple[dict[str, float], dict[str, float]]:
    entail = {key: 0.01 for key in KINDS}
    contradict = {key: 0.05 for key in KINDS}
    entail["search"] = 0.99
    return entail, contradict


def report_fixture() -> dict[str, Any]:
    _, corpus, _ = protocol()
    return loop(empty_state(), corpus, fake_score, 777)


def test_creates_and_closes_only_bot_owned_scoped_measurement_issues() -> None:
    report = report_fixture()
    calls: list[list[str]] = []
    next_issue = [2100]

    def gh(args: list[str]) -> str:
        calls.append(args)
        if args[:2] == ["issue", "list"]:
            assert args[args.index("--search") + 1].startswith(
                f"in:body {MARKER}/"
            )
            return "[]"
        if args[:2] == ["issue", "create"]:
            next_issue[0] += 1
            assert "DEV" in args[args.index("--title") + 1]
            body = args[args.index("--body") + 1]
            assert "NOT independent quality" in body
            return f"https://github.com/{REPO}/issues/{next_issue[0]}"
        if args[:2] == ["issue", "close"]:
            assert int(args[2]) in {2101, 2102}
            assert args[args.index("--reason") + 1] == "completed"
            assert "measurement completed only" in args[-1]
            return ""
        raise AssertionError(args)

    closed = sync_issues(
        report, run_url=RUN_URL, github_repo=REPO, gh=gh,
    )
    assert closed == [2101, 2102]
    assert [call[:2] for call in calls] == [
        ["issue", "list"], ["issue", "create"], ["issue", "close"],
        ["issue", "list"], ["issue", "create"], ["issue", "close"],
    ]
    assert all(str(issue) not in {str(x) for x in closed} for issue in [
        1291, 1339, 1346, 1356, 1403, 1405,
    ])


def test_existing_bot_owned_measurement_can_be_closed_idempotently() -> None:
    report = report_fixture()
    seen: list[list[str]] = []

    def gh(args: list[str]) -> str:
        seen.append(args)
        if args[:2] == ["issue", "list"]:
            identity = args[args.index("--search") + 1].replace(
                "in:body ", ""
            )
            return json.dumps([{
                "number": 4551,
                "title": f"[AutoLab DEV] Measure {identity.split('/')[-1]}",
                "body": f"<!-- {identity} -->",
                "author": {"login": "github-actions[bot]"},
            }])
        if args[:2] == ["issue", "close"]:
            return ""
        raise AssertionError("no unneeded duplicate issues")

    numbers = sync_issues(report, run_url=RUN_URL, github_repo=REPO, gh=gh)
    assert numbers == [4551, 4551]
    assert not any(args[:2] == ["issue", "create"] for args in seen)


def test_never_closes_human_issue_even_if_title_and_body_match() -> None:
    report = report_fixture()
    called: list[list[str]] = []

    def gh(args: list[str]) -> str:
        called.append(args)
        identity = args[args.index("--search") + 1].replace("in:body ", "")
        return json.dumps([{
            "number": 1291,
            "title": f"[AutoLab DEV] Measure {identity.split('/')[-1]}",
            "body": f"<!-- {identity} -->",
            "author": {"login": "human"},
        }])

    with pytest.raises(ValueError, match="human-authored"):
        sync_issues(report, run_url=RUN_URL, github_repo=REPO, gh=gh)
    assert called and all(c[:2] == ["issue", "list"] for c in called)


@pytest.mark.parametrize("case", [
    "different_repository", "forged_release", "missing_row",
    "incomplete_cohort", "unregistered_variant", "invalid_url",
])
def test_invalid_evidence_produces_zero_issue_actions(case: str) -> None:
    report = report_fixture()
    run_url = RUN_URL
    repository = REPO
    if case == "different_repository":
        repository = "someone/other-repo"
    elif case == "forged_release":
        report["may_merge_release"] = True
    elif case == "missing_row":
        report["new_results"][0]["rows"].pop()
    elif case == "incomplete_cohort":
        report["new_results"][0]["metrics"]["supported_refused"] += 1
    elif case == "unregistered_variant":
        report["new_results"][0]["variant"] = "unapproved_model"
    elif case == "invalid_url":
        run_url = "https://attacker.example.com/actions/runs/777"
    called: list[list[str]] = []
    with pytest.raises(ValueError):
        sync_issues(
            report, run_url=run_url, github_repo=repository,
            gh=lambda args: called.append(args) or "",
        )
    assert called == []


def test_fake_resume_with_authority_drift_is_never_accepted() -> None:
    report = copy.deepcopy(report_fixture())
    report["state"]["may_promote_to_product"] = True
    with pytest.raises(ValueError):
        sync_issues(
            report, run_url=RUN_URL, github_repo=REPO,
            gh=lambda _args: "[]",
        )
