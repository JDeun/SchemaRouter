"""Regression coverage for the exact-main qualification watchdog workflow."""

from __future__ import annotations

import json
import os
import textwrap
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from urllib.parse import urlparse
from urllib.request import Request


WORKFLOW = (
    Path(__file__).resolve().parents[1]
    / ".github/workflows/post-merge-qualification-watchdog.yml"
)
BASELINE = "d3c4cb486c6556e50dee035ddd58b49ca66b4543"
HEAD = "0123456789abcdef0123456789abcdef01234567"
OLD = "fedcba9876543210fedcba9876543210fedcba98"


def _watchdog_source() -> str:
    source = WORKFLOW.read_text(encoding="utf-8")
    embedded = source.split("          python - <<'PY'\n", 1)[1].split("\n          PY", 1)[0]
    return textwrap.dedent(embedded)


class _FakeResponse:
    def __init__(self, payload: object) -> None:
        self.payload = json.dumps(payload).encode("utf-8")

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *args: object) -> None:
        pass

    def read(self, *args: object) -> bytes:
        return self.payload


def _run_watchdog(*, new_status: str, unrelated_failure: bool = False) -> dict:
    now = datetime.now(timezone.utc)
    old_date = (now - timedelta(hours=3)).isoformat()
    new_date = (now - timedelta(minutes=3)).isoformat()
    commits = {
        HEAD: {
            "sha": HEAD,
            "parents": [{"sha": OLD if unrelated_failure else BASELINE}, {"sha": OLD}],
            "commit": {"committer": {"date": new_date}},
        },
        BASELINE: {
            "sha": BASELINE,
            "parents": [{"sha": OLD}],
            "commit": {"committer": {"date": old_date}},
        },
        OLD: {
            "sha": OLD,
            "parents": [{"sha": BASELINE}],
            "commit": {"committer": {"date": old_date}},
        },
    }
    runs = [
        {
            "name": "Post-merge Qualification",
            "head_sha": BASELINE,
            "status": "completed",
            "conclusion": "cancelled",
            "id": 42,
            "run_attempt": 1,
        },
        {
            "name": "Post-merge Qualification",
            "head_sha": HEAD,
            "status": "completed" if new_status == "success" else "in_progress",
            "conclusion": "success" if new_status == "success" else None,
            "id": 43,
            "run_attempt": 1,
        },
    ]
    if unrelated_failure:
        runs.append(
            {
                "name": "Post-merge Qualification",
                "head_sha": OLD,
                "status": "completed",
                "conclusion": "failure",
                "id": 44,
                "run_attempt": 1,
            }
        )

    def fake_urlopen(request: Request, *, timeout: int) -> _FakeResponse:
        assert timeout == 20
        path = urlparse(request.full_url).path
        if path.endswith("/git/ref/heads/main"):
            return _FakeResponse({"object": {"sha": HEAD}})
        if "/commits/" in path:
            return _FakeResponse(commits[path.split("/commits/", 1)[1]])
        if path.endswith("/actions/runs"):
            return _FakeResponse({"workflow_runs": runs})
        raise AssertionError(f"Unexpected API path: {path}")

    env = {
        "GITHUB_API_URL": "https://api.github.com",
        "GITHUB_REPOSITORY": "JDeun/SchemaRouter",
        "GH_TOKEN": "synthetic-test-token",
        "LOOKBACK_COMMITS": "12",
        "MISSING_GRACE_MINUTES": "20",
        "STALE_RUN_MINUTES": "105",
        "INITIAL_QUALIFICATION_SHA": BASELINE,
    }
    with (
        TemporaryDirectory() as temporary_path,
        patch("urllib.request.urlopen", fake_urlopen),
        patch.dict(os.environ, env),
    ):
        previous_cwd = Path.cwd()
        os.chdir(temporary_path)
        try:
            try:
                with redirect_stdout(StringIO()):
                    exec(
                        compile(_watchdog_source(), str(WORKFLOW), "exec"),
                        {"__name__": "__main__"},
                    )
            except SystemExit:
                pass
            artifact = Path("artifacts/post-merge-qualification-watchdog.json")
            return json.loads(artifact.read_text(encoding="utf-8"))
        finally:
            os.chdir(previous_cwd)


class PostMergeQualificationWatchdogTests(unittest.TestCase):
    def test_known_cancelled_baseline_superseded_only_by_successful_descendant(self) -> None:
        report = _run_watchdog(new_status="success")
        self.assertEqual(report["failures"], [])
        self.assertEqual(report["commits"][1]["qualification"], "superseded_by_successful_main")
        self.assertEqual(report["commits"][1]["conclusion"], "cancelled")

    def test_known_cancelled_baseline_still_fails_without_completed_descendant(self) -> None:
        report = _run_watchdog(new_status="in_progress")
        self.assertTrue(any(BASELINE in failure for failure in report["failures"]))

    def test_other_failed_main_commit_is_not_excused(self) -> None:
        report = _run_watchdog(new_status="success", unrelated_failure=True)
        self.assertTrue(any(OLD in failure for failure in report["failures"]))
