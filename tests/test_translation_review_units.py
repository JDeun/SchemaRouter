from pathlib import Path

import pytest

from scripts.audit_translation_review_units import audit, review_units


def test_inventory_covers_headings_lists_tables_prose_but_excludes_code() -> None:
    sample = (
        "# Title\n\nDo not mutate.\n\n- Only approved calls\n"
        "- Never untrusted calls\n\n| A | B |\n| --- | --- |\n"
        "\n```python\n# Not a heading\nprint('never')\n```\n"
    )
    units = review_units(sample)
    assert [u["kind"] for u in units] == [
        "heading", "paragraph", "list", "list", "table", "table"
    ]
    assert [u["index"] for u in units] == list(range(1, 7))
    assert all("print" not in str(u["text"]) for u in units)


def test_unclosed_fence_is_not_silently_ignored() -> None:
    with pytest.raises(ValueError, match="unclosed"):
        review_units("# Title\n\n```python\nnot text")


def test_paragraph_loss_is_not_masked_by_other_negation(tmp_path: Path) -> None:
    en, ko = tmp_path / "en", tmp_path / "ko"
    en.mkdir()
    ko.mkdir()
    (en / "a.md").write_text(
        "# Safety\n\nNever grant permissions.\n\nDo not execute mutations.\n",
        encoding="utf-8",
    )
    (ko / "a.md").write_text(
        "# 안전\n\n권한을 부여하지 않습니다.\n\n변경 작업을 실행합니다.\n",
        encoding="utf-8",
    )
    report = audit(en, ko)
    assert report["paired_pages"] == 1
    assert report["independent_sentence_review_complete"] is False
    assert len(report["advisory_prohibition_risks"]) == 1
    assert report["advisory_prohibition_risks"][0]["en_line"] == 5


def test_different_block_counts_are_not_fake_aligned(tmp_path: Path) -> None:
    en, ko = tmp_path / "en", tmp_path / "ko"
    en.mkdir()
    ko.mkdir()
    (en / "a.md").write_text(
        "# A\n\nNever do X.\n\nDo not do Y.\n", encoding="utf-8"
    )
    (ko / "a.md").write_text(
        "# A\n\nX와 Y를 하지 않습니다.\n", encoding="utf-8"
    )
    report = audit(en, ko)
    assert report["structurally_aligned_pages"] == 0
    assert report["advisory_prohibition_risks"] == []
    assert len(report["pages"][0]["en_units"]) == 3
    assert len(report["pages"][0]["ko_units"]) == 2


def test_no_false_semantic_certificate_on_matching_blocks(tmp_path: Path) -> None:
    en, ko = tmp_path / "en", tmp_path / "ko"
    en.mkdir()
    ko.mkdir()
    (en / "a.md").write_text("# Guide\n\nNever do X.\n", encoding="utf-8")
    (ko / "a.md").write_text("# 안내\n\nX는 하지 마십시오.\n", encoding="utf-8")
    report = audit(en, ko)
    assert report["advisory_prohibition_risks"] == []
    assert report["independent_sentence_review_complete"] is False
    assert report["pages"][0]["aligned_by_structure"] is True
