import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _version() -> str:
    content = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version = "([^"]+)"$', content, flags=re.MULTILINE)
    assert match is not None
    return match.group(1)


def test_release_version_is_consistent_across_artifacts() -> None:
    version = _version()

    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    installation = (
        ROOT / "docs" / "getting-started" / "installation.md"
    ).read_text(encoding="utf-8")
    release_notes = (
        ROOT / "docs" / "releases" / f"{version}.md"
    ).read_text(encoding="utf-8")
    workflow = (
        ROOT / ".github" / "workflows" / "release.yml"
    ).read_text(encoding="utf-8")

    assert f"## {version} -" in changelog
    assert f"`{version}`" in installation
    assert f"# SchemaRouter {version}" in release_notes
    assert f"SchemaRouter {version}" in workflow
    assert f"schemarouter.__version__ == '{version}'" in workflow


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
    assert "--prerelease" in workflow
