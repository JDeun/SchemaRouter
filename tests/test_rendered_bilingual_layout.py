"""Regression coverage for EN/KO rendered article layout parity."""

from pathlib import Path

from scripts.check_bilingual_docs import check_rendered, rendered_article_layout


def _page(*, lang: str, article: str) -> str:
    counterpart = "ko" if lang == "en" else "en"
    return (
        "<!doctype html><html><head>"
        f'<link rel="alternate" hreflang="{counterpart}" href="/docs/" />'
        '<script src="/assets/bilingual-switch.js"></script>'
        "</head><body><nav><h2>Navigation</h2></nav>"
        f"<article class='md-content__inner md-typeset'>{article}</article>"
        "</body></html>"
    )


def _site(tmp_path: Path, en_article: str, ko_article: str) -> Path:
    site = tmp_path / "site"
    en = site / "research" / "example" / "index.html"
    ko = site / "ko" / "research" / "example" / "index.html"
    en.parent.mkdir(parents=True)
    ko.parent.mkdir(parents=True)
    en.write_text(_page(lang="en", article=en_article), encoding="utf-8")
    ko.write_text(_page(lang="ko", article=ko_article), encoding="utf-8")
    return site


def test_rendered_article_layout_ignores_navigation() -> None:
    html = _page(
        lang="en",
        article="<h1>Paper</h1><h2>Evidence</h2>"
                "<div class='highlight'><pre><code>print(1)</code></pre></div>"
                "<table><tr><td>1</td></tr></table><img src='diagram.png'>",
    )
    parsed = rendered_article_layout(html)
    assert parsed.articles == 1
    assert parsed.signature() == ((1, 2), 1, 1, 1)


def test_rendered_bilingual_article_parity_passes_translated_text(tmp_path: Path) -> None:
    site = _site(
        tmp_path,
        "<h1>Evidence</h1><h2>Results</h2><pre><code>print(1)</code></pre>"
        "<table><tr><td>FULL</td></tr></table><img src='chart.png'>",
        "<h1>근거</h1><h2>결과</h2><pre><code>print(1)</code></pre>"
        "<table><tr><td>전체</td></tr></table><img src='chart.png'>",
    )
    assert check_rendered(site) == []


def test_rendered_bilingual_article_code_omission_fails(tmp_path: Path) -> None:
    site = _site(
        tmp_path,
        "<h1>Guide</h1><pre><code>python -m tool</code></pre>",
        "<h1>가이드</h1><p>실행 예시가 누락됐습니다.</p>",
    )
    assert any("rendered article layout differs" in msg for msg in check_rendered(site))


def test_rendered_bilingual_heading_corruption_fails(tmp_path: Path) -> None:
    site = _site(
        tmp_path, "<h1>Title</h1><h2>Section</h2>",
        "<h1>제목</h1><h1>본문이 제목으로 렌더링됨</h1>",
    )
    assert any("rendered article layout differs" in msg for msg in check_rendered(site))


def test_rendered_bilingual_missing_article_fails(tmp_path: Path) -> None:
    site = _site(tmp_path, "<h1>Title</h1>", "<h1>제목</h1>")
    file = site / "ko" / "research" / "example" / "index.html"
    file.write_text(
        file.read_text(encoding="utf-8").replace("<article ", "<div ")
        .replace("</article>", "</div>"),
        encoding="utf-8",
    )
    assert any("expected one rendered content article" in msg for msg in check_rendered(site))


def test_reference_api_autodoc_directives_preserve_block_separation() -> None:
    """Both languages must actually expand mkdocstrings, not render ::: as prose."""
    root = Path(__file__).resolve().parents[1]
    for relative in ("api.md", "models.md", "planning.md", "runtime.md"):
        directives: list[list[str]] = []
        for tree in ("docs", "docs_ko"):
            page = (root / tree / "reference" / relative).read_text(encoding="utf-8")
            lines = page.splitlines()
            entries: list[str] = []
            for index, line in enumerate(lines):
                if not line.startswith("::: schemarouter."):
                    continue
                entries.append(line)
                assert index > 0 and not lines[index - 1].strip(), (
                    tree, relative, index + 1, "missing blank line before API directive"
                )
                assert index + 1 == len(lines) or not lines[index + 1].strip(), (
                    tree, relative, index + 1, "missing blank line after API directive"
                )
            assert entries, (tree, relative)
            directives.append(entries)
        assert directives[0] == directives[1], relative
