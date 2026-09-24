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
    assert (
        "actions/attest@1e69f48acb82d1966a394da916b4c1698aa569d6"
        in workflow
    )
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
    assert 'verification: ["wheel", "sdist", "integration-extras"]' in workflow
    assert 'package="schemarouter==$RELEASE_VERSION"' in workflow
    assert (
        'package="schemarouter[mcp,langchain,langgraph,llamaindex,jev,otel]==$RELEASE_VERSION"'
        in workflow
    )
    assert "--lightweight-extras" in workflow
    assert "Verify published artifact digest matches release build" in workflow
    assert "actions/download-artifact@3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c" in workflow
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

    extras = "schemarouter[mcp,langchain,langgraph,llamaindex,jev,otel]"
    assert extras in compatibility
    assert extras in release
    assert "--framework-integrations" in compatibility
    assert "--lightweight-extras" in compatibility
    assert "--framework-integrations --lightweight-extras" in release
    assert 'verification: ["wheel", "sdist", "integration-extras"]' in release
    assert "from installed_extras_smoke import run_smoke as run_installed_extras_smoke" in published_smoke
    assert 'report["lightweight_extras"] = args.lightweight_extras' in published_smoke

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
    assert "dependency-audit:" in workflow
    assert "pip-audit --strict ." in workflow
    assert "needs: [laya-integration, dependency-audit]" in workflow
    assert "--html-out /tmp/decision-benchmark.html" in workflow
    assert "schemarouter inspect registry --db /tmp/inspection-registry.sqlite3 --json" in workflow
    assert (
        "schemarouter inspect traces --db /tmp/inspection-traces.sqlite3 "
        "--complete --json"
    ) in workflow
    assert "schemarouter dashboard --registry /tmp/inspection-registry.sqlite3" in workflow
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

    assert "pull_request:" in codeql
    assert "branches: [main]" in codeql
    assert "permissions:\n  contents: read" in codeql
    assert "security-events: write" in codeql
    assert (
        "github/codeql-action/init@1c5b675653bb5c22dbe9b12b556ec555138e09fd"
        in codeql
    )
    assert (
        "github/codeql-action/analyze@1c5b675653bb5c22dbe9b12b556ec555138e09fd"
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
        "ossf/scorecard-action@2d1146689b8cda280b9bc96326124645441f03bc"
        in workflow
    )
    assert "publish_results: true" in workflow
    assert (
        "github/codeql-action/upload-sarif@ff2f1c621b7f889edc0d3c761ac2e6a3f8cdb0dd"
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
