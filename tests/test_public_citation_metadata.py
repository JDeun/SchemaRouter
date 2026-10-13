"""Protect public source-attribution metadata against release and locale drift.

These tests are offline: no crawler, external model or hosted API is contacted.
They do not assert SEO ranking, AI citation uptake, or #432/#424 outcomes.
"""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlparse

import yaml

ROOT = Path(__file__).resolve().parents[1]
DOCS_ORIGIN = "https://jdeun.github.io"
SITE_PREFIX = "/SchemaRouter/"
DOCUMENT_LINK = re.compile(r"\[[^\]]+\]\((https://jdeun\.github\.io/SchemaRouter/[^\s)]+)\)")


def _project_version() -> str:
    project = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    project_section = project.split("[project]", 1)[1].split("\n[", 1)[0]
    match = re.search(r'^version\s*=\s*"([^"]+)"\s*$', project_section, re.MULTILINE)
    assert match is not None, "Missing [project] version in pyproject.toml"
    return match.group(1)


def test_software_citation_is_valid_yaml_and_matches_package() -> None:
    citation = yaml.safe_load((ROOT / "CITATION.cff").read_text(encoding="utf-8"))

    assert citation["cff-version"] == "1.2.0"
    assert citation["type"] == "software"
    assert citation["title"] == "SchemaRouter"
    assert citation["version"] == _project_version()
    assert citation["license"] == "MIT"
    assert citation["repository-code"] == "https://github.com/JDeun/SchemaRouter"
    assert citation["url"] == "https://jdeun.github.io/SchemaRouter/"
    assert citation["authors"] == [{"family-names": "Cho", "given-names": "Yong-eun"}]
    assert "doi" not in citation, "Do not invent a software DOI"
    assert "date-released" not in citation, "Release dates must be source-verified"


def test_english_and_korean_ai_navigation_link_real_primary_sources() -> None:
    for language, base in (("en", ROOT / "docs"), ("ko", ROOT / "docs_ko")):
        text = (base / "llms.txt").read_text(encoding="utf-8")
        article_urls = DOCUMENT_LINK.findall(text)

        assert len(article_urls) >= 10, f"{language}: too few primary documentation links"
        assert len(article_urls) == len(set(article_urls)), f"{language}: duplicate link"
        assert "#432" in text and "#424" in text, f"{language}: pending science omitted"
        assert "CITATION.cff" in text, f"{language}: software attribution omitted"

        for url in article_urls:
            parsed = urlparse(url)
            assert parsed.scheme == "https"
            assert parsed.netloc == "jdeun.github.io"
            assert parsed.path.startswith(SITE_PREFIX)
            assert not parsed.query and not parsed.fragment

            relative = parsed.path.removeprefix(SITE_PREFIX)
            if language == "ko":
                assert relative.startswith("ko/"), f"Korean AI index links to English: {url}"
                relative = relative.removeprefix("ko/")
            else:
                assert not relative.startswith("ko/"), f"English AI index links to Korean: {url}"

            assert relative.endswith("/"), f"Expected canonical directory URL: {url}"
            source = base / f"{relative.rstrip('/')}.md"
            assert source.is_file(), f"Missing source for published URL {url}: {source}"


def test_ai_indexes_do_not_present_pending_014_studies_as_terminal() -> None:
    english = (ROOT / "docs/llms.txt").read_text(encoding="utf-8")
    korean = (ROOT / "docs_ko/llms.txt").read_text(encoding="utf-8")

    assert "pending canonical terminal evidence" in english
    assert "아직 공개되지 않았습니다" in korean
    assert "0.14" in english and "0.14" in korean
