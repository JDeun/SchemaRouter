"""Regression checks for published bilingual intra-site heading links."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_stable_cross_locale_anchor_definitions() -> None:
    anchors = {
        "docs/getting-started/quickstart.md": "real-provider-capability",
        "docs_ko/getting-started/quickstart.md": "real-provider-capability",
        "docs_ko/guides/mcp.md": "declare-a-result-contract-the-server-does-not-publish",
        "docs_ko/concepts/registry.md": "what-trusted-local-code-may-amend",
        "docs_ko/project/discoverability.md": "release-discoverability-checklist",
    }
    for path, anchor in anchors.items():
        headings = [
            line for line in (ROOT / path).read_text(encoding="utf-8").splitlines()
            if line.startswith("#")
        ]
        assert any(line.endswith("{#" + anchor + "}") for line in headings), path


def test_known_links_target_stable_anchors() -> None:
    references = {
        "docs/getting-started/quickstart.md": "#real-provider-capability",
        "docs_ko/getting-started/quickstart.md": "#real-provider-capability",
        "docs_ko/index.md": "guides/mcp.md#declare-a-result-contract-the-server-does-not-publish",
        "docs_ko/guides/openapi.md": "mcp.md#declare-a-result-contract-the-server-does-not-publish",
        "docs_ko/architecture.md": "concepts/registry.md#what-trusted-local-code-may-amend",
        "docs_ko/release-checklist.md": (
            "project/discoverability.md#release-discoverability-checklist"
        ),
    }
    for path, fragment in references.items():
        assert fragment in (ROOT / path).read_text(encoding="utf-8"), path


def test_anchor_errors_fail_strict_mkdocs_build() -> None:
    config = (ROOT / "mkdocs.yml").read_text(encoding="utf-8")
    assert "  links:\n    anchors: warn\n" in config


def test_korean_checklist_link_is_not_adjacent_to_task_marker() -> None:
    import re

    page = (ROOT / "docs_ko/release-checklist.md").read_text(encoding="utf-8")
    assert not re.search(r"^\s*- \[ \] \[", page, re.MULTILINE)
    assert "project/discoverability.md#release-discoverability-checklist" in page
