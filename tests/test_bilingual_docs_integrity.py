"""Regression tests for fail-closed bilingual documentation checks."""

from pathlib import Path

from scripts import audit_korean_translation_coverage as checker


def _write(root: Path, name: str, content: str) -> None:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_severe_truncation_is_reported(tmp_path: Path, monkeypatch) -> None:
    en = tmp_path / "docs"
    ko = tmp_path / "docs_ko"
    _write(en, "guides/long.md", "# Full guide\n\n" + ("Meaningful source paragraph. " * 140))
    _write(ko, "guides/long.md", "# 전체 안내서\n\n요약만 있습니다.\n")
    monkeypatch.setattr(checker, "EN", en)
    monkeypatch.setattr(checker, "KO", ko)
    assert any("severe Korean truncation" in e for e in checker.check_sources())


def test_complete_short_translation_is_not_truncation(tmp_path: Path, monkeypatch) -> None:
    en = tmp_path / "docs"
    ko = tmp_path / "docs_ko"
    _write(en, "guide.md", "# Guide\n\nInstall and run.")
    _write(ko, "guide.md", "# 안내\n\n설치하고 실행합니다.")
    monkeypatch.setattr(checker, "EN", en)
    monkeypatch.setattr(checker, "KO", ko)
    assert checker.check_sources() == []


def test_skeletal_section_is_detected_even_when_headings_match(
    tmp_path: Path, monkeypatch
) -> None:
    en = tmp_path / "docs"
    ko = tmp_path / "docs_ko"
    _write(en, "research.md", "# Report\n\n" + ("Detailed evidence and provenance. " * 80))
    _write(ko, "research.md", "# 보고서\n\n간단한 요약.\n")
    monkeypatch.setattr(checker, "EN", en)
    monkeypatch.setattr(checker, "KO", ko)
    errors = checker.check_sources()
    assert any("section 1 appears skeletal" in error for error in errors)


def test_code_fences_do_not_count_as_translated_prose() -> None:
    text = "# Example\n\nA real explanation.\n\n```python\nprint(123)\n```\n"
    assert checker.section_prose_lengths(text) == [len("A real explanation.")]


def test_prose_risk_check_has_conservative_lower_bound() -> None:
    short_source = "# Title\n\n" + ("Example. " * 35)
    assert checker.section_prose_lengths(short_source)[0] < 650


def test_verbatim_english_prose_padding_fails_closed(tmp_path: Path, monkeypatch) -> None:
    en = tmp_path / "docs"
    ko = tmp_path / "docs_ko"
    paragraphs = [
        ("A genuine English research paragraph with detailed experimental "
         "methods and reproducibility constraints. ") * 5,
        ("A second comprehensive English explanation reports measurements "
         "and held-out evaluation conditions. ") * 5,
        ("A third substantial English rationale describes model limitations "
         "and security boundaries. ") * 5,
    ]
    _write(en, "research.md", "# Research\n\n" + "\n\n".join(paragraphs))
    _write(ko, "research.md", "# 연구\n\n" + "\n\n".join(paragraphs))
    monkeypatch.setattr(checker, "EN", en)
    monkeypatch.setattr(checker, "KO", ko)
    errors = checker.check_sources()
    assert any("substantial English source paragraphs" in e for e in errors)


def test_code_blocks_are_not_flagged_as_untranslated_prose() -> None:
    long_code = "script output is not translated explanatory prose. " * 15
    en = "# Example\n\n```text\n" + long_code + "\n```\n"
    ko = "# 예시\n\n```text\n" + long_code + "\n```\n"
    assert checker.unchanged_english_prose(en, ko) == []
