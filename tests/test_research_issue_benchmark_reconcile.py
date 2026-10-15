"""Successful DEV workflow evidence may update status, never resolve an issue."""
from __future__ import annotations

import pytest

from scripts.research_issue_benchmark_reconcile import (
    WORKFLOWS,
    verified_result,
)
from scripts.research_issue_benchmark_scheduler import (
    READY,
    dispatch_receipt,
    fingerprint,
    load_registry,
)

SHA = "f" * 40
RUN = 44881234


def fixtures(
    name: str = "ClicShopping 4.33 Offline Development Benchmark",
) -> tuple[dict, dict, list, list]:
    key, issue, prefix = WORKFLOWS[name]
    registry = load_registry()
    entry = next(x for x in registry["benchmark_entries"] if x["id"] == key)
    run = {
        "id": RUN, "name": name, "head_sha": SHA, "head_branch": "main",
        "status": "completed", "conclusion": "success",
        "event": "workflow_dispatch",
        "repository": {"full_name": "JDeun/SchemaRouter"},
    }
    artifacts = {
        "total_count": 1,
        "artifacts": [{
            "id": 992, "workflow_run": {"id": RUN},
            "name": prefix if key == "clear_your_tools_public_dev"
            else prefix + str(RUN),
            "expired": False, "size_in_bytes": 3456,
        }],
    }
    receipt = dispatch_receipt({
        "id": key, "issue": issue,
        "workflow": READY[key][1],
        "fingerprint": fingerprint(entry, SHA),
    }, SHA)
    comments = [{
        "user": {"login": "github-actions[bot]"},
        "body": "DEV dispatch request, not results\n" + receipt,
    }]
    return run, artifacts, comments, []


@pytest.mark.parametrize("name", list(WORKFLOWS))
def test_successful_pinned_run_allows_only_evidence_comment(name: str) -> None:
    run, artifacts, comments, existing = fixtures(name)
    decision = verified_result(run, artifacts, comments, existing)
    assert decision["status"] == "COMMENT_ONLY"
    assert decision["run_id"] == RUN
    assert decision["may_close_issue"] is False
    assert decision["may_promote_model"] is False
    assert decision["may_release"] is False
    assert "not" in decision["body"].lower()
    assert "artifact" in decision["body"].lower()
    assert decision["issue"] in (1208, 839)


def test_repeated_completion_is_idempotent() -> None:
    run, artifacts, comments, _ = fixtures()
    first = verified_result(run, artifacts, comments, [])
    next_comments = [{
        "user": {"login": "github-actions[bot]"},
        "body": first["body"],
    }]
    second = verified_result(run, artifacts, comments, next_comments)
    assert second["status"] == "ALREADY_RECONCILED"
    assert second["may_close_issue"] is False


@pytest.mark.parametrize("field,value", [
    ("event", "pull_request"),
    ("status", "in_progress"),
    ("conclusion", "failure"),
    ("head_branch", "test-feature"),
    ("head_sha", "bad"),
    ("id", True),
    ("name", "Release"),
])
def test_nonqualifying_workflow_is_never_acknowledged(
    field: str, value: object,
) -> None:
    run, artifacts, comments, existing = fixtures()
    run[field] = value
    with pytest.raises(ValueError):
        verified_result(run, artifacts, comments, existing)


@pytest.mark.parametrize("mutation", [
    "unknown_user", "missing_receipt", "wrong_source", "wrong_fingerprint",
    "expired", "wrong_name", "missing_artifact", "wrong_run_id",
])
def test_incomplete_provenance_fails_closed(mutation: str) -> None:
    run, artifacts, comments, existing = fixtures()
    if mutation == "unknown_user":
        comments[0]["user"]["login"] = "random-contributor"
    elif mutation == "missing_receipt":
        comments = []
    elif mutation == "wrong_source":
        run["head_sha"] = "0" * 40
    elif mutation == "wrong_fingerprint":
        comments[0]["body"] = comments[0]["body"].replace(
            fingerprint(load_registry()["benchmark_entries"][0], SHA),
            "0" * 64,
        )
    elif mutation == "expired":
        artifacts["artifacts"][0]["expired"] = True
    elif mutation == "wrong_name":
        artifacts["artifacts"][0]["name"] = "fake"
    elif mutation == "missing_artifact":
        artifacts["artifacts"] = []
    elif mutation == "wrong_run_id":
        artifacts["artifacts"][0]["workflow_run"]["id"] = RUN - 1
    with pytest.raises(ValueError):
        verified_result(run, artifacts, comments, existing)


def test_no_write_status_cannot_be_forged_by_human_comment() -> None:
    run, artifacts, comments, existing = fixtures()
    first = verified_result(run, artifacts, comments, existing)
    marker = first["body"].splitlines()[-1]
    spoof = [{"user": {"login": "human"}, "body": marker}]
    assert verified_result(run, artifacts, comments, spoof)["status"] == "COMMENT_ONLY"
