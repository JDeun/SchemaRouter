"""Keep both published MkDocs identities distinct from unrelated named products.

This checks source metadata only; search-engine indexing and rankings must be
measured on the deployed site separately.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _field(content: str, field: str) -> str:
    for line in content.splitlines():
        if line.startswith(f"{field}: "):
            return line.split(": ", 1)[1].strip()
    raise AssertionError(f"Missing {field} metadata")


def test_english_docs_identify_agent_tool_routing_not_generic_router() -> None:
    config = (ROOT / "mkdocs.yml").read_text(encoding="utf-8")
    title = _field(config, "site_name")
    description = _field(config, "site_description")

    assert title == "SchemaRouter for AI Agents"
    assert "schemarouter" in description.casefold()
    assert "python" in description.casefold()
    assert "tool routing" in description.casefold()
    assert "mcp" in description.casefold()
    assert "openapi" in description.casefold()
    assert _field(config, "site_url") == "https://jdeun.github.io/SchemaRouter/"
    assert _field(config, "repo_url") == "https://github.com/JDeun/SchemaRouter"
    assert "link: /SchemaRouter/ko/" in config


def test_korean_docs_identify_agent_tool_routing_with_same_canonical_paths() -> None:
    config = (ROOT / "mkdocs.ko.yml").read_text(encoding="utf-8")
    title = _field(config, "site_name")
    description = _field(config, "site_description")

    assert "SchemaRouter" in title
    assert "AI 에이전트" in title
    assert "도구 라우팅" in title
    assert "MCP" in description and "OpenAPI" in description
    assert "스키마 검증 실행" in description
    assert _field(config, "site_url") == "https://jdeun.github.io/SchemaRouter/ko/"
    assert "INHERIT: mkdocs.yml" in config
    assert "docs_dir: .build/docs-ko" in config
