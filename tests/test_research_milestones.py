"""Safety and bookkeeping tests for opt-in research milestone synchronization."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / ".github/scripts/sync_research_milestones.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("milestone_sync_under_test", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_milestone_map_partition_and_release_hold() -> None:
    mod = _load_module()
    plan = mod.load_plan()
    assert len(plan["milestones"]) == 6
    ids = [n for stage in plan["milestones"] for n in stage["issues"]]
    assert len(ids) == len(set(ids)) == 30
    assert plan["unassigned_cross_cutting"] == [200]
    assert 1356 not in ids  # Release candidate PR is not an issue/phase completion.
    assert 1345 in plan["milestones"][4]["issues"]
    assert len(plan["milestones"][3]["issues"]) == 10
    assert all("gate" in stage for stage in plan["milestones"])


def test_default_preview_is_network_free(monkeypatch, capsys) -> None:
    mod = _load_module()

    def no_network(*args, **kwargs):
        raise AssertionError("preview unexpectedly called GitHub")

    monkeypatch.setattr(mod, "api", no_network)
    monkeypatch.setattr("sys.argv", ["milestone_sync"])
    mod.main()
    assert "NO NETWORK OR WRITES" in capsys.readouterr().out


def test_apply_requires_matching_repository_before_requests(monkeypatch) -> None:
    mod = _load_module()
    monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)

    def no_network(*args, **kwargs):
        raise AssertionError("foreign repo must not reach GitHub")

    monkeypatch.setattr(mod, "api", no_network)
    with pytest.raises(ValueError, match="repository identity"):
        mod.apply(mod.load_plan(), "test-token")


def test_plan_fail_closed_on_duplicate_issue(tmp_path: Path) -> None:
    mod = _load_module()
    data = mod.load_plan()
    data["milestones"][0]["issues"].append(data["milestones"][1]["issues"][0])
    test_path = tmp_path / "bad.json"
    test_path.write_text(json.dumps(data), encoding="utf-8")
    monkey = mod.PLAN
    try:
        mod.PLAN = test_path
        with pytest.raises(ValueError, match="issue count"):
            mod.load_plan()
    finally:
        mod.PLAN = monkey


def test_conflicting_existing_issue_milestone_aborts_before_writes(monkeypatch) -> None:
    mod = _load_module()
    plan = mod.load_plan()
    monkeypatch.setenv("GITHUB_REPOSITORY", mod.REPO)
    operations = []

    def fake_api(token, method, path, payload=None):
        operations.append((method, path))
        if "milestones?" in path:
            return []
        if "/issues/" in path and method == "GET":
            return {"number": int(path.rsplit("/", 1)[-1]), "state": "open",
                    "milestone": {"title": "UNRELATED EXISTING MILESTONE"}}
        raise AssertionError("preflight must not write")

    monkeypatch.setattr(mod, "api", fake_api)
    with pytest.raises(ValueError, match="another milestone"):
        mod.apply(plan, "test-token")
    assert all(method == "GET" for method, _ in operations)


def test_first_apply_and_rerun_are_idempotent(monkeypatch) -> None:
    mod = _load_module()
    plan = mod.load_plan()
    monkeypatch.setenv("GITHUB_REPOSITORY", mod.REPO)
    milestones: dict[str, dict] = {}
    issues: dict[int, dict] = {
        n: {"state": "open", "milestone": None}
        for stage in plan["milestones"] for n in stage["issues"]
    }
    creates: list[str] = []
    patches: list[int] = []

    def fake_api(token, method, path, payload=None):
        if "milestones?" in path:
            return list(milestones.values())
        if path.endswith("/milestones") and method == "POST":
            title = payload["title"]
            created = {"number": len(milestones) + 1, "title": title, "state": "open"}
            milestones[title] = created
            creates.append(title)
            return created
        if "/issues/" in path:
            n = int(path.rsplit("/", 1)[-1])
            if method == "GET":
                return {"number": n, **issues[n]}
            if method == "PATCH":
                issues[n]["milestone"] = next(
                    m for m in milestones.values() if m["number"] == payload["milestone"]
                )
                patches.append(n)
                return issues[n]
        raise AssertionError((method, path))

    monkeypatch.setattr(mod, "api", fake_api)
    mod.apply(plan, "test-token")
    assert len(creates) == 6
    assert len(patches) == 30
    mod.apply(plan, "test-token")
    assert len(creates) == 6
    assert len(patches) == 30
    assert 200 not in patches


def test_closed_issue_is_not_reopened(monkeypatch) -> None:
    mod = _load_module()
    plan = mod.load_plan()
    monkeypatch.setenv("GITHUB_REPOSITORY", mod.REPO)
    excluded = plan["milestones"][0]["issues"][0]
    patches = []

    def fake_api(token, method, path, payload=None):
        if "milestones?" in path:
            return []
        if path.endswith("/milestones") and method == "POST":
            return {
                "number": int(payload["title"][1]) + 1,
                "title": payload["title"],
                "state": "open",
            }
        if "/issues/" in path:
            n = int(path.rsplit("/", 1)[-1])
            if method == "GET":
                return {"number": n, "state": "closed" if n == excluded else "open",
                        "milestone": None}
            if method == "PATCH":
                patches.append(n)
                return {}
        raise AssertionError((method, path))

    monkeypatch.setattr(mod, "api", fake_api)
    mod.apply(plan, "test-token")
    assert excluded not in patches and len(patches) == 29


def test_midflight_milestone_claim_does_not_get_overwritten(monkeypatch) -> None:
    mod = _load_module()
    plan = mod.load_plan()
    monkeypatch.setenv("GITHUB_REPOSITORY", mod.REPO)
    first = plan["milestones"][0]["issues"][0]
    reads: dict[int, int] = {}
    patches: list[int] = []

    def fake_api(token, method, path, payload=None):
        if "milestones?" in path:
            return []
        if path.endswith("/milestones") and method == "POST":
            return {"number": 1, "title": payload["title"], "state": "open"}
        if "/issues/" in path:
            n = int(path.rsplit("/", 1)[-1])
            if method == "GET":
                reads[n] = reads.get(n, 0) + 1
                assignment = (
                    {"number": 99, "title": "Other valid owner"}
                    if n == first and reads[n] > 1
                    else None
                )
                return {"number": n, "state": "open", "milestone": assignment}
            if method == "PATCH":
                patches.append(n)
                return {}
        raise AssertionError((method, path))

    monkeypatch.setattr(mod, "api", fake_api)
    with pytest.raises(ValueError, match="changed since preflight"):
        mod.apply(plan, "test-token")
    assert reads[first] == 2
    assert patches == []


def test_closed_late_stage_milestone_aborts_before_any_write(monkeypatch) -> None:
    mod = _load_module()
    plan = mod.load_plan()
    monkeypatch.setenv("GITHUB_REPOSITORY", mod.REPO)
    operations: list[str] = []

    def fake_api(token, method, path, payload=None):
        operations.append(method)
        if "milestones?" in path:
            return [
                {
                    "title": plan["milestones"][-1]["title"],
                    "state": "closed",
                    "number": 42,
                }
            ]
        raise AssertionError("closed late stage must abort before issue reads or writes")

    monkeypatch.setattr(mod, "api", fake_api)
    with pytest.raises(ValueError, match="existing milestone is closed"):
        mod.apply(plan, "test-token")
    assert operations == ["GET"]


def test_exact_source_blob_gates_one_time_main_push_initialization() -> None:
    root = Path(__file__).resolve().parents[1]
    manifest_raw = (root / ".github/research-milestones.json").read_bytes()
    manifest = json.loads(manifest_raw)
    approved_sha = hashlib.sha1(
        b"blob " + str(len(manifest_raw)).encode("ascii") + b"\0" + manifest_raw,
    ).hexdigest()
    workflow = (
        root / ".github/workflows/research-milestone-initialize-once.yml"
    ).read_text()
    assert approved_sha == "3df25049ab9854e54961c6fb77518236b9ed92ee"
    assert approved_sha in workflow
    assert manifest["status"] == "REQUEST_LIVE_INITIALIZATION_20261019"
    assert "branches:" in workflow and "      - main" in workflow
    assert "git hash-object .github/research-milestones.json" in workflow
    assert "issues: write" in workflow
    assert "workflow_dispatch:" not in workflow
    assert "issue_comment:" in workflow
    assert "github.event_name == 'issue_comment'" in workflow
    assert "github.event.issue.number == 200" in workflow
    assert "github.event.comment.user.login == 'JDeun'" in workflow
    assert (
        "github.event.comment.body == "
        "'SCHEMAROUTER_APPROVE_MILESTONES_20261019'" in workflow
    )
    assert 'github.ref == \'refs/heads/main\'' in workflow


def test_live_assignment_addendum_preserves_initialization_blob_guard() -> None:
    """Live incremental assignments must never repin the initial write gate."""
    milestone_page = (ROOT / ".github/RESEARCH_MILESTONES.md").read_text()
    research_page = (ROOT / "docs/research/research-program-2026.md").read_text()
    for marker in (
        "#1700", "#1711", "M1", "M5", "historical one-time initialization",
    ):
        assert marker in milestone_page
    assert "BLOCKED_SOURCE_SEMANTICS" in research_page
    assert "retrieve_authorized_concept_graph" in research_page
    assert "EVAL-FIXED5-OPTIN" in research_page
    manifest = (ROOT / ".github/research-milestones.json").read_bytes()
    approved_sha = hashlib.sha1(
        b"blob " + str(len(manifest)).encode("ascii") + b"\0" + manifest,
    ).hexdigest()
    assert approved_sha == "3df25049ab9854e54961c6fb77518236b9ed92ee"
    workflow = (ROOT / ".github/workflows/research-milestone-initialize-once.yml").read_text()
    assert approved_sha in workflow

