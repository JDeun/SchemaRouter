import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


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
    assert 'expected = f"v{version}"' in workflow
    assert 'Path("docs") / "releases" / f"{version}.md"' in workflow
    assert "development versions cannot be published" in workflow
    assert 'RELEASE_VERSION: ${{ needs.build.outputs.version }}' in workflow
    assert '--title "SchemaRouter $RELEASE_VERSION"' in workflow
    assert '--notes-file "$RELEASE_NOTES"' in workflow

    # A future release must not require editing old version literals in the workflow.
    assert "0.2.0a1" not in workflow
    assert "0.3.0.dev0" not in workflow


def test_release_workflow_uses_tag_gate_and_trusted_publishing() -> None:
    workflow = (
        ROOT / ".github" / "workflows" / "release.yml"
    ).read_text(encoding="utf-8")

    assert "tags:" in workflow
    assert '- "v*"' in workflow
    assert "id-token: write" in workflow
    assert "environment:" in workflow
    assert "name: pypi" in workflow
    assert "pypa/gh-action-pypi-publish@release/v1" in workflow
    assert 'gh release create "$GITHUB_REF_NAME"' in workflow
    assert "prerelease_args" in workflow
    assert "quality:" in workflow
    assert "uses: ./.github/workflows/ci.yml" in workflow
    assert "needs: quality" in workflow
    assert 'glob.glob("dist/*.tar.gz")[0]' in workflow
    assert 'subprocess.check_call([str(python), "examples/quickstart.py"])' in workflow



def test_ci_is_reusable_and_contains_release_quality_gates() -> None:
    workflow = (
        ROOT / ".github" / "workflows" / "ci.yml"
    ).read_text(encoding="utf-8")

    assert "workflow_call:" in workflow
    assert '"3.14"' in workflow
    assert '"3.15.0-rc.2"' in workflow
    assert "windows-smoke:" in workflow
    assert "minimum-dependencies:" in workflow
    assert "coverage:" in workflow
    assert "--cov-branch" in workflow
    assert 'dist/*.tar.gz' in workflow



def test_auto_tag_release_waits_for_green_main_ci_and_is_idempotent() -> None:
    workflow = (
        ROOT / ".github" / "workflows" / "auto-tag-release.yml"
    ).read_text(encoding="utf-8")

    assert "workflow_run:" in workflow
    assert 'workflows: ["CI"]' in workflow
    assert "github.event.workflow_run.conclusion == 'success'" in workflow
    assert "github.event.workflow_run.head_branch == 'main'" in workflow
    assert "permissions:" in workflow
    assert "contents: write" in workflow
    assert "pull_request_target" not in workflow
    assert "workflow_dispatch" not in workflow

    assert 'ref: ${{ github.event.workflow_run.head_sha }}' in workflow
    assert 'git rev-parse origin/main' in workflow
    assert 'SKIP_RELEASE_TAG=true' in workflow

    assert 'if ".dev" in version:' in workflow
    assert 'Path("docs") / "releases" / f"{version}.md"' in workflow
    assert 'f"## {version} -"' in workflow
    assert 'tag=v{version}' in workflow

    assert 'git ls-remote --exit-code --tags origin "refs/tags/$RELEASE_TAG"' in workflow
    assert 'git tag -a "$RELEASE_TAG" "$RELEASE_SHA"' in workflow
    assert 'git push origin "refs/tags/$RELEASE_TAG"' in workflow


def test_auto_tag_release_does_not_execute_repository_code() -> None:
    workflow = (
        ROOT / ".github" / "workflows" / "auto-tag-release.yml"
    ).read_text(encoding="utf-8")

    forbidden = [
        "pip install",
        "pytest",
        "python -m",
        "bash scripts/",
        "sh scripts/",
        "./scripts/",
    ]
    assert all(command not in workflow for command in forbidden)
