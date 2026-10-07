from __future__ import annotations

from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = (
    ".github/workflows/ci.yml",
    ".github/workflows/compatibility.yml",
    ".github/workflows/docs.yml",
    ".github/workflows/security.yml",
)


def _setup_python_blocks(text: str) -> tuple[str, ...]:
    lines = text.splitlines()
    blocks: list[str] = []
    for index, line in enumerate(lines):
        if "uses: actions/setup-python@" not in line:
            continue
        indent = len(line) - len(line.lstrip())
        end = index + 1
        while end < len(lines):
            candidate = lines[end]
            if (
                candidate.lstrip().startswith("- ")
                and len(candidate) - len(candidate.lstrip()) == indent
            ):
                break
            end += 1
        blocks.append("\n".join(lines[index:end]))
    return tuple(blocks)


@pytest.mark.parametrize("workflow", WORKFLOWS)
def test_qualification_setup_python_steps_cache_pip_downloads(workflow: str) -> None:
    text = (ROOT / workflow).read_text(encoding="utf-8")
    blocks = _setup_python_blocks(text)

    assert blocks
    for block in blocks:
        assert "cache: pip" in block
        assert "cache-dependency-path: |" in block
        assert "pyproject.toml" in block
        assert workflow in block


def test_main_ci_cache_tracks_external_validation_requirements() -> None:
    text = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    blocks = _setup_python_blocks(text)
    required = (
        "examples/external_validation/pydanticai-tool-search/requirements.txt",
        "examples/external_validation/openai_agents_mcp_filter/requirements.txt",
        "examples/external_validation/mcp_agent_catalog/requirements.txt",
    )

    for block in blocks:
        for dependency in required:
            assert dependency in block
