"""Keep the pinned native ServiceNow DEV replay tied to ranking code changes."""

from __future__ import annotations

import re
from fnmatch import fnmatchcase
from pathlib import Path

WORKFLOW = (
    Path(__file__).resolve().parents[1]
    / ".github/workflows/servicenow-platform-mcp-development-smoke.yml"
)


def _pull_request_path_filters() -> list[str]:
    """Read the existing GitHub Actions PR path filter without YAML extras."""
    yaml = WORKFLOW.read_text(encoding="utf-8")
    section = yaml.split("  pull_request:\n    paths:\n", 1)[1].split("\n\n", 1)[0]
    return re.findall(r'^\s+-\s+"([^"]+)"\s*$', section, flags=re.MULTILINE)


def test_native_ranker_changes_trigger_pinned_servicenow_dev_replay() -> None:
    patterns = _pull_request_path_filters()
    for changed_path in (
        "src/schemarouter/planner.py",
        "src/schemarouter/adapters/mcp.py",
        "tests/test_declared_tool_name_ranking.py",
    ):
        assert any(fnmatchcase(changed_path, pattern) for pattern in patterns), changed_path


def test_unrelated_docs_do_not_trigger_pinned_servicenow_dev_replay() -> None:
    patterns = _pull_request_path_filters()
    assert not any(fnmatchcase("docs/guide.md", pattern) for pattern in patterns)
