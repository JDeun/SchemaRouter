import copy
import json
import re
import textwrap
from pathlib import Path

import pytest

from scripts.qualification_control import load_control

ROOT = Path(__file__).resolve().parents[1]
RELEASE_SHA = "0123456789abcdef0123456789abcdef01234567"
PR_HEAD_SHA = "f" * 40
QUALIFICATION_RUNS = (
    "actions/workflows/post-merge-qualification.yml/runs?head_sha="
    + RELEASE_SHA + "&per_page=1"
)


def _release_gate_source() -> str:
    workflow = (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")
    gate = workflow.split("      - name: Enforce reviewed release qualification\n", 1)[1]
    return textwrap.dedent(gate.split("          python - <<'PY'\n", 1)[1].split(
        "\n          PY", 1,
    )[0])


def _release_approval() -> dict:
    control = copy.deepcopy(load_control())
    control["release"]["decision"] = "APPROVED"
    control["release"]["approval"] = {
        "approval_record_url": "https://github.com/JDeun/SchemaRouter/issues/1345",
        "exact_head_ci_url": "https://github.com/JDeun/SchemaRouter/actions/runs/42",
        "source_sha256": "a" * 64, "artifact_sha256": "b" * 64,
        "approved_by": "synthetic-test-only", "approved_at": "2026-11-03",
        "signed_off_issue_ids": [1345, 1346],
    }
    return control


def _release_github_responses():
    return {
        "pulls/1356": {
            "number": 1356, "merged": True, "merge_commit_sha": RELEASE_SHA,
            "user": {"login": "release-author"},
            "base": {"ref": "main", "repo": {"full_name": "JDeun/SchemaRouter"}},
            "head": {"sha": PR_HEAD_SHA, "repo": {"full_name": "JDeun/SchemaRouter"}},
        },
        "pulls/1356/reviews": [[{
            "user": {"login": "synthetic-test-only", "type": "User"},
            "state": "APPROVED", "commit_id": PR_HEAD_SHA,
        }]],
        "collaborators/synthetic-test-only/permission": {
            "permission": "write", "user": {"login": "synthetic-test-only"},
        },
        QUALIFICATION_RUNS: {"workflow_runs": [{
            "id": 123, "head_sha": RELEASE_SHA, "head_branch": "main",
            "status": "completed", "conclusion": "success",
            "repository": {"full_name": "JDeun/SchemaRouter"},
            "path": ".github/workflows/post-merge-qualification.yml",
        }]},
    }


def _run_release_gate(
    monkeypatch, control, *, version="0.18.0", responses=None, api_error=None,
):
    monkeypatch.setattr("scripts.qualification_control.load_control", lambda: control)
    monkeypatch.setenv("RELEASE_VERSION", version)
    monkeypatch.setenv("RELEASE_SHA", RELEASE_SHA)
    calls = []
    if responses is None:
        responses = _release_github_responses()
        responses["releases/tags/v" + version] = {
            "tag_name": "v" + version, "draft": False,
            "published_at": "2026-10-13T00:00:00Z",
        }

    def github_api(command, **kwargs):
        calls.append(command)
        assert command[:2] == ["gh", "api"]
        path = command[2].removeprefix("repos/JDeun/SchemaRouter/")
        if path.endswith("/reviews"):
            assert command[3:] == ["--paginate", "--slurp"]
        else:
            assert command[3:] == []
        if api_error is not None:
            raise api_error
        return json.dumps(responses[path])

    monkeypatch.setattr("subprocess.check_output", github_api)
    exec(compile(_release_gate_source(), "release qualification gate", "exec"), {})
    return calls


def test_release_qualification_precedes_tag_creation_and_build():
    workflow = (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")
    gate = workflow.index("      - name: Enforce reviewed release qualification")
    assert workflow.index("      - name: Resolve release metadata and target SHA") < gate
    assert gate < workflow.index("      - name: Create annotated tag when missing")
    assert gate < workflow.index("  build:")
    step = workflow[gate:workflow.index("      - name: Create annotated tag when missing")]
    assert "if: steps.metadata.outputs.releasable == 'true'" in step
    assert "RELEASE_SHA: ${{ steps.metadata.outputs.release_sha }}" in step
    assert "GH_TOKEN: ${{ github.token }}" in step


def test_reviewed_release_gate_preserves_separate_model_hold(monkeypatch):
    control = _release_approval()
    assert control["promotion"]["decision"] == "HOLD"
    before = copy.deepcopy(control)
    # The committed receipt refers to earlier CI; the real external review
    # binds the PR head, and merge provenance binds the final qualified SHA.
    assert control["release"]["approval"]["exact_head_ci_url"].endswith("/42")
    assert PR_HEAD_SHA != RELEASE_SHA
    assert len(_run_release_gate(monkeypatch, control)) == 4
    assert control == before


def test_release_gate_fails_closed_when_github_is_unavailable(monkeypatch):
    with pytest.raises(OSError, match="synthetic GitHub outage"):
        _run_release_gate(
            monkeypatch, _release_approval(), api_error=OSError("synthetic GitHub outage"),
        )


@pytest.mark.parametrize("problem", ("hold", "approval", "digest", "owners", "ci_url"))
def test_release_gate_rejects_unapproved_or_malformed_receipt(monkeypatch, problem):
    control = _release_approval()
    gate = control["release"]
    if problem == "hold":
        control = load_control()
    elif problem == "approval":
        del gate["approval"]
    elif problem == "digest":
        gate["approval"]["source_sha256"] = "unverified"
    elif problem == "owners":
        gate["approval"]["signed_off_issue_ids"] = [1345]
    else:
        gate["approval"]["exact_head_ci_url"] = gate["approval"]["approval_record_url"]
    with pytest.raises((ValueError, SystemExit)):
        _run_release_gate(monkeypatch, control)


@pytest.mark.parametrize("field,value", (
    ("head_sha", PR_HEAD_SHA), ("id", 0), ("status", "in_progress"),
    ("head_branch", "release-branch"),
    ("conclusion", "failure"), ("repository", {"full_name": "other/project"}),
    ("path", ".github/workflows/qualification-control.yml"),
))
def test_release_gate_rejects_stale_or_wrong_qualification_run(monkeypatch, field, value):
    responses = _release_github_responses()
    responses[QUALIFICATION_RUNS]["workflow_runs"][0][field] = value
    with pytest.raises((ValueError, SystemExit)):
        _run_release_gate(monkeypatch, _release_approval(), responses=responses)


@pytest.mark.parametrize("problem", (
    "missing", "stale", "changes_requested", "dismissed", "unknown",
    "bot", "other_reviewer", "self_approval", "unmerged", "wrong_merge",
    "wrong_base", "spoofed_base_repo", "spoofed_head_repo", "wrong_pr",
    "no_permission", "spoofed_permission", "missing_qualification",
    "ambiguous_qualification",
))
def test_release_gate_requires_source_bound_current_reviewer_authority(monkeypatch, problem):
    responses = _release_github_responses()
    pull = responses["pulls/1356"]
    review = responses["pulls/1356/reviews"][0][0]
    permission = responses["collaborators/synthetic-test-only/permission"]
    if problem == "missing":
        responses["pulls/1356/reviews"] = [[]]
    elif problem == "stale":
        review["commit_id"] = "a" * 40
    elif problem in ("changes_requested", "dismissed", "unknown"):
        latest = copy.deepcopy(review)
        latest["state"] = {
            "changes_requested": "CHANGES_REQUESTED",
            "dismissed": "DISMISSED", "unknown": "UNKNOWN_API_STATE",
        }[problem]
        responses["pulls/1356/reviews"].append([latest])
    elif problem == "bot":
        review["user"]["type"] = "Bot"
    elif problem == "other_reviewer":
        review["user"]["login"] = "unrelated"
    elif problem == "self_approval":
        pull["user"]["login"] = review["user"]["login"]
    elif problem == "unmerged":
        pull["merged"] = False
    elif problem == "wrong_merge":
        pull["merge_commit_sha"] = "b" * 40
    elif problem == "wrong_base":
        pull["base"]["ref"] = "other-branch"
    elif problem in ("spoofed_base_repo", "spoofed_head_repo"):
        branch = "base" if problem == "spoofed_base_repo" else "head"
        pull[branch]["repo"]["full_name"] = "other/project"
    elif problem == "wrong_pr":
        pull["number"] = 999
    elif problem == "no_permission":
        permission["permission"] = "read"
    elif problem == "spoofed_permission":
        permission["user"]["login"] = "unrelated"
    elif problem == "ambiguous_qualification":
        responses[QUALIFICATION_RUNS]["workflow_runs"].append(
            copy.deepcopy(responses[QUALIFICATION_RUNS]["workflow_runs"][0]),
        )
    else:
        responses[QUALIFICATION_RUNS] = {"workflow_runs": []}
    with pytest.raises((ValueError, SystemExit)):
        _run_release_gate(monkeypatch, _release_approval(), responses=responses)


@pytest.mark.parametrize("permission", ("write", "maintain", "admin"))
def test_release_gate_accepts_current_authority_and_nonrevoking_comments(monkeypatch, permission):
    responses = _release_github_responses()
    responses["collaborators/synthetic-test-only/permission"]["permission"] = permission
    comment = copy.deepcopy(responses["pulls/1356/reviews"][0][0])
    comment["state"] = "COMMENTED"
    responses["pulls/1356/reviews"].append([comment])
    assert len(_run_release_gate(monkeypatch, _release_approval(), responses=responses)) == 4


def test_release_gate_reuses_external_evidence_validator(monkeypatch, tmp_path):
    invalid = tmp_path / "invalid-evidence.json"
    invalid.write_text("{}", encoding="utf-8")
    monkeypatch.setattr("scripts.validate_v018_external_evidence.DEFAULT_PATH", invalid)
    with pytest.raises(ValueError, match="evidence manifest"):
        _run_release_gate(monkeypatch, _release_approval())


@pytest.mark.parametrize("version", ("0.16.0", "0.17.0", "0.17.0rc1"))
def test_release_gate_preserves_historical_version_resumption(monkeypatch, version):
    calls = _run_release_gate(monkeypatch, load_control(), version=version)
    assert calls == [["gh", "api", "repos/JDeun/SchemaRouter/releases/tags/v" + version]]


def test_release_gate_cannot_bypass_hold_with_an_unpublished_legacy_version(monkeypatch):
    with pytest.raises(SystemExit, match="already published"):
        _run_release_gate(
            monkeypatch, load_control(), version="0.16.999",
            responses={"releases/tags/v0.16.999": {}},
        )


def test_development_version_still_skips_before_release_qualification(monkeypatch, tmp_path):
    workflow = (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")
    metadata = workflow.split("      - name: Resolve release metadata and target SHA\n", 1)[1]
    embedded = metadata.split("          python - <<'PY'\n", 1)[1].split("\n          PY", 1)[0]
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pyproject.toml").write_text('[project]\nversion = "0.18.0.dev0"\n')
    output = tmp_path / "outputs"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    monkeypatch.delenv("SKIP_RELEASE", raising=False)
    with pytest.raises(SystemExit) as stopped:
        exec(compile(textwrap.dedent(embedded), "release metadata", "exec"), {})
    assert stopped.value.code == 0
    assert output.read_text() == "releasable=false\n"


@pytest.mark.parametrize("version", ("0.18.0rc1", "0.19.0", "1.0.0"))
def test_release_gate_cannot_bypass_hold_with_an_unreviewed_version(monkeypatch, version):
    with pytest.raises((ValueError, SystemExit)):
        _run_release_gate(monkeypatch, load_control(), version=version)


def _version() -> str:
    content = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version = "([^"]+)"$', content, flags=re.MULTILINE)
    assert match is not None
    return match.group(1)


def test_repository_version_has_valid_development_or_release_state() -> None:
    version = _version()

    if ".dev" in version:
        assert version.endswith(".dev0")
        return

    release_notes = ROOT / "docs" / "releases" / f"{version}.md"
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert release_notes.is_file()
    assert f"## {version} -" in changelog


def test_release_workflow_derives_metadata_from_pyproject() -> None:
    workflow = (
        ROOT / ".github" / "workflows" / "release.yml"
    ).read_text(encoding="utf-8")

    assert 'tomllib.loads(Path("pyproject.toml").read_text())["project"]["version"]' in workflow
    assert 'tag = f"v{version}"' in workflow
    assert 'Path("docs") / "releases" / f"{version}.md"' in workflow
    assert 'f"## {version} -"' in workflow
    assert 'if ".dev" in version:' in workflow
    assert '--title "SchemaRouter $RELEASE_VERSION"' in workflow
    assert '--notes-file "$RELEASE_NOTES"' in workflow

    # A future release must not require editing old version literals in the workflow.
    assert "0.2.0a1" not in workflow
    assert "0.3.0.dev0" not in workflow


def test_release_workflow_consumes_green_post_merge_qualification_and_can_create_tag() -> None:
    workflow = (
        ROOT / ".github" / "workflows" / "release.yml"
    ).read_text(encoding="utf-8")

    assert "workflow_run:" in workflow
    assert 'workflows: ["Post-merge Qualification"]' in workflow
    assert "github.event.workflow_run.conclusion == 'success'" in workflow
    assert "github.event.workflow_run.head_branch == 'main'" in workflow
    assert 'git rev-parse origin/main' in workflow
    assert "git fetch origin main --tags" in workflow
    assert "git fetch origin main --depth=1" not in workflow
    assert 'git ls-remote --exit-code --tags origin "refs/tags/$RELEASE_TAG"' in workflow
    assert 'git tag -a "$RELEASE_TAG" "$RELEASE_SHA"' in workflow
    assert 'git push origin "refs/tags/$RELEASE_TAG"' in workflow
    assert "pull_request_target" not in workflow


def test_release_workflow_keeps_trusted_publishing_top_level_and_isolates_build() -> None:
    workflow = (
        ROOT / ".github" / "workflows" / "release.yml"
    ).read_text(encoding="utf-8")

    assert "id-token: write" in workflow
    assert "attestations: write" in workflow
    assert "artifact-metadata: write" in workflow
    assert (
        "actions/attest@1e69f48acb82d1966a394da916b4c1698aa569d6"
        in workflow
    )
    assert "subject-path: dist/*" in workflow
    assert (
        "anchore/sbom-action@66cbf4bc1f1c0d2edc94016e65bc221b6bb0ad6c"
        in workflow
    )
    assert "format: spdx-json" in workflow
    assert "upload-artifact: false" in workflow
    assert "upload-release-assets: false" in workflow
    assert "dependency-snapshot: false" in workflow
    assert "sbom-path: artifacts/schemarouter-" in workflow
    assert "name: release-sbom" in workflow
    assert "path: sbom" in workflow
    assert "name: release-metadata" in workflow
    assert "artifacts/SHA256SUMS.txt" in workflow
    assert "artifacts/release-manifest.json" in workflow
    assert '"source_sha": os.environ["RELEASE_SHA"]' in workflow
    assert "metadata/*" in workflow
    assert 'gh release create "$RELEASE_TAG" dist/* sbom/*' in workflow
    assert "environment:" in workflow
    assert "name: pypi" in workflow
    assert (
        "pypa/gh-action-pypi-publish@dc37677b2e1c63e2034f94d8a5b11f265b73ba33"
        in workflow
    )
    assert "skip-existing: true" in workflow
    assert 'gh release create "$RELEASE_TAG"' in workflow
    assert "name: Checkout current main" in workflow
    assert "name: Checkout pushed tag" in workflow
    assert "ref: main" in workflow
    assert "name: release-notes" in workflow
    assert "path: release-notes" in workflow
    assert "GH_REPO: ${{ github.repository }}" in workflow
    assert 'glob.glob("dist/*.tar.gz")[0]' in workflow
    assert 'subprocess.check_call([str(python), "examples/quickstart.py"])' in workflow
    assert "post-publish:" in workflow
    assert "needs: [prepare, github-release, pypi]" in workflow
    assert (
        'verification: ["wheel", "sdist", "lightweight-extras", "integration-extras"]'
        in workflow
    )
    assert 'package="schemarouter==$RELEASE_VERSION"' in workflow
    assert 'package="schemarouter[mcp,jev,otel]==$RELEASE_VERSION"' in workflow
    assert (
        'package="schemarouter[mcp,langchain,langgraph,llamaindex,jev,otel,database]==$RELEASE_VERSION"'
        in workflow
    )
    assert "--lightweight-extras" in workflow
    assert "Verify published artifact digest matches release build" in workflow
    assert "actions/download-artifact@9000827ccba6bdab643e8b6fd33ac0654aef8333" in workflow
    assert "--index-url https://pypi.org/simple" in workflow
    assert (
        'python -m pip download "${download_args[@]}" '
        '"schemarouter==$RELEASE_VERSION"'
    ) in workflow
    assert "python scripts/verify_artifact_digest.py" in workflow
    assert "--published-dir /tmp/pypi-artifact" in workflow
    assert '--expected-version "$RELEASE_VERSION"' in workflow
    assert "for attempt in {1..18}; do" in workflow
    assert "python -m pip check" in workflow
    assert "uses: ./.github/workflows/ci.yml" not in workflow



def test_external_package_smokes_cover_lightweight_integration_extras() -> None:
    compatibility = (
        ROOT / ".github" / "workflows" / "compatibility.yml"
    ).read_text(encoding="utf-8")
    release = (
        ROOT / ".github" / "workflows" / "release.yml"
    ).read_text(encoding="utf-8")
    published_smoke = (
        ROOT / "scripts" / "published_pypi_smoke.py"
    ).read_text(encoding="utf-8")

    lightweight_extras = "schemarouter[mcp,jev,otel]"
    compatibility_combined_extras = "schemarouter[mcp,langchain,langgraph,llamaindex,jev,otel]"
    release_combined_extras = (
        "schemarouter[mcp,langchain,langgraph,llamaindex,jev,otel,database]"
    )
    assert "published-pypi-lightweight:" in compatibility
    assert lightweight_extras in compatibility
    assert lightweight_extras in release
    assert compatibility_combined_extras in compatibility
    assert release_combined_extras in release
    assert "--framework-integrations" in compatibility
    assert "--lightweight-extras" in compatibility
    assert "--framework-integrations --lightweight-extras" in release
    assert "--database-integration" in release
    assert (
        'verification: ["wheel", "sdist", "lightweight-extras", "integration-extras"]'
        in release
    )
    assert (
        "from installed_extras_smoke import run_smoke as run_installed_extras_smoke"
        in published_smoke
    )
    assert 'report["lightweight_extras"] = args.lightweight_extras' in published_smoke
    assert 'report["database_integration"] = args.database_integration' in published_smoke
    assert "from installed_database_smoke import run_smoke as run_database_smoke" in published_smoke


def test_ci_is_reusable_and_contains_release_quality_gates() -> None:
    workflow = (
        ROOT / ".github" / "workflows" / "ci.yml"
    ).read_text(encoding="utf-8")

    assert "workflow_call:" in workflow
    assert '"3.14"' in workflow
    assert "windows-smoke:" in workflow
    assert "minimum-dependencies:" in workflow
    assert "coverage:" in workflow
    assert "coverage-native:" in workflow
    assert "Upload Python 3.12 core coverage data" in workflow
    assert "needs: [test, coverage-native]" in workflow
    assert "Verify coverage fan-out" in workflow
    assert "coverage combine coverage-data" in workflow
    assert "coverage report --fail-under=83.5" in workflow
    assert "--cov-branch" in workflow
    assert "dependency-audit:" in workflow
    assert "pip-audit --strict ." in workflow
    assert "package-core:" in workflow
    assert "Publish immutable package artifacts" in workflow
    assert "package-dist-${{ github.run_id }}" in workflow
    assert "package-runtime-smoke:" in workflow
    assert "package-sdist:" in workflow
    assert "Verify package qualification fan-out" in workflow
    assert "- laya-integration" in workflow
    assert "- dependency-audit" in workflow
    assert "- database-integration" in workflow
    assert "database-integration:" in workflow
    assert 'pip install -e ".[dev,database]"' in workflow
    assert "--html-out /tmp/decision-benchmark.html" in workflow
    assert "schemarouter inspect registry --db /tmp/inspection-registry.sqlite3 --json" in workflow
    assert (
        "schemarouter inspect traces --db /tmp/inspection-traces.sqlite3 "
        "--complete --json"
    ) in workflow
    assert "schemarouter dashboard --registry /tmp/inspection-registry.sqlite3" in workflow
    assert 'dist/*.tar.gz' in workflow
    assert "schemarouter[mcp,jev,otel] @ file://" in workflow


def test_pr_ci_uses_path_aware_tiers_without_renaming_required_gates() -> None:
    workflow = (
        ROOT / ".github" / "workflows" / "ci.yml"
    ).read_text(encoding="utf-8")

    assert "changes:" in workflow
    assert "Classify changed paths" in workflow
    assert "max-parallel: 2" in workflow
    assert "fail-fast: true" in workflow
    assert "needs.changes.outputs.native == 'true'" in workflow
    assert "needs.changes.outputs.deps == 'true'" in workflow
    assert "needs.changes.outputs.package == 'true'" in workflow
    assert "needs.changes.outputs.langchain == 'true'" in workflow
    assert "needs.changes.outputs.llamaindex == 'true'" in workflow
    assert "needs.changes.outputs.mcp == 'true'" in workflow
    assert "needs.changes.outputs.database == 'true'" in workflow
    assert "needs.changes.outputs.docs == 'true'" in workflow
    assert '"success", "skipped"' in workflow
    assert 'python-version: ["3.10", "3.12", "3.14"]' in workflow
    assert "name: test (3.11)" in workflow
    assert "name: test (3.13)" in workflow
    assert "if: ${{ false }}" not in workflow
    assert "Python 3.11 full qualification runs in python-compatibility.yml" in workflow
    assert "Python 3.13 full qualification runs in python-compatibility.yml" in workflow
    assert "Skip minimum-dependencies qualification when unaffected" in workflow
    assert "Skip LangChain qualification when unaffected" in workflow
    assert "Skip LlamaIndex qualification when unaffected" in workflow
    assert "Skip MCP qualification when unaffected" in workflow
    assert "Skip docs qualification when unaffected" in workflow


def test_scheduled_python_compatibility_covers_all_supported_versions() -> None:
    workflow = (
        ROOT / ".github" / "workflows" / "python-compatibility.yml"
    ).read_text(encoding="utf-8")

    assert 'python-version: ["3.10", "3.11", "3.12", "3.13", "3.14"]' in workflow
    assert "Run full supported-version suite" in workflow
    assert "schedule:" in workflow
    assert "workflow_dispatch:" in workflow


def test_scheduled_full_qualification_reuses_the_complete_ci() -> None:
    workflow = (
        ROOT / ".github" / "workflows" / "full-qualification.yml"
    ).read_text(encoding="utf-8")

    assert "schedule:" in workflow
    assert "workflow_dispatch:" in workflow
    assert "uses: ./.github/workflows/ci.yml" in workflow
    assert "cancel-in-progress: true" in workflow


def test_pr_ci_and_post_merge_qualification_are_separated() -> None:
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    post_merge = (
        ROOT / ".github" / "workflows" / "post-merge-qualification.yml"
    ).read_text(encoding="utf-8")

    assert "workflow_call:" in ci
    assert "pull_request:" in ci
    assert "  push:\n    branches: [main]" not in ci

    assert "push:\n    branches: [main]" in post_merge
    assert 'python-version: "3.12"' in post_merge
    assert "pytest -q" in post_merge
    assert "--cov-fail-under=83.5" in post_merge
    assert "pyright" in post_merge
    assert "python -m build" in post_merge
    assert "twine check dist/*" in post_merge
    assert "QUALIFIED_SHA" in post_merge
    assert "post-merge-qualification-${{ github.sha }}" in post_merge
    assert "cancel-in-progress: true" not in post_merge


def test_python_preview_is_separate_from_release_blocking_ci() -> None:
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    preview = (
        ROOT / ".github" / "workflows" / "python-preview.yml"
    ).read_text(encoding="utf-8")

    assert "python-preview:" not in ci
    assert '"3.15.0-rc.2"' in preview
    assert "allow-prereleases: true" in preview
    assert "timeout-minutes: 20" in preview
    assert "pull_request:" not in preview
    assert "schedule:" in preview
    assert "  push:" not in preview
    assert "workflow_dispatch:" in preview
    assert "workflow_call:" not in preview

    release = (
        ROOT / ".github" / "workflows" / "release.yml"
    ).read_text(encoding="utf-8")
    assert 'workflows: ["Post-merge Qualification"]' in release
    assert 'workflows: ["Python Preview"]' not in release



def test_security_workflows_cover_dependency_and_code_scanning() -> None:
    security = (
        ROOT / ".github" / "workflows" / "security.yml"
    ).read_text(encoding="utf-8")
    codeql = (
        ROOT / ".github" / "workflows" / "codeql.yml"
    ).read_text(encoding="utf-8")

    assert "pull_request:" not in security
    assert "schedule:" in security
    assert '"pyproject.toml"' in security
    assert "pull_request:" in codeql
    assert "  push:" not in codeql
    assert "pip-audit --strict" in security
    assert "python -m pip check" in security

    assert "pull_request:" in codeql
    assert "branches: [main]" in codeql
    assert "permissions:\n  contents: read" in codeql
    assert "security-events: write" in codeql
    assert (
        "github/codeql-action/init@6f2ac81f5cd81fe351a197ba0b00d91d03cd2aee"
        in codeql
    )
    assert (
        "github/codeql-action/analyze@6f2ac81f5cd81fe351a197ba0b00d91d03cd2aee"
        in codeql
    )
    assert "languages: python" in codeql



def test_openssf_scorecard_workflow_is_pinned_and_least_privilege() -> None:
    workflow = (
        ROOT / ".github" / "workflows" / "scorecard.yml"
    ).read_text(encoding="utf-8")

    assert "permissions: read-all" in workflow
    assert "security-events: write" in workflow
    assert "id-token: write" in workflow
    assert "persist-credentials: false" in workflow
    assert (
        "ossf/scorecard-action@fa7117db83c52d787ae5a89f350999701505d78e"
        in workflow
    )
    assert "publish_results: true" in workflow
    assert (
        "github/codeql-action/upload-sarif@6f2ac81f5cd81fe351a197ba0b00d91d03cd2aee"
        in workflow
    )



def test_all_external_workflow_actions_are_pinned_to_commit_shas() -> None:
    workflow_dir = ROOT / ".github" / "workflows"
    uses_pattern = re.compile(r"^\s*uses:\s*([^#\s]+)", flags=re.MULTILINE)
    pinned_pattern = re.compile(r"^[^@\s]+@[0-9a-f]{40}$")

    unpinned: list[str] = []
    for path in sorted(workflow_dir.glob("*.yml")):
        workflow = path.read_text(encoding="utf-8")
        for reference in uses_pattern.findall(workflow):
            if reference.startswith("./"):
                continue
            if not pinned_pattern.fullmatch(reference):
                unpinned.append(f"{path.name}: {reference}")

    assert unpinned == []



def test_docs_workflow_uses_read_only_default_permissions() -> None:
    workflow = (
        ROOT / ".github" / "workflows" / "docs.yml"
    ).read_text(encoding="utf-8")

    assert "permissions:\n  contents: read" in workflow
    assert '"docs/**"' in workflow
    assert '"docs_ko/**"' in workflow
    build_section = workflow.split("  deploy:", 1)[0]
    assert "pages: write" not in build_section
    deploy_section = workflow.split("  deploy:", 1)[1]
    assert "pages: write" in deploy_section
    assert "id-token: write" in deploy_section



def test_docs_changelog_reuses_the_canonical_root_changelog() -> None:
    docs_changelog = (ROOT / "docs" / "changelog.md").read_text(encoding="utf-8")

    assert '--8<-- "CHANGELOG.md:8:"' in docs_changelog
    assert "## Unreleased" not in docs_changelog



def test_docs_contributing_reuses_the_canonical_root_guide() -> None:
    docs_contributing = (ROOT / "docs" / "contributing.md").read_text(encoding="utf-8")
    root_contributing = (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")

    assert docs_contributing.strip() == '--8<-- "CONTRIBUTING.md"'
    assert "82% branch-coverage" not in root_contributing
    assert "84% branch-coverage" in root_contributing
