"""Whole-corpus translation triage output regression tests."""

from pathlib import Path

from scripts.audit_korean_translation_coverage import untranslated_english_prose_lines
from scripts.report_bilingual_coverage import build_report, markdown_summary


def _write(root: Path, rel: str, content: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_report_finds_missing_pages_and_untouched_english_prose(
    tmp_path: Path,
) -> None:
    en = tmp_path / "docs"
    ko = tmp_path / "docs_ko"
    paragraphs = [
        ("An original English explanation detailing reproducibility and "
         "experimental evidence. ") * 5,
        ("A second original English paragraph describes compatibility "
         "and policy semantics. ") * 5,
        ("A third original English paragraph records controlled "
         "measurements and research caveats. ") * 5,
    ]
    source = "# Evidence\n\n" + "\n\n".join(paragraphs)
    _write(en, "research/a.md", source)
    _write(ko, "research/a.md", source.replace("# Evidence", "# 근거"))
    _write(en, "research/missing.md", "# English only\n")

    report = build_report(en, ko)
    summary = report["summary"]
    assert summary["english_pages"] == 2
    assert summary["korean_pages"] == 1
    assert summary["missing_korean_pages"] == ["research/missing.md"]
    assert summary["pages_with_copied_english_paragraphs"] == 1
    assert summary["copied_english_paragraphs"] == 3
    assert "research/a.md" in markdown_summary(report)


def test_report_is_not_confused_by_code_blocks(tmp_path: Path) -> None:
    en = tmp_path / "en"
    ko = tmp_path / "ko"
    fence = chr(96) * 3
    code = fence + "python\nprint('schema')\n" + fence
    _write(en, "index.md", "# Intro\n\n" + code + "\n")
    _write(ko, "index.md", "# 소개\n\n" + code + "\n")

    report = build_report(en, ko)
    page = report["pages"][0]
    assert page["copied_english_paragraphs"] == 0
    assert page["code_fence_languages_match"] is True
    assert page["heading_levels_match"] is True


def test_english_prose_triage_excludes_code_and_korean() -> None:
    source = (
        "# Long English overview explaining routing and provenance\n"
        "This English paragraph describes execution authority and evidence contracts.\n"
        "한국어로 작성한 상세 설명은 추적 대상에서 제외합니다.\n"
        "The `SchemaPlanner`\n"
        "```python\n"
        "This English comment is inside a protected code fence and not prose.\n"
        "```\n"
        "| Column | This is a technical table cell with labels and values |\n"
    )
    assert untranslated_english_prose_lines(source) == [1, 2]


def test_report_includes_advisory_english_prose_lines(tmp_path: Path) -> None:
    en = tmp_path / "docs"
    ko = tmp_path / "docs_ko"
    _write(en, "guide.md", "# Guide\n\nEnglish original with technical caveats.\n")
    _write(
        ko,
        "guide.md",
        "# 안내\n\nThis English paragraph describes execution authority and evidence contracts.\n",
    )
    report = build_report(en, ko)
    summary = report["summary"]
    assert summary["pages_with_english_prose_candidates"] == 1
    assert summary["english_prose_candidate_lines"] == 1
    assert report["pages"][0]["untranslated_english_prose_lines"] == [3]
    assert "English prose lines" in markdown_summary(report)


def test_brand_readme_is_included_in_whole_corpus_report(tmp_path: Path) -> None:
    en = tmp_path / "docs"
    ko = tmp_path / "docs_ko"
    _write(en, "assets/brand/README.md", "# Brand assets\n\nBrand guidelines.\n")
    _write(ko, "assets/brand/README.md", "# 브랜드 에셋\n\n브랜드 지침.\n")
    report = build_report(en, ko)
    assert report["summary"]["english_pages"] == 1
    assert report["summary"]["korean_pages"] == 1
    assert report["summary"]["paired_pages"] == 1
    assert report["pages"][0]["path"] == "assets/brand/README.md"
