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
    assert 'tag = f"v{version}"' in workflow
    assert 'Path("docs") / "releases" / f"{version}.md"' in workflow
    assert 'f"## {version} -"' in workflow
    assert 'if ".dev" in version:' in workflow
    assert '--title "SchemaRouter $RELEASE_VERSION"' in workflow
    assert '--notes-file "$RELEASE_NOTES"' in workflow

    # A future release must not require editing old version literals in the workflow.
    assert "0.2.0a1" not in workflow
    assert "0.3.0.dev0" not in workflow


def test_release_workflow_consumes_green_main_ci_and_can_create_tag() -> None:
    workflow = (
        ROOT / ".github" / "workflows" / "release.yml"
    ).read_text(encoding="utf-8")

    assert "workflow_run:" in workflow
    assert 'workflows: ["CI"]' in workflow
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
    assert "actions/attest@v4" in workflow
    assert "subject-path: dist/*" in workflow
    assert (
        "anchore/sbom-action@3ad7283483fc7af8ff2b4ea19663c2d5ca935e26"
        in workflow
    )
    assert "format: spdx-json" in workflow
    assert "upload-artifact: false" in workflow
    assert "upload-release-assets: false" in workflow
    assert "dependency-snapshot: false" in workflow
    assert "sbom-path: artifacts/schemarouter-" in workflow
    assert "name: release-sbom" in workflow
    assert "path: sbom" in workflow
    assert 'gh release create "$RELEASE_TAG" dist/* sbom/*' in workflow
    assert "environment:" in workflow
    assert "name: pypi" in workflow
    assert "pypa/gh-action-pypi-publish@release/v1" in workflow
    assert "skip-existing: true" in workflow
    assert 'gh release create "$RELEASE_TAG"' in workflow
    assert 'ref: ${{ needs.prepare.outputs.release_sha }}' in workflow
    assert 'glob.glob("dist/*.tar.gz")[0]' in workflow
    assert 'subprocess.check_call([str(python), "examples/quickstart.py"])' in workflow
    assert "uses: ./.github/workflows/ci.yml" not in workflow



def test_ci_is_reusable_and_contains_release_quality_gates() -> None:
    workflow = (
        ROOT / ".github" / "workflows" / "ci.yml"
    ).read_text(encoding="utf-8")

    assert "workflow_call:" in workflow
    assert '"3.14"' in workflow
    assert "windows-smoke:" in workflow
    assert "minimum-dependencies:" in workflow
    assert "coverage:" in workflow
    assert "--cov-branch" in workflow
    assert "needs: [laya-integration]" in workflow
    assert "--html-out /tmp/decision-benchmark.html" in workflow
    assert 'dist/*.tar.gz' in workflow


def test_python_preview_is_separate_from_release_blocking_ci() -> None:
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    preview = (
        ROOT / ".github" / "workflows" / "python-preview.yml"
    ).read_text(encoding="utf-8")

    assert "python-preview:" not in ci
    assert '"3.15.0-rc.2"' in preview
    assert "allow-prereleases: true" in preview
    assert "timeout-minutes: 20" in preview
    assert "pull_request:" in preview
    assert "branches: [main]" in preview
    assert "workflow_call:" not in preview

    release = (
        ROOT / ".github" / "workflows" / "release.yml"
    ).read_text(encoding="utf-8")
    assert 'workflows: ["CI"]' in release
    assert 'workflows: ["Python Preview"]' not in release



def test_security_workflows_cover_dependency_and_code_scanning() -> None:
    security = (
        ROOT / ".github" / "workflows" / "security.yml"
    ).read_text(encoding="utf-8")
    codeql = (
        ROOT / ".github" / "workflows" / "codeql.yml"
    ).read_text(encoding="utf-8")

    assert "pull_request:" in security
    assert "schedule:" in security
    assert "pip-audit --strict" in security
    assert "python -m pip check" in security

    assert "security-events: write" in codeql
    assert "github/codeql-action/init@v4" in codeql
    assert "github/codeql-action/analyze@v4" in codeql
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
        "ossf/scorecard-action@2d1146689b8cda280b9bc96326124645441f03bc"
        in workflow
    )
    assert "publish_results: true" in workflow
    assert (
        "github/codeql-action/upload-sarif@ff2f1c621b7f889edc0d3c761ac2e6a3f8cdb0dd"
        in workflow
    )
