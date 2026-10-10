"""Generated-site link resolution and browser QA harness regressions."""

from pathlib import Path

from scripts.qa_docs_browser import _paths
from scripts.qa_docs_links import inspect, resolve


def test_local_links_and_fragments_are_verified(tmp_path: Path) -> None:
    en = tmp_path / "guides" / "test" / "index.html"
    ko = tmp_path / "ko" / "guides" / "test" / "index.html"
    en.parent.mkdir(parents=True)
    ko.parent.mkdir(parents=True)
    en.write_text(
        '<h1 id="main">Test</h1>'
        '<a href="/SchemaRouter/ko/guides/test/#ko-main">한국어</a>'
        '<a href="#main">same page</a>',
        encoding="utf-8",
    )
    ko.write_text('<h1 id="ko-main">시험</h1>', encoding="utf-8")
    errors, counts = inspect(tmp_path)
    assert errors == []
    assert counts["checked_local"] == 2
    assert counts["checked_anchors"] == 2
    assert _paths(tmp_path) == ["guides/test/", "ko/guides/test/"]


def test_missing_fragment_and_resource_are_detected(tmp_path: Path) -> None:
    doc = tmp_path / "index.html"
    doc.write_text(
        '<a href="/SchemaRouter/ko/missing/#anchor">bad page</a>'
        '<a href="#missing">bad anchor</a>'
        '<img src="missing.png">',
        encoding="utf-8",
    )
    errors, _ = inspect(tmp_path)
    assert len(errors) == 3
    assert any("missing anchor" in error for error in errors)
    assert any("missing img target" in error for error in errors)


def test_remote_links_and_mailto_are_not_probed(tmp_path: Path) -> None:
    doc = tmp_path / "index.html"
    doc.write_text(
        '<a href="https://github.com/JDeun/SchemaRouter">repository</a>'
        '<a href="mailto:hello@example.org">contact</a>',
        encoding="utf-8",
    )
    errors, counts = inspect(tmp_path)
    assert errors == []
    assert counts["external_or_ignored"] == 2
    assert counts["checked_local"] == 0


def test_path_cannot_escape_site_root(tmp_path: Path) -> None:
    doc = tmp_path / "guides" / "index.html"
    doc.parent.mkdir(parents=True)
    doc.write_text('<a href="../../../../outside.txt">leak</a>', encoding="utf-8")
    errors, _ = inspect(tmp_path)
    assert errors and "escapes docs root" in errors[0]
    assert resolve(tmp_path, doc, "https://example.com/help") is None
